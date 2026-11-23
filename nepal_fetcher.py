"""
nepal_fetcher.py
High-performance news & social media fetcher for Nepal.
1. Monitors leading online newspapers and digital portals in Nepal (both Nepali and English).
2. Classifies content under 8 structured geo-political categories.
3. Dedicated monitoring of Nepal coverage across Top Indian Media (English & Hindi).
"""

import os
import time
import logging
import datetime
import zoneinfo
import urllib.request
import urllib.parse
import ssl
import concurrent.futures
import threading
import collections
import re
import html
import json
from typing import Dict, Any, List, Optional, Tuple
import requests
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dt_parser
from nepal_news_store import (
    batch_upsert_articles,
    record_source_error,
    normalize_canonical_url,
    generate_canonical_id,
    get_stored_articles,
    register_portal_sources,
    ingest_indian_articles_batch,
    get_stored_indian_articles,
    get_indian_media_audit_stats,
    get_existing_indian_hydrated_ids,
    get_existing_article_urls,
    record_indian_source_health,
)

logger = logging.getLogger("nepal_fetcher")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from nepal_config import (
    NEPAL_TZ,
    DEFAULT_NEPAL_RELEVANCE_THRESHOLD,
    BORDERLINE_NEPAL_RELEVANCE_FLOOR,
    STRUCTURED_CATEGORIES,
    CATEGORY_ICONS,
    TOP_NEPAL_NEWS_PORTALS,
    TOP_INDIAN_MEDIA_SOURCES,
    parse_to_nepal_time,
    format_exc,
    DEFAULT_HEADERS,
    _has_devanagari,
    format_nepal_relative_time,
)

SSL_CTX = ssl._create_unverified_context()

from nepal_summarizer import (
    enrich_articles_with_english_summaries,
)

from requests.adapters import HTTPAdapter
from urllib3.util import Retry

_HTTP_SESSION_LOCAL = threading.local()
_FEED_HTTP_CACHE: Dict[str, Dict[str, Any]] = {}
_FEED_HTTP_CACHE_LOCK = threading.Lock()


def get_worker_session() -> requests.Session:
    """Returns a thread-local persistent requests.Session with connection pooling."""
    sess = getattr(_HTTP_SESSION_LOCAL, "session", None)
    if sess is None:
        sess = requests.Session()
        retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(pool_connections=25, pool_maxsize=25, max_retries=retries)
        sess.mount("https://", adapter)
        sess.mount("http://", adapter)
        _HTTP_SESSION_LOCAL.session = sess
    return sess


def fetch_feed_with_conditional_cache(
    url: str,
    timeout_secs: float = 8.0,
    headers: Optional[Dict[str, str]] = None,
    verify: bool = False,
) -> Tuple[Optional[bytes], bool, int]:
    """
    Fetches raw bytes for a feed or page using persistent HTTP session and conditional headers (ETag / If-Modified-Since).
    Returns (content_bytes, is_modified, status_code).
    If server returns 304 Not Modified, content_bytes is None (or cached), is_modified=False, status_code=304.
    """
    sess = get_worker_session()
    req_headers = dict(DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)

    parsed_u = urllib.parse.urlparse(url)
    origin = f"{parsed_u.scheme}://{parsed_u.netloc}/" if parsed_u.scheme and parsed_u.netloc else url
    req_headers.setdefault("Referer", origin)

    with _FEED_HTTP_CACHE_LOCK:
        cached_meta = _FEED_HTTP_CACHE.get(url, {})

    if cached_meta.get("etag"):
        req_headers["If-None-Match"] = cached_meta["etag"]
    if cached_meta.get("last_modified"):
        req_headers["If-Modified-Since"] = cached_meta["last_modified"]

    try:
        resp = sess.get(url, headers=req_headers, timeout=timeout_secs, verify=verify)
        if resp.status_code == 304:
            return None, False, 304
        if resp.status_code == 200:
            etag = resp.headers.get("ETag") or resp.headers.get("etag")
            last_mod = resp.headers.get("Last-Modified") or resp.headers.get("last-modified")
            if etag or last_mod:
                with _FEED_HTTP_CACHE_LOCK:
                    _FEED_HTTP_CACHE[url] = {
                        "etag": etag,
                        "last_modified": last_mod,
                        "updated_at": time.time(),
                    }
            return resp.content, True, 200
        return resp.content, True, resp.status_code
    except Exception as exc:
        logger.debug(f"Conditional fetch failed for {url}: {exc}")
        raise

class _ThreadSafeLRUCache:
    """Thread-safe, bounded in-memory LRU cache with dict-like semantics."""

    def __init__(self, maxsize: int = 1000):
        self._maxsize = max(1, maxsize)
        self._cache: collections.OrderedDict[Any, Any] = collections.OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            if key not in self._cache:
                return default
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: Any, value: Any) -> None:
        self[key] = value

    def pop(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            return self._cache.pop(key, default)

    def setdefault(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            if len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)
            self._cache[key] = default
            return default

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def __getitem__(self, key: Any) -> Any:
        with self._lock:
            if key not in self._cache:
                raise KeyError(key)
            self._cache.move_to_end(key)
            return self._cache[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            elif len(self._cache) >= self._maxsize:
                self._cache.popitem(last=False)
            self._cache[key] = value

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._cache

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)


# Full article news text in-memory bounded LRU cache
FULL_ARTICLE_TEXT_CACHE = _ThreadSafeLRUCache(maxsize=1000)
# Published date in-memory bounded LRU cache
ARTICLE_DATE_CACHE = _ThreadSafeLRUCache(maxsize=1000)
# Resolved t.co shortlink bounded LRU cache
TCO_REDIRECT_CACHE = _ThreadSafeLRUCache(maxsize=1000)
# Resolved Google News RSS article redirect bounded LRU cache
GNEWS_URL_CACHE = _ThreadSafeLRUCache(maxsize=1000)
# Domains served via official X syndication bridge rather than direct HTML scraping (empty: all portals direct-scrapable)
_SKIP_DIRECT_SCRAPE_DOMAINS = frozenset()


def _is_direct_scrape_skipped(url: str) -> bool:
    if not url:
        return False
    try:
        host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
        return host in _SKIP_DIRECT_SCRAPE_DOMAINS
    except Exception:
        return False


def extract_article_full_text(url: str, timeout: int = 8) -> str:
    """
    Extracts the complete news article body text from an article URL.
    Harvests JSON-LD articleBody and OpenGraph meta descriptions before DOM stripping
    so teaser-only RSS or JS portals still yield complete multi-sentence text.
    """
    if not url or not url.startswith("http"):
        return ""
    if _is_direct_scrape_skipped(url):
        return ""
    if url in FULL_ARTICLE_TEXT_CACHE and len(FULL_ARTICLE_TEXT_CACHE[url]) > 600:
        return FULL_ARTICLE_TEXT_CACHE[url]

    try:
        raw_html = ""
        try:
            req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
                raw_html = resp.read().decode("utf-8", errors="ignore")
        except Exception:
            parsed_u = urllib.parse.urlparse(url)
            origin = f"{parsed_u.scheme}://{parsed_u.netloc}/" if parsed_u.scheme and parsed_u.netloc else url
            r_resp = requests.get(
                url,
                headers={**DEFAULT_HEADERS, "Referer": origin},
                timeout=timeout,
                verify=False,
            )
            if r_resp.ok:
                raw_html = r_resp.text
        if not raw_html:
            return ""

        # Primary: Trafilatura full-body extraction
        try:
            import trafilatura
            traf_extracted = trafilatura.extract(raw_html, url=url, include_comments=False, include_tables=False)
            if traf_extracted and len(traf_extracted.strip()) >= 350:
                body_clean = re.sub(r"[\r\n\t]+", "\n\n", traf_extracted.strip())
                FULL_ARTICLE_TEXT_CACHE[url] = body_clean
                return body_clean
        except Exception:
            pass

        soup = BeautifulSoup(raw_html, "html.parser")

        # Extract JSON-LD articleBody and meta description BEFORE stripping tags
        json_ld_texts = []
        for ld_tag in soup.find_all("script", type="application/ld+json"):
            try:
                ld_raw = ld_tag.string or ld_tag.get_text() or ""
                if not ld_raw.strip():
                    continue
                ld_obj = json.loads(ld_raw)
                items_ld = ld_obj if isinstance(ld_obj, list) else [ld_obj]
                for node in items_ld:
                    if isinstance(node, dict):
                        for graph_item in (node.get("@graph") or [node]):
                            if isinstance(graph_item, dict):
                                body_val = graph_item.get("articleBody") or graph_item.get("description") or ""
                                if isinstance(body_val, str) and len(body_val.strip()) > 80:
                                    json_ld_texts.append(html.unescape(body_val.strip()))
            except Exception:
                pass

        meta_desc = ""
        for meta_prop in [("property", "og:description"), ("name", "description"), ("name", "twitter:description")]:
            m_tag = soup.find("meta", attrs={meta_prop[0]: meta_prop[1]})
            if m_tag and m_tag.get("content"):
                cand = html.unescape(str(m_tag["content"]).strip())
                if len(cand) > len(meta_desc):
                    meta_desc = cand

        # Strip script, styles, buttons, navigation, headers, footers, captions, sidebars, and related widgets
        for tag in soup(["script", "style", "noscript", "svg", "button", "header", "footer", "nav", "form", "iframe", "figcaption"]):
            tag.decompose()
        for noisy in soup.select(
            ".comments, #comments, .comment-box, .comment-section, .related-news, .trending-news, "
            ".popular-news, .share-box, .social-share, .author-box, .author-bio, .login-box, .signup-box, "
            ".ok-conv-box, .post-navigation, .breadcrumb, .tags, .tag-list, .advertisement, .ad-box, "
            ".sidebar, .widget, .most-read, .recommended, .more-news, .also-read, .caption, .wp-caption-text, "
            ".rep-paywall, .paywall-box, .login-container, .rep-related, .related-stories, .opinion-box, .section-01, "
            ".col-right, .right-sidebar, .sidebar-widget"
        ):
            noisy.decompose()
        for tag in soup.find_all("aside"):
            # Retain aside if it contains main content column (e.g. Setopati left-side)
            if not any(c in str(tag.get("class", [])) for c in ["left-side", "content", "main", "col-"]):
                tag.decompose()

        specific_containers = soup.select(
            ".editor-box, #textToRead, .the-content, .rep-body--regular, .rep-article-container, "
            ".news_detail-para, .content__desc, .detail-content-paragraph, .news__details, "
            ".content__para, .detail__page-content, "
            ".ok18-single-post-content-wrap, .story-content, .article-content, "
            ".entry-content, .post-content, .news-content, .detail-content, .story__content, "
            ".article__body, .news_detail, .full-content, .content-body, #content-body, "
            ".main-content, .story-details, .news_description, .entry-content-wrap, "
            ".post-detail, .story-with-main-sec"
        )
        content_containers = specific_containers if specific_containers else soup.select("article")
        
        paras = []
        if content_containers:
            for c in content_containers:
                for p in c.find_all(["p", "div"]):
                    if p.name == "p" or (p.name == "div" and not p.find(["p", "div"])):
                        txt = p.get_text(" ", strip=True)
                        if txt and txt not in paras and len(txt) > 20:
                            paras.append(txt)
                if len(" ".join(paras)) >= 400:
                    break

        # Fallback to all paragraphs only when no specific article container yielded substantive body text
        min_container_len = 100 if specific_containers else 250
        if len(" ".join(paras)) < min_container_len:
            paras = []
            for p in soup.find_all("p"):
                txt = p.get_text(" ", strip=True)
                if txt and txt not in paras and len(txt) > 20:
                    paras.append(txt)

        stop_markers = [
            "भर्खरै पुराना लोकप्रिय",
            "खाता खोल्नु भएको छैन",
            "साइनअप गर्नुहोस्",
            "प्रतिक्रिया दिनुहोस्",
            "तपाईंको प्रतिक्रिया",
            "leave a reply",
            "post a comment",
            "नेपाललाइभमा प्रकाशित सामग्रीबारे कुनै गुनासो",
            "सूचना विभाग दर्ता नं",
            "सूचना विभाग दर्ता",
            "gain access to up to 10 free articles",
            "already have an account? log in",
            "already have an account? log",
            "पछिल्लो अध्यावधिक:",
            "पछिल्लो अपडेट:",
        ]
        skip_phrases = [
            "cookie policy", "privacy policy", "terms of service", "terms of use",
            "all rights reserved", "advertisement", "copyright ©", "download our app",
            "rights reserved", "subscribe to", "news summary generated by ok ai",
            "वा इमेल/सोसल मिडियामार्फत् लगइन",
            "nepallivenews@gmail.com",
            "nepallivenews",
            "प्रकाशित मिति:",
        ]

        clean = []
        for p in paras:
            low = p.lower()
            if any(m in low for m in stop_markers):
                break
            if any(b in low for b in skip_phrases) or p.startswith("#"):
                continue
            clean.append(p)

        dom_text = "\n\n".join(clean).strip()
        best_ld = max(json_ld_texts, key=len) if json_ld_texts else ""
        if len(best_ld) > len(dom_text) + 100:
            full_text = best_ld
        elif len(dom_text) >= 120:
            full_text = dom_text
        else:
            full_text = max([dom_text, best_ld, meta_desc], key=len).strip()

        if full_text:
            FULL_ARTICLE_TEXT_CACHE[url] = full_text
            return full_text
    except Exception:
        pass
    return ""

def batch_fetch_full_content(articles: list, max_workers: int = 25, summarize_english: bool = False) -> list:
    """
    Extracts full article text in parallel and enriches articles with LexRank English
    headlines and summaries, persisting all enriched fields back to Supabase.
    """
    to_fetch = []
    for art in articles:
        link = art.get("link", "")
        existing_fc = (art.get("full_content") or "").strip()
        summary = (art.get("summary") or "").strip()
        title = (art.get("title") or "").strip()
        needs_body = (
            len(existing_fc) < 400
            or "..." in existing_fc
            or "appeared first on" in existing_fc.lower()
            or existing_fc == summary
            or existing_fc == title
            or summary == title
            or "..." in summary
        )
        if link in FULL_ARTICLE_TEXT_CACHE and len(FULL_ARTICLE_TEXT_CACHE[link]) > max(len(existing_fc), 400):
            art["full_content"] = FULL_ARTICLE_TEXT_CACHE[link]
        elif link.startswith("http") and needs_body and not _is_direct_scrape_skipped(link):
            to_fetch.append(art)

    if to_fetch:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        try:
            future_to_art = {
                executor.submit(extract_article_full_text, a.get("link", "")): a
                for a in to_fetch
            }
            try:
                for fut in concurrent.futures.as_completed(future_to_art, timeout=25):
                    a = future_to_art[fut]
                    try:
                        extracted = fut.result(timeout=3)
                        existing_fc = (a.get("full_content") or a.get("summary") or "").strip()
                        if extracted and len(extracted) > len(existing_fc):
                            a["full_content"] = extracted
                        elif not a.get("full_content"):
                            a["full_content"] = existing_fc or a.get("title", "")
                    except Exception:
                        if not a.get("full_content"):
                            a["full_content"] = a.get("summary") or a.get("title", "")
            except concurrent.futures.TimeoutError:
                pass
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    if summarize_english and articles:
        enrich_articles_with_english_summaries(articles, max_workers=min(max_workers, 20))

    if articles:
        try:
            from nepal_news_store import persist_enriched_full_content
            persist_enriched_full_content(articles)
        except Exception:
            pass
    return articles

# Category Taxonomy, Portals & parse_to_nepal_time live in nepal_config.py (imported above for compatibility)

def classify_article_editorial(
    title: str,
    summary: str = "",
    source: str = "",
    full_content: str = ""
) -> Dict[str, Any]:
    """
    High-precision Editorial Classification Engine for Nepal Media & Intelligence Monitor.
    Accurately classifies news into 9 structured canonical sections:
    1. India Section
    2. China Section
    3. Bangladesh Section
    4. Pakistan Section
    5. Nepal – Internal
    6. Nepal – External
    7. Nepal – Economy
    8. Nepal – Others
    9. International News

    Supports multi-section canonical associations (e.g. cross-listing bilateral stories
    in both Country Section and Nepal – External), secondary thematic tags, and confidence scoring.
    """
    title_str = (title or "").strip()
    sum_str = (summary or "").strip()
    body_str = (full_content or "").strip()[:1500]
    source_str = (source or "").strip()

    title_lower = title_str.lower()
    full_text = f"{title_str} {sum_str} {body_str}".lower()

    scores = {
        "India Section": 0,
        "China Section": 0,
        "Bangladesh Section": 0,
        "Pakistan Section": 0,
        "Nepal – Internal": 0,
        "Nepal – External": 0,
        "Nepal – Economy": 0,
        "International News": 0,
        "Nepal – Others": 0,
    }
    secondary_tags = set()

    def evaluate_patterns(patterns, regexes, cat_name, tag_name=None, title_mult=3, body_mult=1):
        matched = False
        for p in patterns:
            p_lower = p.lower()
            if p_lower in title_lower:
                scores[cat_name] += title_mult
                matched = True
            elif p_lower in full_text:
                scores[cat_name] += body_mult
                matched = True
        for r in regexes:
            if re.search(r, title_lower):
                scores[cat_name] += title_mult
                matched = True
            elif re.search(r, full_text):
                scores[cat_name] += body_mult
                matched = True
        if matched and tag_name:
            secondary_tags.add(tag_name)
        return matched

    # 1. Bilateral / Nepal Context Detector
    nepal_indicators = [
        "nepal", "nepali", "nepalese", "kathmandu", "काठमाडौं", "काठमाडौँ", "नेपाल", "नेपाली",
        "सिंहदरबार", "बालुवाटार", "द्विपक्षीय", "bilateral", "दौत्य", "ओली", "देउवा", "प्रचण्ड"
    ]
    is_bilateral_nepal = any(k in full_text for k in nepal_indicators)

    # -------------------------------------------------------------------------
    # A. BANGLADESH SECTION
    # -------------------------------------------------------------------------
    bd_patterns = [
        "बंगलादेश", "बङ्गलादेश", "बंगलादेशी", "बङ्गलादेशी", "बंगलादेश दूतावास", "नेपाल-बंगलादेश",
        "नेपाल–बंगलादेश", "रोहनपुर", "सिंघावाद", "फुलबारी", "बंगलाबन्ध", "शेख हसिना", "हसिना",
        "मुहम्मद युनुस", "युनुस सरकार", "अवामी लिग", "बिएनपी", "साफ महिला", "४० मेगावाट",
        "विद्युत् व्यापार (बंगलादेश)", "बिजुली बंगलादेश", "bangladesh", "bangladeshi",
        "bangladesh embassy", "nepal-bangladesh", "sheikh hasina", "hasina", "muhammad yunus",
        "yunus", "tripartite power", "power export to bangladesh", "electricity to bangladesh",
        "rohanpur", "singhabad", "phulbari", "banglabandha", "tarique rahman", "khaleda zia"
    ]
    bd_regex = [
        r'\bdhaka\b',
        r'(?:^|[\s,।!?—\(\)\[\]"\'\/])ढाका(?:$|[\s,।!?—\(\)\[\]"\'\/]|मा|को|ले|सँग|सित|बाट|तिर)',
        r'\b40\s*mw\b'
    ]
    if evaluate_patterns(bd_patterns, bd_regex, "Bangladesh Section", "Bangladesh"):
        secondary_tags.add("South Asia")

    # -------------------------------------------------------------------------
    # B. PAKISTAN SECTION
    # -------------------------------------------------------------------------
    pak_patterns = [
        "पाकिस्तान", "पाकिस्तानी", "इस्लामाबाद", "पाकिस्तानी दूतावास", "नेपाल-पाकिस्तान", "शाहबाज सरिफ",
        "इमरान खान", "बाबर आजम", "पिटिएपी", "पाकिस्तान छात्रवृत्ति", "कराची", "लाहोर", "रावलपिण्डी",
        "सार्क शिखर सम्मेलन", "नेपाल–पाकिस्तान", "असिम मुनिर", "पाकिस्तानी सेना", "आइएसआइ",
        "pakistan", "pakistani", "islamabad", "pakistan embassy", "nepal-pakistan", "pak-nepal",
        "shehbaz sharif", "shehbaz", "imran khan", "pti", "babar azam", "shaheen afridi", "ptap",
        "pakistan scholarship", "karachi", "lahore", "rawalpindi", "psl", "pakistan super league",
        "pak army", "general munir", "bilawal bhutto", "cpec"
    ]
    pak_regex = [r'\bislamabad\b', r'\bpti\b', r'\brawalpindi\b']
    if evaluate_patterns(pak_patterns, pak_regex, "Pakistan Section", "Pakistan"):
        secondary_tags.add("Regional Security")

    # -------------------------------------------------------------------------
    # C. CHINA SECTION
    # -------------------------------------------------------------------------
    china_patterns = [
        "चीन", "चिनियाँ", "बेइजिङ", "सि चिनफिङ", "सी चिनफिङ", "बिआरआई", "केरुङ", "तातोपानी",
        "ल्हासा", "नेपाल-चीन", "चिनियाँ दूतावास", "पोखरा विमानस्थल", "पोखरा अन्तर्राष्ट्रिय विमानस्थल",
        "चिनियाँ अनुदान", "चिनियाँ नागरिक", "रसुवागढी", "हुम्ला सीमा", "कोरला", "किमाथाङ्का",
        "हिल्सा", "तिब्बत", "ऋणको पासो", "चीन-नेपाल", "चिनियाँ लगानी", "चिनियाँ सहयोग", "सिगात्से",
        "नेपाल–चीन", "चिनियाँ ठेकेदार", "वाङ यी", "चिनियाँ कम्युनिष्ट पार्टी", "ताइवान",
        "china", "chinese", "beijing", "xi jinping", "belt and road", "kerung", "kyirong",
        "tatopani", "rasuwagadhi", "lhasa", "sino-nepal", "nepal-china", "china-nepal",
        "chinese embassy", "pokhara airport", "pokhara international airport", "chinese contractor",
        "tibet", "tibetan", "trans-himalayan", "debt trap", "korala", "kimathanka", "hilsa",
        "chinese loan", "chinese grant", "exim bank", "shigatse", "humla border", "chinese aid",
        "communist party of china", "pla", "peoples liberation army", "wang yi", "taiwan"
    ]
    china_regex = [r'\bbri\b', r'\bcpc\b', r'\bpla\b']
    if evaluate_patterns(china_patterns, china_regex, "China Section", "China"):
        secondary_tags.add("Connectivity & BRI")

    # -------------------------------------------------------------------------
    # D. INDIA SECTION
    # -------------------------------------------------------------------------
    india_patterns = [
        "भारत", "भारतीय", "नयाँ दिल्ली", "दिल्ली", "नरेन्द्र मोदी", "मोदी", "जयशंकर", "नेपाल-भारत",
        "भारत-नेपाल", "भारतीय दूतावास", "रक्सौल", "लिपुलेक", "लिम्पियाधुरा", "कालापानी", "सुस्ता",
        "पञ्चेश्वर", "नेपालगन्ज नाका", "विराटनगर भन्सार", "खुला सीमा", "भारतीय सेना", "इपिजी",
        "नाकाबन्दी", "१९५० सन्धि", "१९५० को सन्धि", "सीमा विवाद", "एसएसबी", "विद्युत् निर्यात (भारत)",
        "अयोध्या", "रामायण सर्किट", "सुनौली", "जोगबनी", "जयनगर", "कुर्था", "हिन्दुत्व", "बलिउड",
        "अग्निपथ", "अग्निवीर", "गोर्खा भर्ती", "बिहार", "उत्तर प्रदेश", "उत्तराखण्ड", "पश्चिम बंगाल",
        "सिक्किम", "दार्जिलिङ", "सिलिगुडी", "अमित शाह", "राहुल गान्धी", "भाजपा", "बिजेपी", "लोकसभा",
        "राज्यसभा", "भारतीय सर्वोच्च अदालत",
        "india", "indian", "new delhi", "delhi", "modi", "narendra modi", "jaishankar", "amit shah",
        "nepal-india", "indo-nepal", "india-nepal", "indian embassy", "lipulekh", "limpiyadhura",
        "kalapani", "susta", "pancheshwar", "icp birgunj", "cross-border railway", "epg report",
        "1950 treaty", "blockade", "border dispute", "open border", "ssb", "power export to india",
        "electricity to india", "hindutva", "bollywood", "agniveer", "agnipath", "gorkha recruitment",
        "jogbani", "kakarbhitta", "sunauli", "raxaul", "bihar", "uttar pradesh", "uttarakhand",
        "west bengal", "sikkim", "darjeeling", "siliguri", "bjp", "lok sabha", "rajya sabha",
        "rahul gandhi", "isro", "reserve bank of india"
    ]
    india_regex = [r'\bbjp\b', r'\brbi\b', r'\bssb\b', r'\bisro\b', r'\bnda\b']
    if evaluate_patterns(india_patterns, india_regex, "India Section", "India"):
        secondary_tags.add("Bilateral & Border")
    # Native boost for Indian Media Press sources
    if any(k in source_str.lower() for k in ["indian express", "hindu", "tribune", "india today", "ndtv", "livemint", "business standard", "amar ujala", "live hindustan", "jansatta", "prabhat khabar", "the quint", "swarajya", "oneindia", "moneycontrol"]):
        scores["India Section"] += 2
        secondary_tags.add("Indian Press")

    # -------------------------------------------------------------------------
    # E. NEPAL – INTERNAL
    # -------------------------------------------------------------------------
    internal_patterns = [
        "सरकार", "राजनीति", "संसद", "संसदीय", "निर्वाचन", "चुनाव", "संविधान", "मन्त्रिपरिषद्",
        "मन्त्रिपरिषद", "प्रधानमन्त्री", "उपप्रधानमन्त्री", "ओली", "प्रचण्ड", "देउवा", "रवि लामिछाने",
        "माओवादी", "एमाले", "कांग्रेस", "काङ्ग्रेस", "नेकपा एमाले", "च्यासल", "सानेपा", "नेविसंघ",
        "तरुण दल", "युवा संघ", "अनेरास्ववियु", "शेरबहादुर देउवा", "शेखर कोइराला", "रास्वपा", "राप्रपा",
        "सर्वोच्च अदालत", "सर्वोच्च", "अदालत", "न्यायाधीश", "प्रधानन्यायाधीश", "उच्च अदालत",
        "विशेष अदालत", "आईजीपी", "नेपाल प्रहरी", "विधेयक", "सभामुख", "बालेन", "बालेन शाह", "हर्क साम्पाङ",
        "साम्पाङ", "महानगर", "काठमाडौं महानगर", "मेयर", "मन्त्री", "मुख्यमन्त्री", "प्रदेश सभा",
        "गठबन्धन", "अख्तियार", "सीआईएए", "सिंहदरबार", "हेलो सरकार", "गृह मन्त्रालय", "मुख्यसचिव",
        "निजामती", "कर्मचारी", "राहदानी", "राष्ट्रिय परिचयपत्र", "नागरिकता", "भ्रष्टाचार", "अनियमितता",
        "सहकारी ठगी", "सहकारी छानबिन", "सूर्यदर्शन", "सुप्रिम सहकारी", "स्थानीय तह", "नगरपालिका",
        "गाउँपालिका", "मधेश प्रदेश", "तराई-मधेश", "जसपा", "जनमत पार्टी", "सिके राउत", "लोसपा",
        "नागरिक उन्मुक्ति", "रेशम चौधरी", "आन्दोलन", "हड्ताल", "शिक्षक आन्दोलन", "फास्ट ट्र्याक",
        "politics", "political", "parliament", "parliamentary", "cabinet", "election", "constitution",
        "prime minister", "pm oli", "deuba", "prachanda", "ravi lamichhane", "rabi lamichhane",
        "uml", "cpn-uml", "cpn uml", "nepali congress", "maoist centre", "rsp", "supreme court",
        "chief justice", "high court", "special court", "judge", "bill", "speaker", "balen",
        "balen shah", "mayor", "minister", "provincial", "ciaa", "anti-corruption", "singha durbar",
        "singhadurbar", "nepal government", "home ministry", "chief secretary", "civil service",
        "local governance", "municipality", "harka sampang", "cooperative fraud", "nepal police",
        "bureaucracy", "citizenship bill", "national id", "hello sarkar", "cpn (uml)"
    ]
    internal_regex = [
        r'\bgov\b', r'\bgovernment\b', r'\bciaa\b', r'\brsp\b', r'\buml\b', r'\bkmc\b',
        r'\bpmo\b', r'\bmoha\b', r'\bnc\b', r'\bannfsu\b', r'\byan\b'
    ]
    if evaluate_patterns(internal_patterns, internal_regex, "Nepal – Internal", "Governance & Politics"):
        secondary_tags.add("Domestic Affairs")

    # -------------------------------------------------------------------------
    # F. NEPAL – EXTERNAL
    # -------------------------------------------------------------------------
    external_patterns = [
        "परराष्ट्र", "परराष्ट्रमन्त्री", "परराष्ट्र मन्त्रालय", "राजदूत", "दूतावास", "कूटनीतिक",
        "द्विपक्षीय", "बहुपक्षीय", "संयुक्त राष्ट्रसंघ", "राष्ट्रसंघ", "युएन", "शान्ति सेना",
        "शान्ति मिसन", "युनिफिल्", "युनेस्को", "युनिसेफ", "विश्व बैंक", "आइएमएफ", "एडिबी",
        "डब्लुटिओ", "सार्क", "बिम्सटेक", "असंलग्न", "अमेरिका", "अमेरिकी", "वाशिंगटन", "एमसीसी",
        "एसपीपी", "युएसएड", "डिभी", "डिभी चिट्ठा", "ह्वाइट हाउस", "पेन्टागन", "ट्रम्प", "बाइडेन",
        "बेलायत", "ब्रिटिश", "गोर्खा पेन्सन", "युरोपेली युनियन", "ईयू", "इयु", "युरोप", "फ्रान्स",
        "जर्मनी", "स्विट्जरल्याण्ड", "नर्वे", "हवाई कालोसूची", "जापान", "जापानी", "जाइका",
        "दक्षिण कोरिया", "कोरिया", "इपिएस", "इजरायल", "विपिन जोशी", "रसिया", "रूसी सेना", "रुस",
        "युक्रेन", "कतार", "युएई", "साउदी अरेबिया", "मलेसिया", "वैदेशिक रोजगारी", "श्रम सम्झौता",
        "अष्ट्रेलिया", "क्यानडा", "भुटान", "श्रीलंका", "मालदिभ्स", "विदेशी सहायता", "अनुदान",
        "diplomatic", "bilateral relations", "foreign ministry", "foreign minister", "ambassador",
        "embassy", "united states", "american", "washington", "mcc", "spp", "usaid", "peace corps",
        "dv lottery", "white house", "trump", "biden", "pentagon", "britain", "british", "gurkha pension",
        "european union", "europe", "france", "germany", "switzerland", "aviation blacklist",
        "schengen", "united nations", "unicef", "undp", "peacekeeping", "peacekeepers", "world bank",
        "saarc", "saarc secretariat", "saarc summit", "bimstec", "bimstec summit", "japan",
        "jica", "south korea", "korea", "eps", "israel", "bipin joshi", "russia", "russian army",
        "ukraine", "qatar", "uae", "saudi", "malaysia", "foreign employment", "migrant worker",
        "australia", "canada", "bhutan", "sri lanka", "foreign aid"
    ]
    external_regex = [
        r'\busa\b', r'\bu\.s\.\b', r'\beu\b', r'\bmcc\b', r'\bspp\b', r'\busaid\b',
        r'\bsaarc\b', r'\bbimstec\b', r'\bworld bank\b', r'\bimf\b', r'\badb\b', r'\bwto\b',
        r'\bmofa\b', r'\bun\b', r'\bunga\b', r'\bunifil\b'
    ]
    if evaluate_patterns(external_patterns, external_regex, "Nepal – External", "Foreign Relations"):
        secondary_tags.add("Diplomacy")

    # -------------------------------------------------------------------------
    # G. NEPAL – ECONOMY
    # -------------------------------------------------------------------------
    economy_patterns = [
        "अर्थतन्त्र", "बजेट", "आर्थिक", "बैंक", "बैंकिङ", "नेपाल राष्ट्र बैंक", "राष्ट्र बैंक",
        "मौद्रिक नीति", "नेप्से", "सेयर", "शेयर", "धितोपत्र", "चाँदी", "मुद्रास्फीति", "महँगी",
        "राजस्व", "आयकर", "करदाता", "कर प्रणाली", "कर छुट", "पुँजीगत लाभकर", "अन्तःशुल्क",
        "भन्सार", "रेमिट्यान्स", "विप्रेषण", "व्यापार घाटा", "निर्यात", "आयात", "व्यवसाय",
        "उद्योग", "लगानी", "ऋण", "बीमा", "डलर", "लघुवित्त", "निक्षेप", "कर्जा", "ब्याजदर",
        "तरलता", "विदेशी मुद्रा सञ्चिति", "धितोपत्र बोर्ड", "सेबोन", "लाभांश", "बोनस सेयर",
        "हकप्रद", "आईपिओ", "आईपीओ", "सूचीकृत", "कारोबार", "उद्यमशीलता", "निजी क्षेत्र",
        "एफएनसीसीआई", "परिसंघ", "सुनचाँदी", "सुनको भाउ", "पेट्रोलियम", "डिजेल", "खाना पकाउने ग्यास",
        "पुँजीगत खर्च", "वित्तीय घाटा", "पर्यटन", "पर्यटक आगमन", "होटल", "पर्वतारोहण",
        "नागरिक उड्डयन", "नेपाल वायुसेवा", "नेपाल एयरलाइन्स", "जलविद्युत", "विद्युत् प्राधिकरण",
        "अपर तामाकोशी", "नेपाल आयल निगम",
        "economy", "economic", "budget", "bank", "banking", "monetary policy", "nepse",
        "stock", "share market", "gold", "silver", "inflation", "revenue", "tax", "customs",
        "remittance", "trade deficit", "export", "import", "business", "industry", "investment",
        "loan", "insurance", "finance", "financial", "forex", "dollar", "microfinance",
        "deposit", "credit", "interest rate", "liquidity", "forex reserve", "sebon", "dividend",
        "bonus share", "right share", "ipo", "listed company", "turnover", "bullion", "fuel price",
        "petroleum", "fdi", "foreign direct investment", "fiscal deficit", "public debt",
        "commercial bank", "central bank", "capital expenditure", "fncci", "cni", "tourism",
        "tourist arrival", "civil aviation", "caan", "nepal airlines", "hydropower", "nea"
    ]
    economy_regex = [
        r'\bnrb\b', r'\bgdp\b', r'\bnepse\b', r'\bsebon\b', r'\bipo\b', r'\bfdi\b',
        r'\bfncci\b', r'\bcni\b', r'\bforex\b', r'\bvat\b', r'\bnoc\b', r'\bnea\b'
    ]
    if evaluate_patterns(economy_patterns, economy_regex, "Nepal – Economy", "Economy & Finance"):
        secondary_tags.add("Markets & Trade")

    # -------------------------------------------------------------------------
    # H. INTERNATIONAL NEWS (Major global events without primary Nepal focus)
    # -------------------------------------------------------------------------
    intl_patterns = [
        "विश्व", "विश्व समाचार", "अन्तर्राष्ट्रिय समाचार", "युक्रेन युद्ध", "रुस-युक्रेन", "गाजा",
        "इजरायल-हमास", "हिजबुल्लाह", "लेबनान", "मध्यपूर्व", "लाल सागर", "हुथी", "सिरिया", "सुडान",
        "नेटो", "जी-७", "जी-२०", "ब्रिक्स", "अमेरिकी राष्ट्रपति निर्वाचन", "अमेरिकी सिनेट",
        "ट्रम्प प्रशासन", "कमला ह्यारिस", "पुतिन", "जेलेन्स्की", "नेतान्याहू", "अमेरिकी फेडरल रिजर्भ",
        "वाल स्ट्रिट", "ओपेक", "कच्चा तेल", "ओपनएआई", "च्याटजिपिटी", "नासा", "स्पेसएक्स",
        "international news", "world news", "global news", "ukraine war", "russia-ukraine",
        "gaza", "israel-hamas", "hezbollah", "lebanon war", "middle east crisis", "red sea",
        "houthis", "syria", "sudan conflict", "nato summit", "g7", "g20 summit", "brics summit",
        "us presidential election", "white house", "us senate", "pentagon", "donald trump",
        "kamala harris", "joe biden", "vladimir putin", "zelenskyy", "netanyahu", "federal reserve",
        "wall street", "dow jones", "nasdaq", "opec", "crude oil", "openai", "chatgpt", "deepmind",
        "artificial intelligence regulation", "nasa", "spacex", "starship", "un security council resolution"
    ]
    intl_regex = [
        r'\bnato\b', r'\bg7\b', r'\bg20\b', r'\bbrics\b', r'\bopec\b',
        r'\bicj\b', r'\bicc\b', r'\bopenai\b', r'\bnasa\b'
    ]
    if evaluate_patterns(intl_patterns, intl_regex, "International News", "Global Affairs"):
        secondary_tags.add("World News")

    # -------------------------------------------------------------------------
    # I. NEPAL – OTHERS (Sports, Culture, Entertainment, Environment, Disasters)
    # -------------------------------------------------------------------------
    others_patterns = [
        "खेलकुद", "क्रिकेट", "क्यान", "नेपाल क्रिकेट", "टी-२०", "एनपिएल", "नेपाल प्रिमियर लिग",
        "रोहित पौडेल", "दीपेन्द्र सिंह ऐरी", "सन्दीप लामिछाने", "पारस खड्का", "फुटबल", "एन्फा",
        "चलचित्र", "फिल्म", "सिनेमा", "बक्स अफिस", "अभिनेता", "अभिनेत्री", "नायक", "नायिका",
        "गीत", "संगीत", "गायक", "गायिका", "साहित्य", "पुस्तक", "मिस नेपाल", "टेकपाना",
        "सूचना प्रविधि", "नेपाल टेलिकम", "एनसेल", "स्वास्थ्य", "अस्पताल", "डेंगु", "सगरमाथा",
        "हिमाल", "राष्ट्रिय निकुञ्ज", "चितवन निकुञ्ज", "बाघ", "गैंडा", "भूकम्प", "बाढी",
        "पहिरो", "मौसम", "वर्षा", "हिमपात", "शीतलहर", "चाडपर्व", "दशैं", "दसैं", "तिहार",
        "छठ", "तीज", "ल्होसार", "माघी", "संस्कृति", "सम्पदा",
        "cricket", "can", "cricket association of nepal", "t20", "npl", "nepal premier league",
        "rohit paudel", "paras khadka", "dipendra singh airee", "sandeep lamichhane", "football",
        "anfa", "kollywood", "nepali movie", "box office", "actor", "actress", "singer", "concert",
        "literature", "miss nepal", "techpana", "nepal telecom", "ncell", "mount everest",
        "himalayas", "national park", "chitwan", "bardia", "earthquake", "flood", "landslide",
        "weather forecast", "rainfall", "snowfall", "cold wave", "dashain", "tihar", "chhath",
        "heritage"
    ]
    others_regex = [r'\bcan\b', r'\banfa\b', r'\bnpl\b', r'\bt20\b']
    if evaluate_patterns(others_patterns, others_regex, "Nepal – Others", "Culture & Society"):
        secondary_tags.add("Sports & Lifestyle")

    # -------------------------------------------------------------------------
    # Editorial Rule Balancing & Confidence Calculation
    # -------------------------------------------------------------------------
    # If it's a global story without substantive Nepal mentions, promote International News
    if not is_bilateral_nepal:
        if (scores["International News"] > 0 or scores["Nepal – External"] > 0) and \
           scores["India Section"] < 3 and scores["China Section"] < 3 and scores["Bangladesh Section"] < 3 and scores["Pakistan Section"] < 3:
            scores["International News"] += scores["Nepal – External"] + 2
            scores["Nepal – External"] = 0
    elif scores["International News"] >= 3 and not is_bilateral_nepal:
        scores["Nepal – External"] = max(0, scores["Nepal – External"] - 3)

    # Determine primary section
    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_cat, top_score = sorted_cats[0]
    total_score = sum(scores.values())

    if top_score == 0:
        if "indian" in source_str.lower() or "india" in source_str.lower():
            primary = "India Section"
            confidence = 0.65
        else:
            primary = "Nepal – Others"
            confidence = 0.40
        low_confidence = True
    else:
        primary = top_cat
        # Normalised confidence calculation
        ratio = top_score / max(1, total_score)
        confidence = min(0.98, max(0.40, round(ratio * 1.15, 2)))
        low_confidence = (confidence < 0.60) or (top_score < 3)

    # Multi-section associations (Canonical cross-listing)
    sections = [primary]

    # Bilateral Cross-listing: India/China/BD/Pak stories involving Nepal belong to both
    if primary in ("India Section", "China Section", "Bangladesh Section", "Pakistan Section"):
        if is_bilateral_nepal and "Nepal – External" not in sections:
            sections.append("Nepal – External")
    elif primary == "Nepal – External":
        if scores["India Section"] >= 2 and "India Section" not in sections:
            sections.append("India Section")
        if scores["China Section"] >= 2 and "China Section" not in sections:
            sections.append("China Section")
        if scores["Bangladesh Section"] >= 2 and "Bangladesh Section" not in sections:
            sections.append("Bangladesh Section")
        if scores["Pakistan Section"] >= 2 and "Pakistan Section" not in sections:
            sections.append("Pakistan Section")

    # Economic cross-border trade cross-listing
    if primary == "Nepal – Economy":
        if scores["India Section"] >= 2 and "India Section" not in sections:
            sections.append("India Section")
        if scores["China Section"] >= 2 and "China Section" not in sections:
            sections.append("China Section")
        if scores["Bangladesh Section"] >= 2 and "Bangladesh Section" not in sections:
            sections.append("Bangladesh Section")

    return {
        "primary_section": primary,
        "structured_category": primary,  # Backward compatibility
        "sections": sections,
        "secondary_tags": sorted(list(secondary_tags))[:4],
        "confidence": confidence,
        "classification_confidence": confidence,
        "low_confidence": low_confidence
    }

# Date parsing patterns for HTML news cards & metadata
DATE_SNIPPET_REGEXES = [
    re.compile(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}(?:[,\s\|]+(?:at\s+)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?m\.?)?(?:\s*[\+\-]\d{4}|\s*IST)?)?", re.I),
    re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?,?\s+\d{4}(?:[,\s\|]+(?:at\s+)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?m\.?)?(?:\s*[\+\-]\d{4}|\s*IST)?)?", re.I),
    re.compile(r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\s*,\s*\d{4}", re.I),
    re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\b"),
    re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\b")
]
REL_DATE_REGEX = re.compile(r"\b(\d+)\s*(sec|second|min|minute|hour|hr|day|week|month)s?\s*ago\b", re.I)

NEP_DEVANAGARI_DIGITS = str.maketrans('०१२३४५६७८९', '0123456789')
BS_MONTH_NAMES = [
    'बैशाख', 'वैशाख', 'जेठ', 'असार', 'साउन', 'भदौ',
    'असोज', 'आश्विन', 'कार्तिक', 'कात्तिक', 'मंसिर', 'मंसिर',
    'पुस', 'पौष', 'माघ', 'फागुन', 'फाल्गुन', 'चैत', 'चैत्र'
]

# Official Bikram Sambat (BS) calendar month lengths and 1 Baisakh Gregorian (AD) anchors
_BS_YEAR_TABLE: Dict[int, Any] = {
    2078: (datetime.date(2021, 4, 14), (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30)),
    2079: (datetime.date(2022, 4, 14), (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30)),
    2080: (datetime.date(2023, 4, 14), (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30)),
    2081: (datetime.date(2024, 4, 13), (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31)),
    2082: (datetime.date(2025, 4, 14), (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30)),
    2083: (datetime.date(2026, 4, 14), (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30)),
    2084: (datetime.date(2027, 4, 14), (31, 31, 32, 31, 31, 30, 30, 30, 29, 30, 30, 30)),
    2085: (datetime.date(2028, 4, 13), (31, 32, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30)),
}


def _bs_to_ad_date(bs_year: int, bs_month: int, bs_day: int) -> datetime.date:
    """Converts a Bikram Sambat (BS) year, month (1..12), and day (1..32) to an exact Gregorian date."""
    m_clamped = max(1, min(12, int(bs_month)))
    d_clamped = max(1, min(32, int(bs_day)))
    if bs_year in _BS_YEAR_TABLE:
        anchor_ad, month_lengths = _BS_YEAR_TABLE[bs_year]
        max_d = month_lengths[m_clamped - 1]
        offset_days = sum(month_lengths[: m_clamped - 1]) + (min(d_clamped, max_d) - 1)
        return anchor_ad + datetime.timedelta(days=offset_days)
    # Fallback relative to 2083 BS table for out-of-range years
    anchor_2083, lengths_2083 = _BS_YEAR_TABLE[2083]
    year_offset = int(round((bs_year - 2083) * 365.25))
    offset_days = year_offset + sum(lengths_2083[: m_clamped - 1]) + (d_clamped - 1)
    return anchor_2083 + datetime.timedelta(days=offset_days)


def parse_snippet_to_datetime_with_meta(raw_text: str, now_npt: datetime.datetime):
    """
    Extracts a genuine datetime from a short text snippet, relative phrase, or Nepali byline.
    Returns (dt_or_None, is_date_only: bool) where is_date_only=True indicates the snippet lacked
    an explicit intraday time (HH:MM) and should not short-circuit richer article metadata.
    """
    if not raw_text:
        return None, False
    txt = raw_text.strip()

    # 1. Normalize Devanagari numerals to ASCII digits
    norm_txt = txt.translate(NEP_DEVANAGARI_DIGITS)

    # 2. Match Nepali relative date phrases (e.g., २ घण्टा अघि, १५ मिनेट अघि, ३ दिन अघि)
    m_nep_rel = re.search(r'(\d+)\s*(?:घण्टा|घन्टा|hr|hours?)\s*अघि', norm_txt)
    if m_nep_rel:
        return now_npt - datetime.timedelta(hours=int(m_nep_rel.group(1))), False
    m_nep_min = re.search(r'(\d+)\s*(?:मिनेट|min|minutes?)\s*अघि', norm_txt)
    if m_nep_min:
        return now_npt - datetime.timedelta(minutes=int(m_nep_min.group(1))), False
    m_nep_day = re.search(r'(\d+)\s*(?:दिन|days?)\s*अघि', norm_txt)
    if m_nep_day:
        return now_npt - datetime.timedelta(days=int(m_nep_day.group(1))), False
    m_nep_week = re.search(r'(\d+)\s*(?:हप्ता|साता|weeks?)\s*अघि', norm_txt)
    if m_nep_week:
        return now_npt - datetime.timedelta(days=int(m_nep_week.group(1)) * 7), False
    m_nep_month = re.search(r'(\d+)\s*(?:महिना|months?)\s*अघि', norm_txt)
    if m_nep_month:
        return now_npt - datetime.timedelta(days=int(m_nep_month.group(1)) * 30), False
    m_nep_year = re.search(r'(\d+)\s*(?:वर्ष|बर्ष|years?)\s*अघि', norm_txt)
    if m_nep_year:
        return now_npt - datetime.timedelta(days=int(m_nep_year.group(1)) * 365), False
    m_nep_sec = re.search(r'(\d+)\s*(?:सेकेन्ड|सेकेण्ड|sec|seconds?)\s*अघि', norm_txt)
    if m_nep_sec:
        return now_npt - datetime.timedelta(seconds=int(m_nep_sec.group(1))), False
    if re.search(r'\bहिजो\b', norm_txt):
        return now_npt - datetime.timedelta(days=1), True
    if re.search(r'\bअस्ति\b', norm_txt):
        return now_npt - datetime.timedelta(days=2), True

    # 3. Match English relative date phrases
    rel = REL_DATE_REGEX.search(norm_txt)
    if rel:
        v = int(rel.group(1))
        u = rel.group(2).lower()
        if "sec" in u: return now_npt - datetime.timedelta(seconds=v), False
        if "min" in u: return now_npt - datetime.timedelta(minutes=v), False
        if "hr" in u or "hour" in u: return now_npt - datetime.timedelta(hours=v), False
        if "day" in u: return now_npt - datetime.timedelta(days=v), False
        if "week" in u: return now_npt - datetime.timedelta(days=v * 7), False
        if "month" in u: return now_npt - datetime.timedelta(days=v * 30), False

    # 4. Match Nepali Bikram Sambat dates (e.g. कात्तिक २४, २०८३ or ३ मंसिर २०८३)
    bs_month_idx_map = {
        'बैशाख': 1, 'वैशाख': 1, 'जेठ': 2, 'असार': 3, 'साउन': 4, 'श्रावण': 4, 'भदौ': 5, 'भाद्र': 5,
        'असोज': 6, 'आश्विन': 6, 'कार्तिक': 7, 'कात्तिक': 7, 'मंसिर': 8,
        'पुस': 9, 'पुष': 9, 'पौष': 9, 'माघ': 10, 'फागुन': 11, 'फाल्गुन': 11, 'चैत': 12, 'चैत्र': 12
    }
    for m_name, m_idx in bs_month_idx_map.items():
        if m_name in norm_txt:
            m_bs = re.search(rf'(?:{m_name}\s+(\d{{1,2}})|(\d{{1,2}})\s+{m_name},?)(?:,?\s*(20\d{{2}}))?(?:[^\d:]+(\d{{1,2}}):(\d{{2}})(?::(\d{{2}}))?)?', norm_txt)
            if m_bs:
                day_val = int(m_bs.group(1) or m_bs.group(2))
                bs_year = int(m_bs.group(3)) if m_bs.group(3) else 2083
                ad_date = _bs_to_ad_date(bs_year, m_idx, day_val)
                has_explicit_time = bool(m_bs.group(4) and m_bs.group(5))
                if has_explicit_time:
                    hr, mn, sc = int(m_bs.group(4)), int(m_bs.group(5)), int(m_bs.group(6) or 0)
                elif ad_date == now_npt.date():
                    hr, mn, sc = now_npt.hour, now_npt.minute, now_npt.second
                else:
                    hr, mn, sc = 12, 0, 0
                cand_dt = datetime.datetime(ad_date.year, ad_date.month, ad_date.day, hr, mn, sc, tzinfo=NEPAL_TZ)
                return cand_dt, (not has_explicit_time)

    # 5. Clean common formatting artifacts
    clean_txt = re.sub(r"\[IST\]|IST", "+0530", norm_txt)
    clean_txt = re.sub(
        r"Updated(?:\s+On|\s+at)?\s*:\s*|Published(?:\s+Date|\s+On|\s+at)?\s*:\s*|By[^\d]+",
        "",
        clean_txt,
        flags=re.I,
    )
    clean_txt = re.sub(r"^[A-Za-z]+(?=\d{2}\s+[A-Za-z]{3}\s+\d{4})", "", clean_txt)
    clean_txt = re.sub(r"([A-Za-z]{3})\.", r"\1", clean_txt)
    clean_txt = clean_txt.replace("p.m.", "PM").replace("a.m.", "AM").replace("|", " ")

    # 6. Check standard regexes
    for rgx in DATE_SNIPPET_REGEXES:
        m = rgx.search(clean_txt)
        if m:
            try:
                matched_str = m.group(0)
                has_explicit_time = bool(re.search(r"\b\d{1,2}:\d{2}\b", matched_str))
                dt = dt_parser.parse(matched_str, fuzzy=True)
                dt = dt.astimezone(NEPAL_TZ) if dt.tzinfo else dt.replace(tzinfo=NEPAL_TZ)
                if not has_explicit_time:
                    if dt.date() == now_npt.date():
                        dt = dt.replace(hour=now_npt.hour, minute=now_npt.minute, second=now_npt.second, microsecond=0)
                    else:
                        dt = dt.replace(hour=12, minute=0, second=0, microsecond=0)
                return dt, (not has_explicit_time)
            except Exception:
                pass
    return None, False


def parse_snippet_to_datetime(raw_text: str, now_npt: datetime.datetime):
    """Extracts a genuine datetime from a short text snippet, relative phrase, or Nepali byline."""
    dt, _ = parse_snippet_to_datetime_with_meta(raw_text, now_npt)
    return dt


def _extract_intraday_dt_from_article_html(chunk: str, now_npt: datetime.datetime) -> Tuple[Optional[datetime.datetime], bool]:
    """
    Parses article HTML for publication/update timestamps, prioritizing timestamps with
    an explicit intraday time (HH:MM) over date-only strings and ignoring masthead dates.
    Returns (best_dt, is_date_only).
    """
    if not chunk:
        return None, True

    fallback_date_only: Optional[datetime.datetime] = None

    # 1. Check <meta> and JSON-LD datePublished / dateCreated / published_time / dateModified
    meta_candidates: List[str] = []
    for m_meta in re.finditer(
        r"<meta[^>]+(?:article:published_time|article:modified_time|og:updated_time|datePublished|publish-date|published_time)[^>]+content=[\"\x27]([^\x27\"]+)[\"\x27]",
        chunk,
        re.I,
    ):
        meta_candidates.append(m_meta.group(1).strip())
    for m_ld in re.finditer(
        r"\"(?:datePublished|dateCreated|published_time|dateModified)\"\s*:\s*\"([^\"]+)\"",
        chunk,
    ):
        meta_candidates.append(m_ld.group(1).strip())

    for cand in meta_candidates:
        try:
            has_time = bool(re.search(r"(?:T|\s)\d{1,2}:\d{2}", cand))
            dt = dt_parser.parse(cand, fuzzy=True)
            dt = dt.astimezone(NEPAL_TZ) if dt.tzinfo else dt.replace(tzinfo=NEPAL_TZ)
            if has_time:
                return dt, False
            if fallback_date_only is None:
                if dt.date() == now_npt.date():
                    dt = dt.replace(hour=now_npt.hour, minute=now_npt.minute, second=now_npt.second, microsecond=0)
                else:
                    dt = dt.replace(hour=12, minute=0, second=0, microsecond=0)
                fallback_date_only = dt
        except Exception:
            pass

    # 2. Check explicit "Updated at :" / "Published at :" / "Published Date :" labels (e.g. The Kathmandu Post)
    # Prefer Updated at when it carries HH:MM and Published at is date-only
    for pat in (
        r'Updated(?:\s+at|\s+On)?\s*:\s*(?:</?[a-z0-9][^>]*>\s*)*([A-Za-z0-9\s,\.:/\-]{6,50})',
        r'Published(?:\s+at|\s+Date|\s+On)?\s*:\s*(?:</?[a-z0-9][^>]*>\s*)*([A-Za-z0-9\s,\.:/\-]{6,50})',
    ):
        for m_lbl in re.finditer(pat, chunk, re.I):
            dt, is_do = parse_snippet_to_datetime_with_meta(m_lbl.group(1).strip(), now_npt)
            if dt is not None:
                if not is_do:
                    return dt, False
                if fallback_date_only is None:
                    fallback_date_only = dt

    # 3. Check specific article timestamp classes (including updated-time, excluding epaper/blocktop-date)
    for m_cls in re.finditer(
        r'class=["\x27][^"\x27]*(?:news-detail-time-text|published-date|pub-date|article-date|updated-time|post-date|post__meta-date)[^"\x27]*["\x27][^>]*>(?:<[^>]+>)*\s*([^<\r\n]{4,90})',
        chunk,
        re.I,
    ):
        full_match_low = m_cls.group(0).lower()
        if any(bad in full_match_low for bad in ("epaper", "blocktop", "current-date", "masthead")):
            continue
        dt, is_do = parse_snippet_to_datetime_with_meta(m_cls.group(1).strip(), now_npt)
        if dt is not None:
            if not is_do:
                return dt, False
            if fallback_date_only is None:
                fallback_date_only = dt

    # 4. Check <time> tag datetime attribute or inner text
    for m_time in re.finditer(r'<time([^>]*)>(?:<[^>]+>)*\s*([^<]{0,90})\s*</time>', chunk, re.I):
        attrs_str, inner_str = m_time.group(1) or "", (m_time.group(2) or "").strip()
        if "Intl.DateTimeFormat" in inner_str or "blocktop" in attrs_str.lower():
            continue
        m_dt_attr = re.search(r'datetime=["\x27]([^"\x27]+)["\x27]', attrs_str, re.I)
        for t_cand in ([m_dt_attr.group(1)] if m_dt_attr else []) + ([inner_str] if inner_str else []):
            dt, is_do = parse_snippet_to_datetime_with_meta(t_cand, now_npt)
            if dt is not None:
                if not is_do:
                    return dt, False
                if fallback_date_only is None:
                    fallback_date_only = dt

    # 5. Strip masthead blocktop-date elements and scan chunk[:25000] only for snippets with explicit HH:MM
    clean_chunk = re.sub(r'<div[^>]+blocktop-date[^>]*>.*?</div>', ' ', chunk[:25000], flags=re.I | re.S)
    for rgx in DATE_SNIPPET_REGEXES:
        for m_chunk in rgx.finditer(clean_chunk):
            dt, is_do = parse_snippet_to_datetime_with_meta(m_chunk.group(0), now_npt)
            if dt is not None:
                if not is_do:
                    return dt, False
                if fallback_date_only is None:
                    fallback_date_only = dt

    return fallback_date_only, True


def extract_date_from_card_or_url(a_tag, href: str, now_npt: datetime.datetime, allow_http_fetch: bool = True):
    """
    Extracts real publication datetime for an HTML article card or RSS item link:
    1. Memory cache check.
    2. Parent DOM container inspection (only short-circuits when an explicit intraday time HH:MM is present).
    3. URL path pattern extraction (/YYYY/MM/DD/ or -YYYY-MM-DD-) as date-only fallback.
    4. Article page metadata retrieval (JSON-LD datePublished, <meta>, Updated at : / Published at :)
       prioritized over date-only card/URL guesses for recent articles.
    """
    if not href:
        return None
    if href in ARTICLE_DATE_CACHE:
        return ARTICLE_DATE_CACHE[href]

    fallback_date_only: Optional[datetime.datetime] = None

    # 1. Inspect DOM ancestors
    curr = a_tag.parent if a_tag else None
    for _ in range(6):
        if not curr or curr.name in ["body", "html", "header", "nav"]:
            break
        curr_classes = " ".join(curr.get("class") or []).lower()
        if any(bad in curr_classes for bad in ["navbar", "search-overlay", "header", "masthead", "topbar", "footer", "blocktop"]):
            break
        time_tag = curr.find("time")
        if time_tag:
            dt, is_do = parse_snippet_to_datetime_with_meta(
                time_tag.get("datetime") or time_tag.get_text(strip=True), now_npt
            )
            if dt:
                if not is_do:
                    ARTICLE_DATE_CACHE[href] = dt
                    return dt
                if fallback_date_only is None:
                    fallback_date_only = dt

        date_elems = curr.find_all(class_=re.compile(r"date|time|meta|updated|publish|oi-article-country|byline", re.I))
        for de in date_elems:
            de_cls = " ".join(de.get("class") or []).lower()
            if any(bad in de_cls for bad in ["navbar", "header", "epaper", "current-date", "today", "blocktop"]):
                continue
            dt, is_do = parse_snippet_to_datetime_with_meta(de.get_text(" ", strip=True), now_npt)
            if dt:
                if not is_do:
                    ARTICLE_DATE_CACHE[href] = dt
                    return dt
                if fallback_date_only is None:
                    fallback_date_only = dt

        for el in curr.find_all(["p", "span", "small"]):
            el_cls = " ".join(el.get("class") or []).lower()
            if any(bad in el_cls for bad in ["navbar", "header", "epaper", "current-date", "blocktop"]):
                continue
            t = el.get_text(" ", strip=True)
            if t and len(t) < 80:
                dt, is_do = parse_snippet_to_datetime_with_meta(t, now_npt)
                if dt:
                    if not is_do:
                        ARTICLE_DATE_CACHE[href] = dt
                        return dt
                    if fallback_date_only is None:
                        fallback_date_only = dt

        curr = curr.parent

    # 2a. Check full 6-part intraday URL timestamp slugs (e.g. nepalkhabar.com/.../291968-2026-11-19-11-2-58)
    m_url_ts = re.search(
        r"-(202[0-9])-(0?[1-9]|1[0-2])-(0?[1-9]|[12][0-9]|3[01])-(2[0-3]|[01]?\d)-([0-5]?\d)-([0-5]?\d)(?:$|[/?#])",
        href,
    )
    if m_url_ts:
        try:
            u_year, u_month, u_day = int(m_url_ts.group(1)), int(m_url_ts.group(2)), int(m_url_ts.group(3))
            u_hour, u_min, u_sec = int(m_url_ts.group(4)), int(m_url_ts.group(5)), int(m_url_ts.group(6))
            naive_dt = datetime.datetime(u_year, u_month, u_day, u_hour, u_min, u_sec)
            # NepalKhabar RSS embeds UTC timestamps in URL slugs while homepage/social links may use NPT
            if "nepalkhabar.com" in href.lower():
                cand_utc_as_npt = naive_dt.replace(tzinfo=datetime.timezone.utc).astimezone(NEPAL_TZ)
                if cand_utc_as_npt <= now_npt + datetime.timedelta(minutes=5):
                    exact_url_dt = cand_utc_as_npt
                else:
                    exact_url_dt = naive_dt.replace(tzinfo=NEPAL_TZ)
            else:
                exact_url_dt = naive_dt.replace(tzinfo=NEPAL_TZ)
            if exact_url_dt <= now_npt + datetime.timedelta(minutes=5):
                ARTICLE_DATE_CACHE[href] = exact_url_dt
                return exact_url_dt
        except Exception:
            pass

    # 2b. Check URL date patterns (/YYYY/MM/DD/ or -YYYY-MM-DD-) as date_only fallback
    m_url = re.search(r"/(202[0-9])[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])", href)
    if not m_url:
        m_url = re.search(r"-(202[0-9])-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])", href)
    if m_url:
        try:
            u_year, u_month, u_day = int(m_url.group(1)), int(m_url.group(2)), int(m_url.group(3))
            u_date = datetime.date(u_year, u_month, u_day)
            if u_date == now_npt.date():
                u_dt = datetime.datetime(u_year, u_month, u_day, now_npt.hour, now_npt.minute, now_npt.second, tzinfo=NEPAL_TZ)
            else:
                u_dt = datetime.datetime(u_year, u_month, u_day, 12, 0, 0, tzinfo=NEPAL_TZ)
            # For archive URLs older than 2 days, skip live HTTP check and return date-only noon
            if (now_npt.date() - u_date).days > 2:
                ARTICLE_DATE_CACHE[href] = u_dt
                return u_dt
            if fallback_date_only is None or u_date == now_npt.date():
                fallback_date_only = u_dt
        except Exception:
            pass

    # 3. Fetch article page metadata to resolve exact intraday HH:MM before falling back to date_only
    if allow_http_fetch and href.startswith("http") and not _is_direct_scrape_skipped(href):
        try:
            req = urllib.request.Request(href, headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=2.5) as resp:
                chunk = resp.read(120000).decode("utf-8", errors="ignore")
            page_dt, page_is_do = _extract_intraday_dt_from_article_html(chunk, now_npt)
            if page_dt is not None and not page_is_do:
                ARTICLE_DATE_CACHE[href] = page_dt
                return page_dt
            if page_dt is not None and fallback_date_only is None:
                fallback_date_only = page_dt
        except Exception:
            pass

    if fallback_date_only is not None:
        # Only cache date-only fallback permanently if it's from a past day; allow today's date-only to upgrade later
        if fallback_date_only.date() < now_npt.date():
            ARTICLE_DATE_CACHE[href] = fallback_date_only
        return fallback_date_only

    return None

# parse_to_nepal_time is imported from nepal_config above for single source of truth.


def resolve_tco_url(url: str, timeout: float = 4.0, allow_redirects: bool = False) -> str:
    """
    Resolves a https://t.co/... shortlink to its real destination URL using a lightweight
    HEAD (or GET fallback) request with allow_redirects=False so destination sites are never probed.
    """
    clean_u = (url or "").strip()
    if not clean_u:
        return ""
    if clean_u in TCO_REDIRECT_CACHE:
        return TCO_REDIRECT_CACHE[clean_u]
    try:
        parsed = urllib.parse.urlparse(clean_u)
        if parsed.netloc.lower() not in ("t.co", "www.t.co"):
            return clean_u
    except Exception:
        return clean_u

    resolved = clean_u
    headers = {"User-Agent": "curl/8.7.1", "Accept": "*/*"}
    try:
        resp = requests.head(clean_u, headers=headers, allow_redirects=allow_redirects, timeout=timeout)
        loc = (resp.headers.get("Location") or resp.headers.get("location") or "").strip()
        if loc.startswith("http"):
            resolved = loc
        else:
            resp_get = requests.get(clean_u, headers=headers, allow_redirects=allow_redirects, timeout=timeout)
            loc2 = (resp_get.headers.get("Location") or resp_get.headers.get("location") or "").strip()
            if loc2.startswith("http"):
                resolved = loc2
            elif resp_get.text:
                m_meta = re.search(
                    r'http-equiv=["\']?refresh["\']?[^>]*content=["\'][^"\']*URL=([^"\'>\s]+)',
                    resp_get.text,
                    re.IGNORECASE,
                )
                m_js = re.search(r'location\.replace\(["\']([^"\']+)["\']\)', resp_get.text)
                cand = (m_meta.group(1) if m_meta else (m_js.group(1) if m_js else "")).strip()
                if cand.startswith("http"):
                    resolved = html.unescape(cand)
    except Exception:
        pass

    if resolved and resolved != clean_u:
        TCO_REDIRECT_CACHE[clean_u] = resolved
    return resolved


def _clean_x_bridge_text(raw_text: str) -> str:
    """Strips URLs, t.co shortlinks, #hashtags, @mentions, and trailing portal suffixes from X text."""
    if not raw_text:
        return ""
    txt = html.unescape(str(raw_text)).replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    # Strip embedded URLs even when glued immediately after Devanagari punctuation (e.g. छ।https://t.co/...)
    txt = re.sub(r"https?://\S+", " ", txt)
    txt = re.sub(r"\bt\.co/\S+", " ", txt, flags=re.IGNORECASE)
    # Strip hashtags (ASCII and Devanagari/Unicode) and @mentions
    txt = re.sub(r"(?<!\S)#[^\s#]+", " ", txt)
    txt = re.sub(r"(?<!\S)@[A-Za-z0-9_]+", " ", txt)
    # Strip trailing source branding often appended to tweets and card titles
    txt = re.sub(
        r"\s*[\|\-–—]\s*(?:Annapurna\s*Post|अन्नपूर्ण\s*पोस्ट|Naya\s*Patrika(?:\s*News|\s*Daily)?(?:\.\.\.|…)?|नयाँ\s*पत्रिका(?:\s*दैनिक)?|TechPana|टेकपाना|The\s*Himalayan\s*Times|THT)\s*$",
        "",
        txt,
        flags=re.IGNORECASE,
    )
    # Normalize spaces per line and collapse blank lines
    clean_lines = []
    for line in txt.split("\n"):
        norm = re.sub(r"[ \t]+", " ", line).strip()
        norm = re.sub(r"\s+([।.,!?;:])", r"\1", norm)
        if norm:
            clean_lines.append(norm)
    return "\n".join(clean_lines).strip()


def _clean_x_card_description(raw_desc: str) -> str:
    """Normalizes a Twitter syndication card description and cleanly trims mid-word cutoffs."""
    cleaned = _clean_x_bridge_text(raw_desc)
    if not cleaned:
        return ""
    cleaned = re.sub(r"\s*:\s*", " : ", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
    if not cleaned:
        return ""

    # Twitter syndication card descriptions are often truncated around ~60-75 chars mid-word.
    if cleaned[-1] not in ("।", ".", "!", "?", "…"):
        last_sent = max(cleaned.rfind("।"), cleaned.rfind(". "))
        if last_sent >= 25:
            cleaned = cleaned[: last_sent + 1].strip()
        elif len(cleaned) >= 45 and " " in cleaned:
            trimmed = cleaned.rsplit(" ", 1)[0].rstrip(" ,;:-–—")
            if len(trimmed) >= 25:
                cleaned = f"{trimmed}…"
    return cleaned


def _extract_x_bridge_article_url(
    raw_text: str,
    expanded_urls: Optional[List[str]] = None,
    x_handle: str = "Annapurna_Post",
    tweet_id: str = "",
    preferred_domain: str = "annapurnapost.com",
) -> str:
    """
    Resolves the canonical publisher article URL from syndication expanded_urls or t.co links
    without ever probing the destination domain. Falls back to the X permalink only when
    no external article link exists.
    """
    candidates: List[str] = []
    for u in (expanded_urls or []):
        if isinstance(u, str) and u.strip().startswith("http"):
            candidates.append(u.strip())
    for m_u in re.findall(r"https?://[^\s<>\"']+", raw_text or ""):
        clean_m = m_u.rstrip(").,;।")
        if clean_m and clean_m not in candidates:
            candidates.append(clean_m)

    resolved_urls: List[str] = []
    for cand in candidates:
        host = urllib.parse.urlparse(cand).netloc.lower()
        target = resolve_tco_url(cand) if host in ("t.co", "www.t.co") else cand
        if not target or not target.startswith("http"):
            continue
        t_host = urllib.parse.urlparse(target).netloc.lower().split(":")[0]
        if t_host in (
            "t.co",
            "www.t.co",
            "pic.twitter.com",
            "pbs.twimg.com",
            "video.twimg.com",
            "x.com",
            "www.x.com",
            "twitter.com",
            "www.twitter.com",
        ):
            continue
        if target not in resolved_urls:
            resolved_urls.append(target)

    if preferred_domain:
        for ru in resolved_urls:
            if preferred_domain.lower() in urllib.parse.urlparse(ru).netloc.lower():
                return ru
    if resolved_urls:
        return resolved_urls[0]
    if tweet_id:
        clean_h = (x_handle or "Annapurna_Post").lstrip("@").strip()
        return f"https://x.com/{clean_h}/status/{tweet_id}"
    return ""


def build_x_bridged_article(
    portal: Dict[str, Any],
    tweet_id: str,
    raw_text: str,
    published_dt_raw: Any,
    now_npt: datetime.datetime,
    expanded_urls: Optional[List[str]] = None,
    card_title: str = "",
    card_description: str = "",
    x_handle: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Normalizes an official media X post into the exact standard Nepali Media article schema
    with resolved publisher URL, editorial classification, topic tags, and Reader-safe body text.
    """
    handle = (x_handle or portal.get("x_handle") or portal.get("x_boost_handle") or "").lstrip("@").strip()
    preferred_domain = (portal.get("target_domain") or "").strip().lower()
    if not preferred_domain:
        pname_low = portal.get("name", "").lower()
        if "annapurna" in pname_low:
            preferred_domain = "annapurnapost.com"
        elif "naya patrika" in pname_low:
            preferred_domain = "nayapatrikadaily.com"
        elif "techpana" in pname_low:
            preferred_domain = "techpana.com"
        elif portal.get("url"):
            try:
                preferred_domain = urllib.parse.urlparse(portal["url"]).netloc.lower().split(":")[0].replace("www.", "")
            except Exception:
                pass

    clean_tweet = _clean_x_bridge_text(raw_text)
    clean_card_title = _clean_x_bridge_text(card_title)
    clean_card_desc = _clean_x_card_description(card_description)

    if len(clean_card_title) >= 12:
        title = clean_card_title
    elif clean_tweet:
        first_line = clean_tweet.split("\n", 1)[0].strip()
        # If first line is a multi-sentence paragraph (e.g. TechPana tweets without card titles), split first sentence as headline
        if len(first_line) > 85:
            m_sent = re.search(r"^(.{20,140}?[।.!?])(?:\s|$)", first_line)
            if m_sent:
                title = m_sent.group(1).strip()
            elif len(first_line) > 140:
                title = first_line[:140].rsplit(" ", 1)[0].strip()
            else:
                title = first_line
        else:
            title = first_line
    else:
        return None

    title = title.strip()
    if len(title) < 10:
        return None

    article_url = _extract_x_bridge_article_url(
        raw_text=raw_text,
        expanded_urls=expanded_urls,
        x_handle=handle,
        tweet_id=str(tweet_id),
        preferred_domain=preferred_domain,
    )
    if not article_url:
        return None

    norm_link = normalize_canonical_url(article_url)
    pub_dt, rel_time, exact_time = parse_to_nepal_time(published_dt_raw, now_npt)

    # Build clean distinct summary and full_content so card preview and Read modal both work identically
    body_paras: List[str] = []
    norm_title_cmp = " ".join(title.lower().split())
    norm_tweet_cmp = " ".join(clean_tweet.lower().split())
    if clean_tweet and norm_tweet_cmp != norm_title_cmp:
        # Remove exact leading title prefix when tweet repeats headline + extra commentary
        remainder = clean_tweet
        if remainder.startswith(title):
            remainder = remainder[len(title):].lstrip(" \n,:;-–—|।.")
        chosen_tweet_body = remainder if len(remainder) >= 20 else clean_tweet
        if chosen_tweet_body and " ".join(chosen_tweet_body.lower().split()) != norm_title_cmp:
            body_paras.append(chosen_tweet_body)

    if clean_card_desc and " ".join(clean_card_desc.lower().split()) != norm_title_cmp:
        # Avoid duplicating card description when tweet body already contains the same opening sentence
        desc_probe = re.sub(r"^[^:]{2,25}:\s*", "", clean_card_desc)[:30].strip()
        already_covered = any(desc_probe and desc_probe in p for p in body_paras)
        if not already_covered:
            body_paras.append(clean_card_desc)

    if body_paras:
        summary = body_paras[0]
        full_content = "\n\n".join(body_paras)
    else:
        summary = title
        if portal.get("lang", "Nepali") == "Nepali":
            full_content = f"{title}\n\n{portal['name']} बाट प्रकाशित ताजा समाचार अपडेट।"
        else:
            full_content = f"{title}\n\nLatest news update published by {portal['name']}."

    cls_res = classify_article_editorial(title, summary, portal["name"], full_content)
    classified_cat = cls_res["primary_section"]
    headline_en = title if portal.get("lang") == "English" else ""
    canonical_id = generate_canonical_id(portal["name"], norm_link, title)

    return {
        "canonical_id": canonical_id,
        "source": portal["name"],
        "language": portal.get("lang", "Nepali"),
        "portal_category": portal.get("category", "National Daily"),
        "structured_category": classified_cat,
        "primary_section": classified_cat,
        "sections": cls_res["sections"],
        "secondary_tags": cls_res["secondary_tags"],
        "classification_confidence": cls_res["confidence"],
        "low_confidence": cls_res["low_confidence"],
        "category_icon": CATEGORY_ICONS.get(classified_cat, "📌"),
        "title": title,
        "headline_english": headline_en,
        "link": article_url,
        "canonical_url": norm_link,
        "summary": summary,
        "full_content": full_content,
        "published_dt": pub_dt,
        "relative_time": rel_time,
        "exact_time": exact_time,
        "is_viral": False,
    }


def fetch_x_bridged_portal_articles(
    portal: Dict[str, Any],
    now_npt: datetime.datetime,
    max_entries: int = 50,
    seed_x_posts: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Discovers recent posts for a media portal's official X account (combining live profile
    discovery, recent Supabase x_posts rows, and optional seed posts from X ingestion),
    resolves real publisher article URLs via Twitter syndication metadata or t.co HEAD redirects,
    and returns fully classified Nepali Media article records.
    """
    from nepal_x_scanner import (
        ACCOUNT_BY_HANDLE,
        _decode_snowflake_dt,
        _discover_profile_tweet_candidates,
        _enrich_tweet_by_id,
        _get_x_http_session,
    )
    from nepal_news_store import esc_sql, query_supabase, save_x_posts

    x_handle = (portal.get("x_handle") or "").lstrip("@").strip()
    if not x_handle:
        return []
    handle_low = x_handle.lower()
    acc = ACCOUNT_BY_HANDLE.get(handle_low) or {
        "handle": x_handle,
        "name": portal["name"],
        "type": "Major Media & Broadcast Journalists",
        "role": portal.get("category", "National Daily"),
        "avatar_bg": "#b91c1c",
        "initials": portal["name"][:2].upper(),
    }

    # 1. Gather candidate tweet metadata from seed posts, Supabase x_posts (past 14 days), and live profile
    stored_by_sid: Dict[str, Dict[str, Any]] = {}
    has_recent_seed_for_handle = False
    for sp in (seed_x_posts or []):
        sp_h = (sp.get("raw_handle") or sp.get("handle") or "").lstrip("@").strip().lower()
        sp_id = str(sp.get("id") or "").strip()
        if sp_id and sp_h == handle_low:
            stored_by_sid[sp_id] = sp
            has_recent_seed_for_handle = True

    newest_synced_utc: Optional[datetime.datetime] = None
    try:
        db_rows = query_supabase(
            "SELECT id, raw_handle, text, title, link, published_dt, updated_at "
            f"FROM x_posts WHERE LOWER(raw_handle) = {esc_sql(handle_low)} "
            "AND published_dt >= NOW() - INTERVAL '14 days' "
            f"ORDER BY published_dt DESC LIMIT {min(max(int(max_entries), 20), 60)};"
        )
        for r in (db_rows or []):
            sid = str(r.get("id") or "").strip()
            if sid and sid not in stored_by_sid:
                stored_by_sid[sid] = r
            upd = r.get("updated_at")
            upd_utc: Optional[datetime.datetime] = None
            if isinstance(upd, datetime.datetime):
                upd_utc = upd.astimezone(datetime.timezone.utc) if upd.tzinfo else upd.replace(tzinfo=datetime.timezone.utc)
            elif isinstance(upd, str) and upd.strip():
                try:
                    upd_dt = dt_parser.parse(upd)
                    upd_utc = upd_dt.astimezone(datetime.timezone.utc) if upd_dt.tzinfo else upd_dt.replace(tzinfo=datetime.timezone.utc)
                except Exception:
                    upd_utc = None
            if upd_utc is not None and (newest_synced_utc is None or upd_utc > newest_synced_utc):
                newest_synced_utc = upd_utc
    except Exception:
        pass

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    synced_within_5m = bool(
        has_recent_seed_for_handle
        or (newest_synced_utc is not None and (now_utc - newest_synced_utc).total_seconds() < 300.0)
    )

    live_sids: List[str] = []
    if not synced_within_5m:
        try:
            profile_cands = _discover_profile_tweet_candidates([acc], timeout_secs=8.0) or {}
            for sid, cand_acc in profile_cands.items():
                cand_h = (cand_acc.get("handle") or "").lstrip("@").strip().lower() if isinstance(cand_acc, dict) else handle_low
                if cand_h == handle_low:
                    live_sids.append(str(sid).strip())
        except Exception:
            pass

    all_sids = sorted(
        {s for s in list(stored_by_sid.keys()) + live_sids if s and s.isdigit()},
        key=int,
        reverse=True,
    )[:max_entries]
    if not all_sids:
        return []

    # 2. Fetch Twitter syndication payloads in parallel to get exact expanded_url + card title/description
    def _fetch_syndication_payload(sid: str):
        try:
            sess = _get_x_http_session()
            r = sess.get(
                f"https://cdn.syndication.twimg.com/tweet-result?id={sid}&token=4",
                verify=False,
                timeout=(2.5, 4.5),
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and data.get("text"):
                    return sid, data
        except Exception:
            pass
        return sid, None

    synd_map: Dict[str, Dict[str, Any]] = {}
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(all_sids)))
    try:
        futs = [pool.submit(_fetch_syndication_payload, sid) for sid in all_sids]
        for fut in concurrent.futures.as_completed(futs, timeout=14.0):
            try:
                sid, payload = fut.result(timeout=1.0)
                if payload:
                    synd_map[sid] = payload
            except Exception:
                pass
    except concurrent.futures.TimeoutError:
        pass
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    # Opportunistically persist any brand-new live tweets into x_posts so X feed & Media feed stay aligned
    new_live_sids = [sid for sid in live_sids if sid not in stored_by_sid and sid in synd_map]
    if new_live_sids:
        try:
            x_rows_to_save = []
            for sid in new_live_sids[:12]:
                xp = _enrich_tweet_by_id(sid, known_handle=x_handle, known_account=acc)
                if xp:
                    x_rows_to_save.append(xp)
            if x_rows_to_save:
                save_x_posts(x_rows_to_save, batch_size=50)
        except Exception:
            pass

    # 3. Normalize each tweet into the standard Nepali Media article schema
    bridged_articles: List[Dict[str, Any]] = []
    seen_urls = set()
    for sid in all_sids:
        payload = synd_map.get(sid)
        stored = stored_by_sid.get(sid)

        raw_text = ""
        expanded_urls: List[str] = []
        card_title = ""
        card_desc = ""
        pub_raw: Any = None

        if payload:
            # Verify tweet author matches expected media handle
            p_user = (payload.get("user") or {}).get("screen_name", "")
            if p_user and p_user.lower() != handle_low:
                continue
            raw_text = str(payload.get("text") or "").strip()
            note = payload.get("note_tweet")
            if isinstance(note, dict):
                long_txt = (
                    note.get("note_tweet_results", {}).get("result", {}).get("text")
                    or note.get("text")
                )
                if long_txt and len(long_txt) > len(raw_text):
                    raw_text = str(long_txt).strip()
            entities = payload.get("entities") if isinstance(payload.get("entities"), dict) else {}
            for u_obj in (entities.get("urls") or []):
                if isinstance(u_obj, dict):
                    eu = (u_obj.get("expanded_url") or u_obj.get("url") or "").strip()
                    if eu:
                        expanded_urls.append(eu)
            card = payload.get("card") if isinstance(payload.get("card"), dict) else {}
            bv = card.get("binding_values") if isinstance(card.get("binding_values"), dict) else {}
            card_title = str((bv.get("title") or {}).get("string_value") or "").strip()
            card_desc = str((bv.get("description") or {}).get("string_value") or "").strip()
            card_url = str((bv.get("card_url") or {}).get("string_value") or "").strip()
            if card_url and card_url not in expanded_urls:
                expanded_urls.append(card_url)
            pub_raw = payload.get("created_at") or _decode_snowflake_dt(sid)
        elif stored:
            raw_text = str(stored.get("text") or stored.get("title") or "").strip()
            pub_raw = stored.get("published_dt") or _decode_snowflake_dt(sid)
        else:
            continue

        # Skip pure replies to other users
        if raw_text.startswith("@"):
            continue

        art = build_x_bridged_article(
            portal=portal,
            tweet_id=sid,
            raw_text=raw_text,
            published_dt_raw=pub_raw,
            now_npt=now_npt,
            expanded_urls=expanded_urls,
            card_title=card_title,
            card_description=card_desc,
            x_handle=x_handle,
        )
        if not art:
            continue
        c_url = art["canonical_url"]
        if c_url in seen_urls:
            continue
        seen_urls.add(c_url)
        bridged_articles.append(art)

    return bridged_articles


_NON_ARTICLE_EXACT_PATHS = {
    "", "/npl", "/airquality", "/calendar", "/follow", "/here-now", "/opinion",
    "/editorial", "/multimedia", "/archive", "/about", "/contact", "/advertise",
    "/weather", "/forex", "/horoscope", "/rashifal", "/epaper", "/unicode",
    "/date-converter", "/login", "/register", "/search", "/news", "/national",
    "/business", "/politics", "/world", "/sports", "/valley", "/money", "/feature",
    "/art-culture", "/columns", "/cricket", "/health", "/lifestyle", "/literature",
    "/video", "/videos", "/photo", "/photos", "/live", "/latest", "/trending",
}

_X_BOOST_SOCIAL_HOSTS = frozenset({
    "t.co", "www.t.co", "pic.twitter.com", "pbs.twimg.com", "video.twimg.com",
    "x.com", "www.x.com", "twitter.com", "www.twitter.com",
    "facebook.com", "www.facebook.com", "fb.watch", "youtu.be", "youtube.com",
    "www.youtube.com", "instagram.com", "www.instagram.com", "tiktok.com", "www.tiktok.com",
})


def _extract_url_path_date(url: str) -> Optional[datetime.date]:
    """Extracts a calendar date from URL path segments (e.g. /YYYY/MM/DD/ or /YYYY-MM-DD)."""
    if not url:
        return None
    try:
        path = urllib.parse.urlparse(url).path or ""
    except Exception:
        path = str(url)
    m_ymd = re.search(r"/(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])(?:/|-|\.|_|$)", path)
    if not m_ymd:
        m_ymd = re.search(r"-(20\d{2})-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])(?:-|\.|/|$)", path)
    if m_ymd:
        try:
            return datetime.date(int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3)))
        except ValueError:
            return None
    m_ym = re.search(r"/(20\d{2})/(0?[1-9]|1[0-2])(?:/|$)", path)
    if m_ym:
        try:
            import calendar
            y, m = int(m_ym.group(1)), int(m_ym.group(2))
            return datetime.date(y, m, calendar.monthrange(y, m)[1])
        except ValueError:
            return None
    return None


def _is_x_boost_article_url_valid(
    url: str,
    portal: Dict[str, Any],
    now_npt: datetime.datetime,
    max_path_age_hours: float = 24.0,
) -> bool:
    """
    Validates that an X-boost candidate URL belongs to the target portal's domain,
    looks like an actual article URL (not a homepage/category/social link), and does
    not carry a URL path date older than max_path_age_hours.
    """
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    host = parsed.netloc.lower().split(":")[0]
    if not host or host in _X_BOOST_SOCIAL_HOSTS:
        return False

    portal_domain = (portal.get("target_domain") or "").strip().lower()
    if not portal_domain:
        portal_domain = urllib.parse.urlparse(portal.get("url", "")).netloc.lower().split(":")[0]
    if portal_domain.startswith("www."):
        portal_domain = portal_domain[4:]
    if not portal_domain:
        return False

    if host != portal_domain and not host.endswith("." + portal_domain):
        return False
    # Prevent Nepali-edition X-boost handles from ingesting separate English-subdomain portals
    if portal.get("lang") == "Nepali" and (host.startswith("en.") or host.startswith("english.")):
        return False

    path = (parsed.path or "").strip()
    path_low = path.rstrip("/").lower()
    if path_low in _NON_ARTICLE_EXACT_PATHS:
        return False
    if any(seg in path_low for seg in ("/author/", "/tag/", "/tags/", "/category/", "/topic/", "/page/", "/morearticles/", "/epaper")):
        return False

    segs = [s for s in path.split("/") if s]
    if not segs:
        return False
    last_seg = segs[-1]
    looks_like_article = bool(
        re.search(r"\.(?:html?|ece|aspx|php)$", last_seg, re.I)
        or re.search(r"\d{3,}", path)
        or "/story/" in path_low
        or "/news/" in path_low
        or (len(segs) >= 2 and (len(last_seg) >= 8 or "-" in last_seg))
    )
    if not looks_like_article:
        return False

    path_date = _extract_url_path_date(url)
    if path_date is not None:
        end_of_url_day = datetime.datetime.combine(path_date, datetime.time(23, 59, 59), tzinfo=NEPAL_TZ)
        if (now_npt - end_of_url_day).total_seconds() > (max_path_age_hours * 3600.0):
            return False

    return True


def _resolve_x_boost_article_url(
    raw_text: str,
    expanded_urls: Optional[List[str]],
    portal: Dict[str, Any],
    now_npt: datetime.datetime,
) -> str:
    """Resolves t.co shortlinks via resolve_tco_url(..., allow_redirects=False) and validates article URL."""
    candidates: List[str] = []
    for u in (expanded_urls or []):
        if isinstance(u, str) and u.strip().startswith("http"):
            candidates.append(u.strip())
    for m_u in re.findall(r"https?://[^\s<>\"']+", raw_text or ""):
        clean_m = m_u.rstrip(").,;।")
        if clean_m and clean_m not in candidates:
            candidates.append(clean_m)

    for cand in candidates:
        host = urllib.parse.urlparse(cand).netloc.lower().split(":")[0]
        target = resolve_tco_url(cand, allow_redirects=False) if host in ("t.co", "www.t.co") else cand
        if _is_x_boost_article_url_valid(target, portal, now_npt):
            return target
    return ""


def boost_x_portals_to_articles(
    x_posts: Optional[List[Dict[str, Any]]] = None,
    now_npt: Optional[datetime.datetime] = None,
) -> int:
    """
    Dual-Feed X-Boost layer for high-velocity RSS/HTML portals configured with 'x_boost_handle'.
    Resolves t.co links without extra site probing, skips non-article and >24h path-date links,
    skips URLs already stored in Supabase articles, classifies via classify_article_editorial(),
    and upserts new breaking stories so RSS/HTML can upgrade them in place on the next scrape.
    """
    from nepal_news_store import esc_sql, query_supabase

    ref_npt = now_npt or datetime.datetime.now(NEPAL_TZ)
    boost_portals_by_handle: Dict[str, Dict[str, Any]] = {}
    for portal in TOP_NEPAL_NEWS_PORTALS:
        if portal.get("type") == "x_bridge":
            continue
        bh = (portal.get("x_boost_handle") or "").lstrip("@").strip().lower()
        if bh:
            boost_portals_by_handle[bh] = portal

    if not boost_portals_by_handle:
        return 0

    source_posts = list(x_posts) if x_posts is not None else []
    if x_posts is None:
        try:
            in_handles = ", ".join(esc_sql(h) for h in sorted(boost_portals_by_handle.keys()))
            source_posts = query_supabase(
                "SELECT id, raw_handle, handle, text, title, link, published_dt "
                f"FROM x_posts WHERE LOWER(raw_handle) IN ({in_handles}) "
                "AND published_dt >= NOW() - INTERVAL '24 hours' "
                "ORDER BY published_dt DESC LIMIT 180;"
            ) or []
        except Exception:
            source_posts = []

    if not source_posts:
        return 0

    candidates_by_portal: Dict[str, List[Dict[str, Any]]] = {}
    candidate_norm_urls: List[str] = []
    seen_norm_urls = set()

    for post in source_posts:
        raw_h = (post.get("raw_handle") or post.get("handle") or "").lstrip("@").strip().lower()
        portal = boost_portals_by_handle.get(raw_h)
        if not portal:
            continue

        raw_text = str(post.get("text") or post.get("title") or "").strip()
        if not raw_text or raw_text.startswith("@"):
            continue

        pub_raw = post.get("published_dt")
        pub_dt, _, _ = parse_to_nepal_time(pub_raw, ref_npt)
        if (ref_npt - pub_dt).total_seconds() > 86400.0:
            continue

        article_url = _resolve_x_boost_article_url(
            raw_text=raw_text,
            expanded_urls=post.get("expanded_urls"),
            portal=portal,
            now_npt=ref_npt,
        )
        if not article_url:
            continue

        norm_u = normalize_canonical_url(article_url)
        if not norm_u or norm_u in seen_norm_urls:
            continue

        art = build_x_bridged_article(
            portal=portal,
            tweet_id=str(post.get("id") or ""),
            raw_text=raw_text,
            published_dt_raw=pub_dt,
            now_npt=ref_npt,
            expanded_urls=[article_url],
            card_title=str(post.get("card_title") or ""),
            card_description=str(post.get("card_description") or ""),
            x_handle=portal.get("x_boost_handle"),
        )
        if not art:
            continue

        art["link"] = article_url
        art["canonical_url"] = norm_u
        seen_norm_urls.add(norm_u)
        candidate_norm_urls.append(norm_u)
        candidates_by_portal.setdefault(portal["name"], []).append(art)

    if not candidate_norm_urls:
        return 0

    existing_urls = get_existing_article_urls(candidate_norm_urls)
    total_boosted = 0
    for portal_name, portal_arts in candidates_by_portal.items():
        fresh_arts = [a for a in portal_arts if a.get("canonical_url") not in existing_urls]
        if not fresh_arts:
            continue
        try:
            batch_fetch_full_content(fresh_arts, max_workers=8, summarize_english=False)
        except Exception:
            pass
        for a in fresh_arts:
            cls_res = classify_article_editorial(
                a.get("title", ""),
                a.get("summary", ""),
                portal_name,
                a.get("full_content", ""),
            )
            cat = cls_res["primary_section"]
            a["structured_category"] = cat
            a["primary_section"] = cat
            a["sections"] = cls_res["sections"]
            a["secondary_tags"] = cls_res["secondary_tags"]
            a["classification_confidence"] = cls_res["confidence"]
            a["low_confidence"] = cls_res["low_confidence"]
            a["category_icon"] = CATEGORY_ICONS.get(cat, "📌")
        res = batch_upsert_articles(fresh_arts, portal_name, is_x_boost=True)
        total_boosted += int(res.get("ingested", 0) or 0)

    return total_boosted


def bridge_x_portals_to_articles(x_posts: Optional[List[Dict[str, Any]]] = None) -> int:
    """
    Triggers X-to-Nepali-Media bridging for all configured x_bridge portals (e.g. Annapurna Post)
    and X-Boost breaking discovery for x_boost_handle portals right after X ingestion runs.
    """
    import time
    now_npt = datetime.datetime.now(NEPAL_TZ)
    total_bridged = 0
    for portal in TOP_NEPAL_NEWS_PORTALS:
        if portal.get("type") != "x_bridge":
            continue
        t0 = time.time()
        try:
            bridged = fetch_x_bridged_portal_articles(
                portal,
                now_npt,
                max_entries=40,
                seed_x_posts=x_posts,
            )
            if bridged:
                try:
                    batch_fetch_full_content(bridged, max_workers=8, summarize_english=False)
                except Exception:
                    pass
                latency = round(time.time() - t0, 3)
                batch_upsert_articles(bridged, portal["name"], latency_secs=latency)
                total_bridged += len(bridged)
        except Exception:
            pass
    try:
        total_bridged += boost_x_portals_to_articles(x_posts=x_posts, now_npt=now_npt)
    except Exception:
        pass
    return total_bridged


def fetch_single_portal(
    portal,
    now_npt,
    max_entries: int = 50,
    persist: bool = True,
    raise_on_error: bool = False,
):
    """
    Fetches articles from a single online news portal (RSS, category feeds, or direct HTML).
    Guarantees deep article discovery without arbitrary limits, normalizes canonical URLs,
    extracts rich metadata, and updates persistent checkpoints and health metrics.
    """
    import time
    t0 = time.time()
    items = []
    seen_links = set()

    def process_rss_content(content_bytes, p_info, entry_limit: int = max_entries):
        parsed_items = []
        feed = feedparser.parse(content_bytes)
        for entry in feed.entries[:entry_limit]:
            title = entry.get("title", "").strip()
            raw_link = entry.get("link", "#")
            norm_link = normalize_canonical_url(raw_link)
            if not title or not norm_link or norm_link in seen_links:
                continue

            pub_raw = entry.get("published", "") or entry.get("updated", "")
            if not pub_raw and norm_link.startswith("http"):
                pub_raw = extract_date_from_card_or_url(None, norm_link, now_npt)
            pub_dt, rel_time, exact_time = parse_to_nepal_time(pub_raw, now_npt)

            content_candidates = []
            if "content" in entry and isinstance(entry["content"], list):
                for c in entry["content"]:
                    if isinstance(c, dict) and "value" in c:
                        content_candidates.append(c["value"])
            if "content:encoded" in entry and entry["content:encoded"]:
                content_candidates.append(entry["content:encoded"])
            if "description" in entry and entry["description"]:
                content_candidates.append(entry["description"])
            if "summary" in entry and entry["summary"]:
                content_candidates.append(entry["summary"])

            best_content = ""
            for cand in content_candidates:
                clean_cand = re.sub(r"<[^>]+>", " ", str(cand))
                clean_cand = html.unescape(clean_cand)
                clean_cand = re.sub(r"\s+", " ", clean_cand).strip()
                if len(clean_cand) > len(best_content):
                    best_content = clean_cand

            full_content = best_content if best_content else title
            clean_summary = full_content[:260] + ("..." if len(full_content) > 260 else "")

            title_lower = title.lower()
            is_viral = any(k in title_lower for k in [
                "social media", "twitter", "facebook", "viral", "एक्स", "फेसबुक", "सामाजिक सञ्जाल", "भाइरल", "ट्वीट"
            ])

            cls_res = classify_article_editorial(title, clean_summary, p_info["name"], full_content)
            classified_cat = cls_res["primary_section"]
            headline_en = title if p_info.get("lang") == "English" else ""
            canonical_id = generate_canonical_id(p_info["name"], norm_link, title)

            clean_link = norm_link if ("bing.com" in raw_link.lower() and norm_link.startswith("http")) else raw_link
            seen_links.add(norm_link)
            parsed_items.append({
                "canonical_id": canonical_id,
                "source": p_info["name"],
                "language": p_info.get("lang", "Nepali"),
                "portal_category": p_info.get("category", "General News"),
                "structured_category": classified_cat,
                "primary_section": classified_cat,
                "sections": cls_res["sections"],
                "secondary_tags": cls_res["secondary_tags"],
                "classification_confidence": cls_res["confidence"],
                "low_confidence": cls_res["low_confidence"],
                "category_icon": CATEGORY_ICONS.get(classified_cat, "📌"),
                "title": title,
                "headline_english": headline_en,
                "link": clean_link,
                "canonical_url": norm_link,
                "summary": clean_summary,
                "full_content": full_content,
                "published_dt": pub_dt,
                "relative_time": rel_time,
                "exact_time": exact_time,
                "is_viral": is_viral
            })
        return parsed_items

    def _clean_anchor_title_and_summary(a_el) -> Tuple[str, str]:
        """
        Extracts clean headline text and standfirst summary from an <a> node without mutating
        the live DOM tree, stripping embedded date-only spans (e.g. <span>2026-11-19</span>)
        and UI badge elements so dates never pollute article titles or canonical_id hashes.
        """
        a_clone = BeautifulSoup(str(a_el), "html.parser")
        for noisy_child in a_clone.find_all(["svg", "script", "style", "time", "button"]):
            noisy_child.decompose()
        for span_el in a_clone.find_all(["span", "small", "div"]):
            s_cls = " ".join(span_el.get("class") or []).lower()
            s_txt = span_el.get_text(" ", strip=True)
            if any(b in s_cls for b in ("prem-icon", "badge", "date", "time", "cat-label", "tag-label")):
                span_el.decompose()
            elif s_txt and re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", s_txt.strip()):
                span_el.decompose()

        heading_el = a_clone.find(["h1", "h2", "h3", "h4", "h5"])
        p_in = a_clone.find("p")
        card_summary = ""
        if heading_el and heading_el.get_text(strip=True):
            raw_title = " ".join(heading_el.get_text(" ", strip=True).split())
            if p_in and p_in.get_text(strip=True):
                card_summary = " ".join(p_in.get_text(" ", strip=True).split())
        elif p_in and p_in.get_text(strip=True):
            p_txt = " ".join(p_in.get_text(" ", strip=True).split())
            full_txt = " ".join(a_clone.get_text(" ", strip=True).split())
            raw_title = full_txt.replace(p_txt, "").strip() or full_txt
            card_summary = p_txt if p_txt != raw_title else ""
        else:
            raw_title = " ".join(a_clone.get_text(" ", strip=True).split())

        # Strip trailing bare YYYY-MM-DD / YYYY/MM/DD date tokens appended inside latest-news links
        clean_title = re.sub(r"\s+\b202[0-9][-/](?:0[1-9]|1[0-2])[-/](?:0[1-9]|[12][0-9]|3[01])\b\s*$", "", raw_title).strip()
        return clean_title, card_summary

    def _candidate_freshness_key(cand_tuple) -> Tuple[int, int, int]:
        """Prioritizes today's and recent article URLs ahead of older archive features before max_entries slicing."""
        a_el, _txt, _sum, href_val, _norm, dom_idx = cand_tuple
        m_u = re.search(r"/(202[0-9])[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])", href_val)
        if not m_u:
            m_u = re.search(r"-(202[0-9])-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])", href_val)
        if m_u:
            try:
                u_date = datetime.date(int(m_u.group(1)), int(m_u.group(2)), int(m_u.group(3)))
                day_age = (now_npt.date() - u_date).days
                if day_age <= 0:
                    return (0, 0, dom_idx)
                if day_age == 1:
                    return (1, 1, dom_idx)
                return (3, max(2, day_age), dom_idx)
            except Exception:
                pass
        anc_cls = " ".join(" ".join(p.get("class") or []) for p in a_el.parents if hasattr(p, "get")).lower()
        if any(k in anc_cls for k in ("template-taja", "latest", "breaking", "taja")):
            return (0, 0, dom_idx)
        return (2, 0, dom_idx)

    def _process_html_content(
        html_raw: str,
        base_url: str,
        p_info: Dict[str, Any],
        entry_limit: int = max_entries,
    ) -> List[Dict[str, Any]]:
        parsed_html: List[Dict[str, Any]] = []
        soup = BeautifulSoup(html_raw, "html.parser")
        seen_titles = set()
        local_seen_links = set(seen_links)
        candidates = []

        for dom_idx, a in enumerate(soup.find_all("a", href=True)):
            href = a["href"].strip()
            anc_tags = {p.name for p in a.parents if hasattr(p, "name")}
            if "nav" in anc_tags or "header" in anc_tags or "footer" in anc_tags:
                continue
            anc_classes = " ".join(" ".join(p.get("class") or []) for p in a.parents if hasattr(p, "get")).lower()
            if any(skip_cls in anc_classes for skip_cls in ["search-overlay", "trending-scroll", "navbar", "nav-menu", "main-menu", "header-menu", "footer", "blocktop"]):
                continue
            if any(skip_p in href.lower() for skip_p in ["/author/", "/tag/", "/category/", "/topic/", "/morearticles/", "/page/", "/hong-kong-home", "/entertainment"]):
                continue
            if href.startswith("/"):
                parsed_base = urllib.parse.urlparse(base_url)
                origin = f"{parsed_base.scheme}://{parsed_base.netloc}" if parsed_base.scheme and parsed_base.netloc else base_url.rstrip("/")
                href = origin.rstrip("/") + href
            elif not href.startswith("http"):
                continue

            parsed_path = urllib.parse.urlparse(href).path.rstrip("/").lower()
            if parsed_path in _NON_ARTICLE_EXACT_PATHS:
                continue

            txt, card_summary = _clean_anchor_title_and_summary(a)
            if len(txt) < 20 or txt in seen_titles:
                continue
            if any(k in txt.lower() for k in [
                "privacy", "terms", "contact us", "about us", "advertise", "epaper",
                "login", "more articles", "see more", "preferred source on google",
                "view calendar", "air quality in kathmandu",
            ]):
                continue

            norm_link = normalize_canonical_url(href)
            if not norm_link or norm_link in local_seen_links:
                continue

            seen_titles.add(txt)
            local_seen_links.add(norm_link)
            candidates.append((a, txt, card_summary, href, norm_link, dom_idx))

        candidates.sort(key=_candidate_freshness_key)

        for a, txt, card_summary, href, norm_link, _dom_idx in candidates[:entry_limit]:
            seen_links.add(norm_link)
            art_summary = card_summary if (card_summary and len(card_summary) > 15 and card_summary != txt) else txt
            if art_summary == txt:
                curr = a.parent
                for _ in range(3):
                    if not curr:
                        break
                    for p in curr.find_all("p", recursive=False):
                        p_text = p.get_text(strip=True)
                        if len(p_text) > 15 and p_text != txt:
                            art_summary = p_text
                            break
                    if art_summary != txt:
                        break
                    curr = curr.parent

            parsed_dt = extract_date_from_card_or_url(a, href, now_npt)
            art_dt, rel_time, exact_time = parse_to_nepal_time(parsed_dt, now_npt)
            cls_res = classify_article_editorial(txt, art_summary, p_info["name"], art_summary)
            classified_cat = cls_res["primary_section"]
            headline_en = txt if p_info.get("lang") == "English" else ""
            canonical_id = generate_canonical_id(p_info["name"], norm_link, txt)

            parsed_html.append({
                "canonical_id": canonical_id,
                "source": p_info["name"],
                "language": p_info.get("lang", "Nepali"),
                "portal_category": p_info.get("category", "General News"),
                "structured_category": classified_cat,
                "primary_section": classified_cat,
                "sections": cls_res["sections"],
                "secondary_tags": cls_res["secondary_tags"],
                "classification_confidence": cls_res["confidence"],
                "low_confidence": cls_res["low_confidence"],
                "category_icon": CATEGORY_ICONS.get(classified_cat, "📌"),
                "title": txt,
                "headline_english": headline_en,
                "link": href,
                "canonical_url": norm_link,
                "summary": art_summary,
                "full_content": art_summary,
                "published_dt": art_dt,
                "relative_time": rel_time,
                "exact_time": exact_time,
                "is_viral": False
            })
        return parsed_html

    def _fetch_bytes(target_url: str, timeout_secs: float, allow_conditional: bool = False) -> Tuple[Optional[bytes], bool]:
        if allow_conditional:
            try:
                c_bytes, is_mod, st_code = fetch_feed_with_conditional_cache(target_url, timeout_secs=timeout_secs)
                if not is_mod or st_code == 304:
                    return None, False
                if c_bytes is not None:
                    return c_bytes, True
            except Exception as cond_err:
                logger.debug(f"Conditional fetcher failed for {target_url}, falling back: {cond_err}")

        sess = get_worker_session()
        parsed_u = urllib.parse.urlparse(target_url)
        origin = f"{parsed_u.scheme}://{parsed_u.netloc}/" if parsed_u.scheme and parsed_u.netloc else target_url
        try:
            r_resp = sess.get(
                target_url,
                headers={**DEFAULT_HEADERS, "Referer": origin},
                timeout=timeout_secs,
                verify=False,
            )
            if r_resp.ok and r_resp.content:
                return r_resp.content, True
        except Exception as primary_err:
            try:
                req = urllib.request.Request(target_url, headers=DEFAULT_HEADERS)
                with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout_secs) as response:
                    return response.read(), True
            except Exception:
                pass
            raise primary_err
        return b"", True

    def _ingest_endpoint_bytes(raw_bytes: bytes, endpoint_url: str, p_info: Dict[str, Any], limit_items: int) -> List[Dict[str, Any]]:
        head_low = raw_bytes[:1024].lstrip().lower()
        is_html_doc = head_low.startswith(b"<!doctype html") or head_low.startswith(b"<html") or (b"<html" in head_low and b"<rss" not in head_low and b"<feed" not in head_low)
        if not is_html_doc and (
            b"<rss" in head_low
            or b"<feed" in head_low
            or b"<item" in head_low
            or b"<?xml" in head_low
            or endpoint_url.rstrip("/").endswith(("/rss", "/feed", "/feeds"))
            or "format=rss" in endpoint_url.lower()
        ):
            return process_rss_content(raw_bytes, p_info, entry_limit=limit_items)
        return _process_html_content(raw_bytes.decode("utf-8", errors="ignore"), endpoint_url, p_info, entry_limit=limit_items)

    last_exc: Optional[Exception] = None
    is_x_bridge = portal.get("type") == "x_bridge"
    try:
        # 1. Poll primary portal source (X-bridge syndication or direct RSS/HTML)
        if is_x_bridge:
            try:
                bridged = fetch_x_bridged_portal_articles(portal, now_npt, max_entries=max_entries)
                for ba in bridged:
                    norm_u = ba.get("canonical_url") or normalize_canonical_url(ba.get("link", ""))
                    if norm_u and norm_u not in seen_links:
                        seen_links.add(norm_u)
                        items.append(ba)
            except Exception as e:
                last_exc = e
        else:
            try:
                primary_bytes, is_mod = _fetch_bytes(portal["url"], 6.0, allow_conditional=(portal["type"] == "rss"))
                if not is_mod or primary_bytes is None:
                    # 304 Not Modified: feed has not changed since last cycle
                    logger.info(f"Feed unchanged (HTTP 304): {portal['name']} ({portal['url']})")
                elif portal["type"] == "rss":
                    items.extend(process_rss_content(primary_bytes, portal, entry_limit=max_entries))
                else:
                    items.extend(_process_html_content(primary_bytes.decode("utf-8", errors="ignore"), portal["url"], portal, entry_limit=max_entries))
            except Exception as e:
                last_exc = e

        # 2. Poll configured alt_urls (section pages, category feeds, and date-sorted RSS fallbacks)
        # For x_bridge portals, alt_urls serve strictly as a zero-item fallback when X syndication yields nothing;
        # for HTML/RSS portals, always supplement discovery across section pages.
        if portal.get("alt_urls") and (not is_x_bridge or not items):
            per_alt_limit = max_entries if not items else max(20, max_entries // 2)
            total_cap = max_entries + len(portal.get("alt_urls", [])) * 20
            for alt_url in portal.get("alt_urls", []):
                if len(items) >= total_cap:
                    break
                try:
                    alt_bytes, alt_mod = _fetch_bytes(alt_url, 4.5, allow_conditional=True)
                    if alt_mod and alt_bytes:
                        items.extend(_ingest_endpoint_bytes(alt_bytes, alt_url, portal, limit_items=per_alt_limit))
                except Exception as e:
                    if last_exc is None:
                        last_exc = e

        # If every candidate URL errored and nothing was parsed, surface real failure instead of silent empty
        if not items and last_exc is not None:
            raise last_exc

        # Hydrate full article body (batch_fetch_full_content automatically skips _SKIP_DIRECT_SCRAPE_DOMAINS)
        if items:
            try:
                batch_fetch_full_content(items, max_workers=12, summarize_english=False)
            except Exception:
                pass

        # Persist discovered batch once when caller doesn't handle persistence itself
        latency = round(time.time() - t0, 3)
        if items and persist:
            batch_upsert_articles(items, portal["name"], latency_secs=latency)
    except Exception as e:
        if raise_on_error:
            raise
        latency = round(time.time() - t0, 3)
        record_source_error(portal["name"], format_exc(e), latency_secs=latency)

    return items

def fetch_top_nepal_media(max_workers: int = 25, force_refresh: bool = False, return_all_stored: bool = True, on_progress=None):
    """
    Fetches real-time news items across all configured Top Nepal Online News Portals in parallel.
    If force_refresh=False and the SQLite store already holds recent articles, returns them
    immediately in <50ms while the background daemon keeps the store continuously synced.
    Pass return_all_stored=False during background/manual ingestion to skip re-fetching 1500 stored rows.
    """
    now_npt = datetime.datetime.now(NEPAL_TZ)
    all_articles = []

    # Fast path: serve immediately from store unless explicit refresh is requested
    if not force_refresh:
        try:
            since_dt = now_npt - datetime.timedelta(days=7)
            stored_fast = get_stored_articles(start_dt=since_dt, limit=1500)
            if len(stored_fast) >= 50:
                for sa in stored_fast:
                    pdt = sa.get("published_dt")
                    if isinstance(pdt, datetime.datetime):
                        _, sa["relative_time"], sa["exact_time"] = parse_to_nepal_time(pdt, now_npt)
                stored_fast.sort(key=lambda x: x["published_dt"] if isinstance(x["published_dt"], datetime.datetime) else now_npt, reverse=True)
                return stored_fast
        except Exception:
            pass

    # Ensure source registry is synced (internally cached with 15-min TTL)
    try:
        register_portal_sources(TOP_NEPAL_NEWS_PORTALS)
    except Exception:
        pass

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    try:
        futures = [executor.submit(fetch_single_portal, p, now_npt) for p in TOP_NEPAL_NEWS_PORTALS]
        try:
            for f in concurrent.futures.as_completed(futures, timeout=45):
                try:
                    res = f.result(timeout=5)
                    if res:
                        all_articles.extend(res)
                        if on_progress is not None:
                            try:
                                on_progress(len(all_articles))
                            except Exception:
                                pass
                except Exception:
                    pass
        except concurrent.futures.TimeoutError:
            pass
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if not return_all_stored:
        return all_articles

    # Reconcile with persistent stored articles from past 7 days to prevent any missed articles
    try:
        since_dt = now_npt - datetime.timedelta(days=7)
        stored_articles = get_stored_articles(start_dt=since_dt, limit=1500)
        seen_ids = {a.get("canonical_id") or a.get("link") for a in all_articles}
        for sa in stored_articles:
            cid = sa.get("canonical_id") or sa.get("link")
            if cid not in seen_ids:
                all_articles.append(sa)
                seen_ids.add(cid)
    except Exception:
        pass

    all_articles.sort(key=lambda x: x["published_dt"] if isinstance(x["published_dt"], datetime.datetime) else now_npt, reverse=True)
    return all_articles

# =====================================================================
# CONTEXTUAL AI / SEMANTIC NEPAL-RELEVANCE CLASSIFIER FOR INDIAN MEDIA
# =====================================================================

_NAV_BOILERPLATE_RE = re.compile(
    r'\b(cookie policy|privacy policy|terms of use|subscribe now|newsletter|about us|contact us|'
    r'epaper|download app|play store|feedback|personal loan|home loan|credit card|gold rate|'
    r'horoscope|astrology|zodiac|weather today|stock market live|sensex|nifty|crossword|sudoku|'
    r'entertainment desk|lifestyle desk|sports desk|trending news|photo gallery|web stories|'
    r'visual stories|click here|read more|advertisement|sponsored|preferred source on google|'
    r'whatsapp channel|join telegram|follow us on)\b|'
    r'(?:google\s*पर\s*पसंदीदा\s*सोर्स|पसंदीदा\s*सोर्स\s*बनाएं)',
    re.IGNORECASE
)

_NEPAL_CORE_SUBJECT_RE = re.compile(
    r'(\bnepal\b|\bnepali\b|\bnepalese\b|\bkathmandu\b|\bpokhara\b|\bbirgunj\b|\bbiratnagar\b|'
    r'\bjanakpur\b|\bjanakpurdham\b|\blumbini\b|\bchitwan\b|\bbhairahawa\b|\bdhangadhi\b|\bnepalgunj\b|\bmadhesh\b|'
    r'\bterai\b|\btarai\b|\brautahat\b|\bayodhya-janakpur\b|\bsingha durbar\b|\bsheetal niwas\b|\bbaluwatar\b|'
    r'\bkp sharma oli\b|\bk\.?\s*p\.?\s*oli\b|\boli\b|\bprachanda\b|\bpushpa kamal dahal\b|'
    r'\bsher bahadur deuba\b|\bdeuba\b|\bbalen shah\b|\bbalen\b|\bbalendra shah\b|\bbalendra\b|'
    r'\bsushila karki\b|\brabi lamichhane\b|\bgagan thapa\b|\bram chandra paudel\b|\barzu rana\b|'
    r'\bindo-nepal\b|\bnepal-india\b|\bkalapani\b|\blipulekh\b|\blimpiyadhura\b|\bsusta\b|'
    r'\bgorkha\b|\bgurkha\b|\bannapurna\b|\bmustang\b|\bbhotekoshi\b|\brasuwagadhi\b|\btatopani\b|'
    r'\bnepal premier league\b|\bnpl\b|\btribhuvan\b|'
    r'\bpashupatinath\b|\bmuktinath\b|\bsagarmatha\b|\beverest\b|\bkoshi\b|\bgandak\b|\bmahakali\b|'
    r'\bpancheshwar\b|\barun-?3\b|\barun iii\b|\bupper karnali\b|\bwest seti\b|'
    r'नेपाल|नेपाली|नेपाल-भारत|भारत-नेपाल|नेपाल सीमा|काठमांडू|काठमाण्डू|काठमाण्डौ|काठमाडौँ|'
    r'पोखरा|बीरगंज|वीरगन्ज|विराटनगर|जनकपुर|जनकपुरधाम|लुम्बिनी|लुंबिनी|मधेस|मधेश|तराई|रौतहट|धनगढी|भैरहवा|नेपालगंज|'
    r'ओली|केपी ओली|प्रचंड|प्रचण्ड|देउवा|बालेन|बालेन्द्र|बालेंद्र|सुशीला कार्की|नेपाली कांग्रेस|माओवादी|एमाले|'
    r'गोरखा|एवरेस्ट|अन्नपूर्णा|भोटेकोशी|रसुवागढी|तातोपानी|मुस्ताङ|त्रिभुवन|'
    r'कालापानी|लिपुलेख|लिम्पियाधुरा|कोशी|सप्तकोशी|गंडक|महाकाली|पशुपतिनाथ|मुक्तिनाथ|सोनौली|रक्सौल|जोगबनी|रुपईडीहा|बनबसा)',
    re.IGNORECASE
)

_NEPAL_URL_SLUG_RE = re.compile(
    r'(?<![a-z0-9])(nepal|kathmandu|kalapani|lipulekh|oli|prachanda|pokhara|madhesh|gorkha|gurkha|koshi|balen|balendra)(?![a-z0-9])',
    re.IGNORECASE,
)

_NEPAL_PILLAR_PATTERNS = {
    "Bilateral & Diplomacy": re.compile(
        r'(\bindo-nepal\b|\bnepal-india\b|\bbilateral\b|\bdiploma(?:cy|tic|t)\b|\bambassador\b|\benvoy\b|'
        r'\bembassy\b|\bforeign minister\b|\bforeign secretary\b|\bmea\b|\bexternal affairs\b|'
        r'\bjoint commission\b|\btreaty of peace\b|\b1950 treaty\b|\bstate visit\b|\bofficial visit\b|'
        r'\bmou\b|\bmemorandum of understanding\b|\bhigh-level visit\b|\bsummit\b|\bdelegation\b|'
        r'द्विपक्षीय|कूटनीतिक|राजदूत|विदेश मंत्री|विदेश सचिव|संधि|समझौता|दौरा|शिखर वार्ता)',
        re.IGNORECASE
    ),
    "Policy, Economy & Connectivity": re.compile(
        r'(\btrade\b|\bimport\b|\bexport\b|\btariff\b|\bcustoms\b|\btransit\b|\bconnectivity\b|'
        r'\brailway\b|\brail link\b|\bhydropower\b|\bpower trade\b|\belectricity\b|\bmegawatt\b|\bmw\b|'
        r'\bgrid\b|\bpipeline\b|\bpetroleum\b|\bioc\b|\bupi\b|\bcross-border payment\b|\brupay\b|'
        r'\brbi\b|\bnrb\b|\bnepal rastra bank\b|\binvestment\b|\blines? of credit\b|\bgrant\b|\baid\b|'
        r'\bicp\b|\bintegrated check post\b|\bbridge\b|\bhighway\b|\bairspace\b|\baviation\b|'
        r'\barun\b|\bpancheshwar\b|\bkoshi\b|\bgandak\b|\bmahakali\b|\bkarnali\b|\bseti\b|'
        r'\bwheat\b|\brice export\b|\bonion export\b|\bsugar\b|\bfertilizer\b|'
        r'व्यापार|आयात|निर्यात|सीमा शुल्क|पारवहन|रेलवे|जलविद्युत|बिजली|पाइपलाइन|निवेश|अनुदान|सहायता|बजट)',
        re.IGNORECASE
    ),
    "Borders & Security": re.compile(
        r'(\bborder\b|\bkalapani\b|\blipulekh\b|\blimpiyadhura\b|\bsusta\b|\bno-man\'?s land\b|'
        r'\bpillar\b|\bssb\b|\bsashastra seema bal\b|\bapf\b|\barmed police\b|\braxaul\b|\bsunauli\b|'
        r'\brupaidiha\b|\bbanbasa\b|\bpanitanki\b|\bjogbani\b|\bjhulaghat\b|\bdarchula\b|\bkakarbhitta\b|'
        r'\bborder outpost\b|\bbop\b|\bsmuggling\b|\binfiltration\b|\bextradition\b|\bsecurity\b|'
        r'\bdefence\b|\bdefense\b|\bmilitary\b|\barmy chief\b|\bsurya kiran\b|\bjoint exercise\b|'
        r'\bagnipath\b|\bgorkha rifles\b|\bgorkha recruitment\b|\bcross-border\b|\bcheckpost\b|'
        r'\bpassport\b|\bimmigration\b|\bvisa\b|'
        r'सीमा|कालापानी|लिपुलेख|लिम्पियाधुरा|सुस्ता|एसएसबी|रक्सौल|सोनौली|रुपईडीहा|बनबसा|जोगबनी|सुरक्षा|सैन्य|गोरखा|तस्करी)',
        re.IGNORECASE
    ),
    "Nepal Domestic Affairs": re.compile(
        r'(\bkathmandu\b|\bparliament\b|\bcabinet\b|\bcoalition\b|\bprime minister\b|\bpresident\b|'
        r'\bsupreme court\b|\bconstitution\b|\belection\b|\bprotest\b|\bmonarchy\b|\broyalist\b|'
        r'\brsp\b|\buml\b|\bnepali congress\b|\bmaoist\b|\bmadhesh\b|\bprovince\b|\bgovernance\b|'
        r'\bearthquake\b|\bflood\b|\blandslide\b|\bavalanche\b|\bplane crash\b|\bhelicopter\b|'
        r'\btourism\b|\bpilgrim(?:s|age)?\b|\beverest\b|\bpashupatinath\b|\bmuktinath\b|\blumbini\b|'
        r'संसद|मंत्रिमंडल|गठबंधन|प्रधानमंत्री|राष्ट्रपति|सर्वोच्च न्यायालय|संविधान|चुनाव|प्रदर्शन|राजतंत्र|भूकंप|बाढ़|भूस्खलन|तीर्थयात्री|पर्यटन)',
        re.IGNORECASE
    ),
    "Regional Geopolitics": re.compile(
        r'(\bsaarc\b|\bbimstec\b|\bbbin\b|\bchina\b|\bbeijing\b|\bbri\b|\bbelt and road\b|'
        r'\btrilateral\b|\bhimalaya(?:n|s)?\b|\bsouth asia\b|\bneighborhood first\b|\bneighbourhood first\b|'
        r'\bindo-pacific\b|\bmcc\b|\bgeopolitic(?:s|al)\b|\bstrategic\b|'
        r'सार्क|बिमस्टेक|चीन|बीआरआई|हिमालय|दक्षिण एशिया|भू-राजनीति|सामरिक)',
        re.IGNORECASE
    ),
}

_OTHER_COUNTRIES_RE = re.compile(
    r'\b(sri lanka|maldives|bangladesh|bhutan|myanmar|pakistan|afghanistan|mauritius|seychelles|'
    r'thailand|indonesia|vietnam|singapore|malaysia|philippines|japan|south korea|australia|uae|qatar|'
    r'श्रीलंका|मालदीव|बांग्लादेश|भूटान|म्यांमार|पाकिस्तान|अफगानिस्तान|मॉरीशस)\b',
    re.IGNORECASE
)

_PURE_INDIAN_DOMESTIC_NOISE_RE = re.compile(
    r'\b(ipl|bcci|ranji trophy|bollywood|box office|bigg boss|kbc|neet|jee main|cbse|icse|'
    r'lok sabha सीट|विधानसभा उपचुनाव|शेयर बाजार|सेंसेक्स|निफ्टी|बॉलीवुड|क्रिकेट|आईपीएल|'
    r'personal loan|emi calculator|rashifal|राशिफल|पंचांग)\b',
    re.IGNORECASE
)


def evaluate_indian_article_nepal_relevance(
    title: str,
    summary: str = "",
    full_content: str = "",
    link: str = "",
    source: str = "",
    threshold: float = DEFAULT_NEPAL_RELEVANCE_THRESHOLD
) -> dict:
    """
    Contextual AI / Multi-Feature Semantic Classifier evaluating whether an Indian media
    article is SUBSTANTIALLY related to Nepal.
    
    Returns:
        {
            "nepal_relevance_score": float (0.0 to 1.0),
            "relevance_status": "substantive" | "borderline_review" | "excluded",
            "relevance_reason": str,
            "nepal_dimensions": list[str],
            "is_substantive": bool
        }
    """
    clean_title = (title or "").strip()
    clean_summary = (summary or "").strip()
    clean_body = (full_content or clean_summary or "").strip()
    clean_link = (link or "").strip().lower()

    # Step 1: Reject empty/short titles, navigation links, or bare tag index pages
    if len(clean_title) < 18 or _NAV_BOILERPLATE_RE.search(clean_title):
        return {
            "nepal_relevance_score": 0.0,
            "relevance_status": "excluded",
            "relevance_reason": "Navigation/boilerplate or non-article link",
            "nepal_dimensions": [],
            "is_substantive": False,
        }

    if clean_link:
        parsed_path = urllib.parse.urlparse(clean_link).path.rstrip("/")
        if (
            parsed_path.endswith(("/topic/nepal", "/tags/nepal", "/about/nepal", "/topic/india-nepal-relations", "/nepal"))
            or re.search(r"/(?:tag|tags|topic|topics|about)/[^/]+$", parsed_path)
        ):
            return {
                "nepal_relevance_score": 0.0,
                "relevance_status": "excluded",
                "relevance_reason": "Index/tag landing page URL rather than an article",
                "nepal_dimensions": [],
                "is_substantive": False,
            }

    # Step 2: Check core Nepal anchors across Headline, Body, and URL slug (strict slug boundaries)
    title_matches = _NEPAL_CORE_SUBJECT_RE.findall(clean_title)
    body_text_only = clean_body if clean_body != clean_title else ""
    body_matches = _NEPAL_CORE_SUBJECT_RE.findall(body_text_only)
    url_has_nepal = bool(_NEPAL_URL_SLUG_RE.search(clean_link))

    total_nepal_anchors = len(title_matches) + len(body_matches) + (1 if url_has_nepal else 0)
    if total_nepal_anchors == 0:
        return {
            "nepal_relevance_score": 0.0,
            "relevance_status": "excluded",
            "relevance_reason": "No Nepal entity, geography, leadership, or bilateral anchor detected",
            "nepal_dimensions": [],
            "is_substantive": False,
        }

    # Step 3: Evaluate contextual thematic dimensions
    combined_text = f"{clean_title} {body_text_only}"
    matched_dimensions = []
    pillar_hit_count = 0
    for dim_name, pattern in _NEPAL_PILLAR_PATTERNS.items():
        hits = pattern.findall(combined_text)
        if hits:
            matched_dimensions.append(dim_name)
            pillar_hit_count += len(hits)

    # Step 4: Compute Contextual Relevance Confidence Score
    score = 0.0
    reasons = []

    # A. Headline prominence (strongest signal that Nepal is the core subject of the article)
    if len(title_matches) >= 2:
        score += 0.56
        reasons.append("Primary headline subject is Nepal/Indo-Nepal")
    elif len(title_matches) == 1:
        score += 0.48
        reasons.append("Nepal explicitly anchored in headline")
    elif url_has_nepal:
        score += 0.28
        reasons.append("Nepal in article URL slug")
    elif len(body_matches) >= 2:
        score += 0.28
        reasons.append("Multiple Nepal references in article body")
    else:
        score += 0.14
        reasons.append("Single passing mention of Nepal in body")

    # B. Thematic pillar depth (monotonic: matched pillars always outscore 0-pillar fallback)
    if matched_dimensions:
        dim_boost = min(0.38, 0.20 + 0.07 * (len(matched_dimensions) - 1) + min(0.08, pillar_hit_count * 0.02))
        score += dim_boost
        reasons.append(f"Contextual pillars: {', '.join(matched_dimensions)}")
    elif len(title_matches) >= 1:
        score += 0.18
        matched_dimensions.append("Nepal Domestic Affairs")
        reasons.append("Direct Nepal coverage in headline")

    # C. Body density bonus when body differs from title and reinforces Nepal focus
    if len(body_matches) >= 2 and len(title_matches) >= 1:
        score += 0.08

    # Step 5: Contextual Penalties for Incidental / Fleeting Mentions & Domestic Indian Noise
    other_countries = set(m.lower() for m in _OTHER_COUNTRIES_RE.findall(combined_text))
    if len(other_countries) >= 3 and len(title_matches) == 0:
        # Multi-country roundup where Nepal is just one item in a list of countries
        score -= 0.28
        reasons.append(f"Penalized: multi-country list mention ({len(other_countries)} other nations)")
    elif len(other_countries) >= 3 and len(title_matches) == 1 and "Bilateral & Diplomacy" not in matched_dimensions:
        score -= 0.18
        reasons.append("Penalized: broad regional list without dedicated Nepal focus")

    # Skip domestic noise penalties whenever a Nepal core subject is explicitly anchored in the headline
    if len(title_matches) == 0 and _PURE_INDIAN_DOMESTIC_NOISE_RE.search(combined_text):
        score -= 0.35
        reasons.append("Penalized: domestic Indian entertainment/sports/finance noise")

    # Check if an Indian domestic story merely mentions "border" or a state (Bihar/UP) with a fleeting Nepal mention
    if len(title_matches) == 0 and len(body_matches) <= 1 and not url_has_nepal:
        score = min(score, 0.52)
        if "Passing/incidental reference only" not in reasons:
            reasons.append("Capped: Nepal is not in headline/URL and appears only once in summary")

    score = round(max(0.0, min(0.99, score)), 2)

    if score >= threshold:
        status = "substantive"
    elif score >= BORDERLINE_NEPAL_RELEVANCE_FLOOR:
        status = "borderline_review"
    else:
        status = "excluded"

    return {
        "nepal_relevance_score": score,
        "relevance_status": status,
        "relevance_reason": " | ".join(reasons),
        "nepal_dimensions": matched_dimensions,
        "is_substantive": status == "substantive",
    }


_NEPALI_EXCLUDED_DOMAINS = (
    ".com.np", ".gov.np", ".edu.np", ".org.np", ".net.np",
    "ekantipur.com", "onlinekhabar.com", "setopati.com", "ratopati.com",
    "kathmandupost.com", "thehimalayantimes.com", "myrepublica.nagariknetwork.com",
    "nepalkhabar.com", "khabarhub.com", "nepallive.com", "nepalnews.com",
    "nepalpress.com", "baahrakhari.com", "himalpress.com", "deshsanchar.com",
    "shilapatra.com", "gorkhapatraonline.com", "risingnepaldaily.com",
    "nayapatrikadaily.com", "newsofnepal.com",
    "imagekhabar.com", "nepalaaja.com", "lokaantar.com", "hamrokura.com",
)


def _is_excluded_nepali_domain(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(host == d or host.endswith(d if d.startswith(".") else f".{d}") for d in _NEPALI_EXCLUDED_DOMAINS)


def _unwrap_bing_link(raw_link: str, fallback_base: str = "") -> str:
    link = (raw_link or "").strip()
    if link.startswith("/") and fallback_base:
        link = urllib.parse.urljoin(fallback_base, link)
    if "bing.com" in link.lower() and "url=" in link:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
        if qs.get("url") and qs["url"][0].startswith("http"):
            link = qs["url"][0]
    return link


def _norm_title_key(title: str) -> str:
    return " ".join(
        title.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').lower().split()
    )


def _apply_indian_eval(item: Dict[str, Any], rel_eval: Dict[str, Any]) -> None:
    item["nepal_relevance_score"] = rel_eval["nepal_relevance_score"]
    item["relevance_status"] = rel_eval["relevance_status"]
    item["relevance_reason"] = rel_eval["relevance_reason"]
    item["nepal_dimensions"] = rel_eval["nepal_dimensions"]


def _build_indian_article_record(
    src: Dict[str, Any],
    raw_title: str,
    summary_text: str,
    link_url: str,
    pub_dt: datetime.datetime,
    rel_time: str,
    exact_time: str,
    rel_eval: Dict[str, Any],
) -> Dict[str, Any]:
    cls_res = classify_article_editorial(raw_title, summary_text, src["name"], summary_text)
    if "India Section" not in cls_res["sections"]:
        cls_res["sections"].insert(0, "India Section")
    clean_link = normalize_canonical_url(link_url) or link_url
    return {
        "canonical_id": generate_canonical_id(src["name"], clean_link, raw_title),
        "source": src["name"],
        "language": src["lang"],
        "portal_category": "Indian Press",
        "structured_category": cls_res["primary_section"],
        "primary_section": cls_res["primary_section"],
        "sections": cls_res["sections"],
        "secondary_tags": cls_res["secondary_tags"],
        "classification_confidence": cls_res["confidence"],
        "low_confidence": cls_res["low_confidence"],
        "category_icon": CATEGORY_ICONS.get(cls_res["primary_section"], "🇮🇳"),
        "title": raw_title,
        "headline_english": raw_title if src["lang"] == "English" else "",
        "link": clean_link,
        "canonical_url": clean_link,
        "summary": summary_text[:280] + ("..." if len(summary_text) > 280 else ""),
        "full_content": summary_text,
        "published_dt": pub_dt,
        "relative_time": rel_time,
        "exact_time": exact_time,
        "nepal_relevance_score": rel_eval["nepal_relevance_score"],
        "relevance_status": rel_eval["relevance_status"],
        "relevance_reason": rel_eval["relevance_reason"],
        "nepal_dimensions": rel_eval["nepal_dimensions"],
    }


def resolve_google_news_url(url: str, timeout: float = 4.5) -> str:
    """
    Resolves a news.google.com/rss/articles/... redirect URL to its canonical publisher article URL
    via fast base64 protobuf decode (v1 tokens) or Google News batchexecute (v2 AU_yqL tokens),
    caching results in GNEWS_URL_CACHE. Falls back cleanly to the input URL if unresolved.
    """
    import base64

    clean_u = (url or "").strip()
    if not clean_u:
        return ""
    if clean_u in GNEWS_URL_CACHE:
        return GNEWS_URL_CACHE[clean_u]
    try:
        parsed = urllib.parse.urlparse(clean_u)
        if "news.google.com" not in parsed.netloc.lower() or "/articles/" not in parsed.path:
            return clean_u
    except Exception:
        return clean_u

    m_id = re.search(r"/articles/([^?/#]+)", clean_u)
    if not m_id:
        return clean_u
    art_id = m_id.group(1)

    resolved = clean_u
    # 1. Fast local decode for legacy base64-embedded URLs (zero network cost)
    try:
        padded = art_id + "=" * (-len(art_id) % 4)
        raw_b = base64.urlsafe_b64decode(padded)
        raw_s = raw_b.decode("latin-1", errors="ignore")
        if "AU_yqL" not in raw_s:
            m_http = re.search(r"(https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+)", raw_s)
            if m_http and "news.google.com" not in m_http.group(1).lower():
                resolved = m_http.group(1).rstrip("\x00\x01\x02")
    except Exception:
        pass

    # 2. Decode Google News v2 tokens via article splash metadata + batchexecute
    if resolved == clean_u:
        try:
            r_page = requests.get(
                f"https://news.google.com/articles/{art_id}",
                headers=DEFAULT_HEADERS,
                timeout=timeout,
            )
            if r_page.status_code == 200 and r_page.text:
                m_sg = re.search(r'data-n-a-sg="([^"]+)"', r_page.text)
                m_ts = re.search(r'data-n-a-ts="([^"]+)"', r_page.text)
                if m_sg and m_ts:
                    payload = [[
                        "Fbv4je",
                        json.dumps([
                            "garturlreq",
                            [
                                ["X", "X", ["X", "X"], None, None, 1, 1, "IN:en", None, 1, None, None, None, None, None, 0, 1],
                                "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0,
                            ],
                            art_id,
                            int(m_ts.group(1)),
                            m_sg.group(1),
                        ]),
                        None,
                        "generic",
                    ]]
                    r_b = requests.post(
                        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
                        data={"f.req": json.dumps([payload])},
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                            "User-Agent": DEFAULT_HEADERS["User-Agent"],
                        },
                        timeout=timeout,
                    )
                    if r_b.status_code == 200 and r_b.text:
                        m_u = re.search(r'"garturlres","(https?://[^"\\]+)', r_b.text.replace('\\"', '"'))
                        if m_u and "news.google.com" not in m_u.group(1).lower():
                            resolved = m_u.group(1)
        except Exception as exc:
            logger.debug(f"Google News URL decode skipped for {art_id[:16]}: {format_exc(exc, 120)}")

    if resolved and resolved != clean_u:
        GNEWS_URL_CACHE[clean_u] = resolved
    return resolved


def _indian_anchor_date_sort_key(cand_tuple, now_npt: datetime.datetime):
    """Prioritizes fresher dated article URLs ahead of evergreen/pinned links before capping topic_html."""
    _a, _txt, _snip, href_val, dom_idx = cand_tuple
    m_u = re.search(r"/(202[0-9])[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])", href_val)
    if not m_u:
        m_u = re.search(r"-(202[0-9])-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])", href_val)
    if m_u:
        try:
            u_date = datetime.date(int(m_u.group(1)), int(m_u.group(2)), int(m_u.group(3)))
            day_age = max(0, (now_npt.date() - u_date).days)
            return (0 if day_age <= 3 else (1 if day_age <= 14 else 3), day_age, dom_idx)
        except Exception:
            pass
    return (2, 0, dom_idx)


def _fetch_batched_google_news_indian_media(
    sources: List[Dict[str, Any]],
    now_npt: datetime.datetime,
    relevance_threshold: float = DEFAULT_NEPAL_RELEVANCE_THRESHOLD,
    existing_title_keys: Optional[set] = None,
    batch_size: int = 5,
    max_decode_urls: int = 60,
) -> List[Dict[str, Any]]:
    """
    Executes locale-aware batched Google News RSS sweeps (4-6 domains per OR query, when:3d)
    across English and Hindi Indian outlets, attributes each story to its source via <source>,
    skips titles already captured by Bing/HTML, and resolves net-new Google News redirect URLs in parallel.
    """
    if not sources:
        return []

    by_domain: Dict[str, Dict[str, Any]] = {}
    by_name_low: Dict[str, Dict[str, Any]] = {}
    en_sources: List[Dict[str, Any]] = []
    hi_sources: List[Dict[str, Any]] = []

    for s in sources:
        dom = (s.get("domain") or urllib.parse.urlparse(s.get("url", "")).netloc.lower().lstrip("www.")).strip().lower()
        if not dom:
            continue
        by_domain[dom] = s
        by_name_low[s["name"].strip().lower()] = s
        if s.get("lang") == "Hindi":
            hi_sources.append(s)
        else:
            en_sources.append(s)

    def _attribute_source(entry_src: Any, raw_title: str, batch_srcs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        href = ""
        stitle = ""
        if isinstance(entry_src, dict):
            href = (entry_src.get("href") or "").strip().lower()
            stitle = (entry_src.get("title") or "").strip().lower()
        if href:
            host = urllib.parse.urlparse(href).netloc.lower().lstrip("www.")
            for dom, scfg in by_domain.items():
                if host == dom or host.endswith(f".{dom}"):
                    return scfg
        if stitle:
            if stitle in by_name_low:
                return by_name_low[stitle]
            for scfg in batch_srcs:
                sn = scfg["name"].lower()
                if sn in stitle or stitle in sn:
                    return scfg
        if " - " in raw_title:
            tail = raw_title.rsplit(" - ", 1)[-1].strip().lower()
            for scfg in batch_srcs:
                if scfg["name"].lower() in tail or tail in scfg["name"].lower():
                    return scfg
        return None

    queries: List[tuple] = []
    for lang_is_hi, src_list in ((False, en_sources), (True, hi_sources)):
        for i in range(0, len(src_list), batch_size):
            chunk = src_list[i : i + batch_size]
            dom_expr = " OR ".join(f"site:{c['domain']}" for c in chunk if c.get("domain"))
            if not dom_expr:
                continue
            if lang_is_hi:
                q = f"({dom_expr}) (intitle:नेपाल OR intitle:काठमांडू OR intitle:बालेन OR intitle:गोरखा) when:3d"
                u = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=hi&gl=IN&ceid=IN:hi"
            else:
                q = f"({dom_expr}) (intitle:Nepal OR intitle:Kathmandu OR intitle:Balen OR intitle:Balendra OR intitle:Gorkha) when:3d"
                u = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-IN&gl=IN&ceid=IN:en"
            queries.append((u, chunk))

    def _fetch_gnews_batch(url_and_chunk):
        g_url, chunk = url_and_chunk
        try:
            req = urllib.request.Request(g_url, headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=7.0) as resp:
                feed = feedparser.parse(resp.read())
            return chunk, list(feed.entries or [])
        except Exception as exc:
            doms = ",".join(c.get("domain", "") for c in chunk[:3])
            logger.warning(f"Google News RSS batch failed ({doms}...): {format_exc(exc, 160)}")
            return chunk, []

    raw_hits: List[tuple] = []
    seen_local_keys = set(existing_title_keys or set())

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(queries))))
    try:
        futs = [pool.submit(_fetch_gnews_batch, q_item) for q_item in queries]
        for fut in concurrent.futures.as_completed(futs, timeout=18.0):
            try:
                chunk, entries = fut.result(timeout=2.0)
                for e in entries:
                    raw_t = (e.get("title") or "").strip()
                    clean_t = re.sub(r"\s*[-–|]\s*[^-–|]+$", "", raw_t).strip() or raw_t
                    if len(clean_t) < 18 or _NAV_BOILERPLATE_RE.search(clean_t):
                        continue
                    src_cfg = _attribute_source(e.get("source"), raw_t, chunk)
                    if not src_cfg:
                        continue
                    t_key = (src_cfg["name"], _norm_title_key(clean_t))
                    if t_key in seen_local_keys:
                        continue
                    # Pre-screen headline relevance before spending a Google News URL decode request
                    pre_eval = evaluate_indian_article_nepal_relevance(
                        title=clean_t,
                        summary=clean_t,
                        full_content=clean_t,
                        link="",
                        source=src_cfg["name"],
                        threshold=relevance_threshold,
                    )
                    if pre_eval["relevance_status"] == "excluded" and "Navigation/boilerplate" in pre_eval["relevance_reason"]:
                        continue
                    pub_raw = e.get("published", "") or e.get("updated", "")
                    pub_dt, rel_time, exact_time = parse_to_nepal_time(pub_raw, now_npt)
                    # Enforce 7-day freshness guard (Google News occasionally slips older archive hits into when:3d)
                    if (now_npt - pub_dt).total_seconds() > 7 * 86400:
                        continue
                    seen_local_keys.add(t_key)
                    raw_hits.append((pub_dt, rel_time, exact_time, src_cfg, clean_t, e.get("link", ""), pre_eval))
            except Exception as exc:
                logger.warning(f"Google News RSS batch parse error: {format_exc(exc, 160)}")
    except concurrent.futures.TimeoutError:
        logger.warning("Batched Google News RSS discovery reached 18s timeout; proceeding with collected hits.")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    if not raw_hits:
        return []

    # Sort newest-first and decode Google News redirect URLs in parallel for top net-new hits
    raw_hits.sort(key=lambda x: x[0], reverse=True)
    to_decode = raw_hits[:max_decode_urls]
    resolved_map: Dict[str, str] = {}
    dec_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)
    try:
        fut_to_raw = {dec_pool.submit(resolve_google_news_url, hit[5], 4.0): hit[5] for hit in to_decode}
        for fut in concurrent.futures.as_completed(fut_to_raw, timeout=14.0):
            raw_lk = fut_to_raw[fut]
            try:
                resolved_map[raw_lk] = fut.result(timeout=1.0) or raw_lk
            except Exception:
                resolved_map[raw_lk] = raw_lk
    except concurrent.futures.TimeoutError:
        logger.warning("Google News URL resolution hit 14s budget; keeping unresolved links as fallback.")
    finally:
        dec_pool.shutdown(wait=False, cancel_futures=True)

    records: List[Dict[str, Any]] = []
    seen_norm_urls = set()
    for pub_dt, rel_time, exact_time, src_cfg, clean_t, raw_lk, _pre_eval in to_decode:
        final_url = resolved_map.get(raw_lk, raw_lk)
        if not final_url.startswith("http") or _is_excluded_nepali_domain(final_url):
            continue
        norm_u = normalize_canonical_url(final_url) or final_url
        if norm_u in seen_norm_urls:
            continue
        rel_eval = evaluate_indian_article_nepal_relevance(
            title=clean_t,
            summary=clean_t,
            full_content=clean_t,
            link=final_url,
            source=src_cfg["name"],
            threshold=relevance_threshold,
        )
        if "Index/tag landing" in rel_eval["relevance_reason"] or "Navigation/boilerplate" in rel_eval["relevance_reason"]:
            continue
        seen_norm_urls.add(norm_u)
        rec = _build_indian_article_record(
            src=src_cfg,
            raw_title=clean_t,
            summary_text=clean_t,
            link_url=final_url,
            pub_dt=pub_dt,
            rel_time=rel_time,
            exact_time=exact_time,
            rel_eval=rel_eval,
        )
        rec["_precision_search"] = True
        records.append(rec)
    return records


def fetch_single_indian_media(
    src,
    now_npt,
    relevance_threshold: float = DEFAULT_NEPAL_RELEVANCE_THRESHOLD,
    hydrate_bodies: bool = True,
    metrics_out: Optional[Dict[str, Any]] = None,
):
    """
    Fetches candidate articles from prominent Indian media outlets and applies
    contextual Nepal-relevance classification to each candidate.
    Always pairs precision intitle: Bing News RSS discovery with live topic_html/RSS
    scraping (without blocking on synchronous per-link HTTP date fetches).
    """
    t0 = time.time()
    items: List[Dict[str, Any]] = []
    seen_titles = set()
    seen_urls = set()
    excluded_kept = 0
    errors_seen: List[str] = []

    def _try_append_candidate(
        raw_title: str,
        summary_raw: str,
        raw_link: str,
        pub_raw: Any,
        allow_excluded: bool = True,
        dom_tag: Any = None,
        is_precision_search: bool = False,
    ) -> Optional[str]:
        nonlocal excluded_kept
        clean_title = re.sub(r'\s+', ' ', (raw_title or "").strip())
        if len(clean_title) < 18 or clean_title.startswith("{") or _NAV_BOILERPLATE_RE.search(clean_title):
            return None
        title_key = _norm_title_key(clean_title)
        link_url = _unwrap_bing_link(raw_link, src["url"])
        norm_url = normalize_canonical_url(link_url) or link_url
        if not link_url.startswith("http") or _is_excluded_nepali_domain(link_url):
            return None
        if title_key in seen_titles or (norm_url and norm_url in seen_urls):
            return None

        clean_sum = re.sub(r'<[^>]+>', ' ', summary_raw or "")
        clean_sum = re.sub(r'\s+', ' ', html.unescape(clean_sum)).strip()
        summary_text = clean_sum if (clean_sum and clean_sum != clean_title) else clean_title

        rel_eval = evaluate_indian_article_nepal_relevance(
            title=clean_title,
            summary=summary_text,
            full_content=summary_text,
            link=link_url,
            source=src["name"],
            threshold=relevance_threshold,
        )
        if rel_eval["relevance_status"] == "excluded":
            if (
                "Navigation/boilerplate" in rel_eval["relevance_reason"]
                or "Index/tag landing" in rel_eval["relevance_reason"]
            ):
                return None
            # Do not drop precision intitle: items with empty RSS descriptions behind excluded_kept >= 4 before hydration
            has_empty_rss_desc = is_precision_search and (not clean_sum or clean_sum == clean_title)
            if not has_empty_rss_desc:
                if not allow_excluded or excluded_kept >= 4:
                    return None
                excluded_kept += 1

        seen_titles.add(title_key)
        if norm_url:
            seen_urls.add(norm_url)

        eff_pub_raw = pub_raw
        if not eff_pub_raw and link_url.startswith("http"):
            # Never make synchronous per-link HTTP date fetches inside topic_html loops
            eff_pub_raw = extract_date_from_card_or_url(dom_tag, link_url, now_npt, allow_http_fetch=False)
        pub_dt, rel_time, exact_time = parse_to_nepal_time(eff_pub_raw, now_npt)

        rec = _build_indian_article_record(
            src=src,
            raw_title=clean_title,
            summary_text=summary_text,
            link_url=link_url,
            pub_dt=pub_dt,
            rel_time=rel_time,
            exact_time=exact_time,
            rel_eval=rel_eval,
        )
        if is_precision_search:
            rec["_precision_search"] = True
        items.append(rec)
        return rel_eval["relevance_status"]

    def _ingest_rss_feed(
        rss_url: str,
        max_entries: int = 60,
        allow_excluded: bool = True,
        is_bing: bool = False,
        is_precision_search: bool = False,
    ) -> int:
        req = urllib.request.Request(rss_url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=7.0) as resp:
            feed = feedparser.parse(resp.read())
        added = 0
        for e in feed.entries[:max_entries]:
            raw_t = (e.get("title") or "").strip()
            strip_pat = r"\s*[-–|]\s*[^-–|]+$" if is_bing else r"\s*-\s*[^-]+$"
            clean_t = re.sub(strip_pat, "", raw_t).strip() or raw_t
            st = _try_append_candidate(
                raw_title=clean_t,
                summary_raw=e.get("summary", "") or e.get("description", ""),
                raw_link=e.get("link", "#"),
                pub_raw=e.get("published", "") or e.get("updated", ""),
                allow_excluded=allow_excluded,
                is_precision_search=is_precision_search,
            )
            if st is not None:
                added += 1
        return added

    src_type = src.get("type", "search_rss")
    is_search_first = src_type in ("bing_rss", "search_rss")

    if src_type == "rss":
        for rss_u in [src["url"]] + list(src.get("alt_urls") or []):
            try:
                _ingest_rss_feed(rss_u, max_entries=60, allow_excluded=True, is_bing=False)
            except Exception as exc:
                err_s = format_exc(exc, 180)
                errors_seen.append(err_s)
                logger.warning(f"Indian RSS failed [{src['name']}] ({rss_u}): {err_s}")
    elif not is_search_first:
        try:
            req = urllib.request.Request(src["url"], headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=7.0) as resp:
                data = resp.read()
            soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
            for nav_tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
                nav_tag.decompose()

            # Collect & sort candidates by URL freshness before applying the substantive >= 20 cap
            raw_anchors = []
            for dom_idx, a in enumerate(soup.find_all("a", href=True)):
                anc_classes = " ".join(" ".join(p.get("class") or []) for p in a.parents if hasattr(p, "get")).lower()
                if any(bad in anc_classes for bad in ("sidebar", "trending", "popular", "most-read", "widget", "navbar", "footer")):
                    continue
                heading_el = a.find(["h1", "h2", "h3", "h4"])
                p_inside = a.find("p")
                if heading_el and heading_el.get_text(strip=True):
                    txt = heading_el.get_text(" ", strip=True)
                elif p_inside and p_inside.get_text(strip=True):
                    p_txt = p_inside.get_text(" ", strip=True)
                    full_a_txt = a.get_text(" ", strip=True)
                    txt = full_a_txt.replace(p_txt, "").strip() or full_a_txt
                else:
                    txt = a.get_text(" ", strip=True)
                if len(txt) <= 22:
                    continue

                card_snippet = ""
                if p_inside and p_inside.get_text(strip=True):
                    card_snippet = p_inside.get_text(" ", strip=True)
                else:
                    parent_card = a.find_parent(["article", "li", "div"])
                    if parent_card:
                        p_tag = parent_card.find("p")
                        if p_tag:
                            card_snippet = p_tag.get_text(" ", strip=True)

                href_val = _unwrap_bing_link(a["href"], src["url"])
                raw_anchors.append((a, txt, card_snippet, href_val, dom_idx))

            raw_anchors.sort(key=lambda c: _indian_anchor_date_sort_key(c, now_npt))
            subst_count = 0
            for a, txt, card_snippet, href_val, _dom_idx in raw_anchors:
                st = _try_append_candidate(
                    raw_title=txt,
                    summary_raw=card_snippet,
                    raw_link=href_val,
                    pub_raw=None,
                    allow_excluded=True,
                    dom_tag=a,
                )
                if st == "substantive":
                    subst_count += 1
                    if subst_count >= 20:
                        break
        except Exception as exc:
            err_s = format_exc(exc, 180)
            errors_seen.append(err_s)
            logger.warning(f"Indian topic_html failed [{src['name']}] ({src['url']}): {err_s}")

    # Always run precision intitle: Bing News RSS unconditionally (removes stale 72h gate).
    # Note: bare `site:{dom} intitle:Nepal` preserves Bing's intitle: precision (parenthesized OR breaks Bing intitle:).
    dom = (src.get("domain") or urllib.parse.urlparse(src["url"]).netloc.lower().lstrip("www.")).strip()
    is_hi = src.get("lang") == "Hindi"
    mkt = "hi-IN" if is_hi else "en-IN"
    primary_kw = "नेपाल" if is_hi else "Nepal"
    secondary_kw = "काठमांडू" if is_hi else "Kathmandu"
    bing_added = 0
    try:
        q_prim = f"site:{dom} intitle:{primary_kw}"
        bing_url = f"https://www.bing.com/news/search?q={urllib.parse.quote(q_prim)}&qft=sortbydate%3d%221%22&format=rss&mkt={mkt}"
        bing_added += _ingest_rss_feed(bing_url, max_entries=15, allow_excluded=False, is_bing=True, is_precision_search=True)
    except Exception as exc:
        err_s = format_exc(exc, 180)
        errors_seen.append(err_s)
        logger.warning(f"Indian Bing intitle RSS failed [{src['name']}]: {err_s}")

    if is_search_first and bing_added < 4:
        try:
            q_sec = f"site:{dom} intitle:{secondary_kw}"
            bing_url_2 = f"https://www.bing.com/news/search?q={urllib.parse.quote(q_sec)}&qft=sortbydate%3d%221%22&format=rss&mkt={mkt}"
            _ingest_rss_feed(bing_url_2, max_entries=10, allow_excluded=False, is_bing=True, is_precision_search=True)
        except Exception as exc:
            logger.debug(f"Indian Bing secondary intitle RSS failed [{src['name']}]: {format_exc(exc, 140)}")

    if hydrate_bodies and items:
        try:
            relevant_items = [
                x for x in items
                if x.get("relevance_status") != "excluded" or x.get("_precision_search")
            ]
            if relevant_items:
                batch_fetch_full_content(relevant_items[:18], max_workers=10, summarize_english=False)
                for x in relevant_items[:18]:
                    fc = (x.get("full_content") or "").strip()
                    if len(fc) > 120:
                        re_eval = evaluate_indian_article_nepal_relevance(
                            title=x.get("title", ""),
                            summary=x.get("summary", ""),
                            full_content=fc,
                            link=x.get("link", ""),
                            source=x.get("source", ""),
                            threshold=relevance_threshold,
                        )
                        if re_eval["nepal_relevance_score"] > float(x.get("nepal_relevance_score", 0.0)):
                            _apply_indian_eval(x, re_eval)
        except Exception as exc:
            logger.warning(f"Indian body hydration error [{src['name']}]: {format_exc(exc, 160)}")

    if metrics_out is not None:
        metrics_out.update({
            "source_name": src["name"],
            "source_type": src_type,
            "domain": dom,
            "language": src.get("lang", "English"),
            "discovered": len(items),
            "substantive": sum(1 for x in items if x.get("relevance_status") == "substantive"),
            "borderline": sum(1 for x in items if x.get("relevance_status") == "borderline_review"),
            "excluded": sum(1 for x in items if x.get("relevance_status") == "excluded"),
            "latency_secs": round(time.time() - t0, 3),
            "error": "; ".join(errors_seen)[:300],
        })
    return items


def fetch_nepal_in_indian_media(
    max_workers: int = 16,
    relevance_threshold: float = DEFAULT_NEPAL_RELEVANCE_THRESHOLD,
    include_borderline: bool = False,
    force_refresh: bool = False,
    return_all_stored: bool = True,
    on_progress=None,
):
    """
    Fetches real-time Nepal news across Top Indian Media Outlets using decoupled fast discovery:
      1. Concurrent per-outlet precision intitle: Bing RSS (+ live topic_html) with max_workers=16.
      2. Batched locale-aware Google News RSS sweeps (when:3d, 5 domains/query) with URL decoding.
      3. Selective full-text hydration ONLY for net-new canonical_ids not already hydrated in Supabase.
      4. Persists all candidates to `indian_media_articles` and per-outlet telemetry to `indian_source_health`.
    """
    now_npt = datetime.datetime.now(NEPAL_TZ)
    if not force_refresh:
        try:
            stored_ind = get_stored_indian_articles(
                status_filter=None if include_borderline else "substantive",
                min_score=BORDERLINE_NEPAL_RELEVANCE_FLOOR if include_borderline else relevance_threshold,
                limit=250,
            )
            if len(stored_ind) >= 3:
                for sa in stored_ind:
                    pdt = sa.get("published_dt")
                    if isinstance(pdt, datetime.datetime):
                        _, sa["relative_time"], sa["exact_time"] = parse_to_nepal_time(pdt, now_npt)
                stored_ind.sort(key=lambda x: x["published_dt"] if isinstance(x["published_dt"], datetime.datetime) else now_npt, reverse=True)
                return stored_ind
        except Exception as exc:
            logger.warning(f"Stored Indian articles fast-path failed: {format_exc(exc, 160)}")

    eff_workers = max(16, int(max_workers or 16))
    raw_candidates: List[Dict[str, Any]] = []
    metrics_by_source: Dict[str, Dict[str, Any]] = {
        s["name"]: {
            "source_name": s["name"],
            "source_type": s.get("type", "search_rss"),
            "domain": s.get("domain", ""),
            "language": s.get("lang", "English"),
            "discovered": 0,
            "substantive": 0,
            "borderline": 0,
            "excluded": 0,
            "latency_secs": 0.0,
            "error": "",
        }
        for s in TOP_INDIAN_MEDIA_SOURCES
    }

    # Phase 1: Fast concurrent per-outlet discovery (no full-body scraping yet!)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=eff_workers)
    try:
        future_to_src = {}
        for s in TOP_INDIAN_MEDIA_SOURCES:
            m_slot = metrics_by_source[s["name"]]
            future_to_src[
                executor.submit(
                    fetch_single_indian_media,
                    s,
                    now_npt,
                    relevance_threshold,
                    False,  # hydrate_bodies=False: decoupled selective hydration runs in Phase 3
                    m_slot,
                )
            ] = s["name"]
        try:
            for f in concurrent.futures.as_completed(future_to_src, timeout=30.0):
                sname = future_to_src[f]
                try:
                    res = f.result(timeout=3.0)
                    if res:
                        raw_candidates.extend(res)
                        if on_progress is not None:
                            try:
                                on_progress(len(raw_candidates))
                            except Exception:
                                pass
                except Exception as exc:
                    err_s = format_exc(exc, 200)
                    metrics_by_source[sname]["error"] = err_s
                    logger.warning(f"Indian outlet worker failed [{sname}]: {err_s}")
        except concurrent.futures.TimeoutError:
            timed_out = [name for fut, name in future_to_src.items() if not fut.done()]
            for tname in timed_out:
                metrics_by_source[tname]["error"] = "Timed out after 30s"
            if timed_out:
                logger.warning(f"Indian per-outlet discovery timed out on {len(timed_out)} outlet(s): {', '.join(timed_out[:6])}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    # Phase 2: Batched locale-aware Google News RSS sweeps (when:3d) for net-new discoveries
    existing_title_keys = {
        (a.get("source", ""), _norm_title_key(a.get("title", "")))
        for a in raw_candidates
        if a.get("title")
    }
    try:
        gnews_items = _fetch_batched_google_news_indian_media(
            TOP_INDIAN_MEDIA_SOURCES,
            now_npt=now_npt,
            relevance_threshold=relevance_threshold,
            existing_title_keys=existing_title_keys,
            batch_size=5,
            max_decode_urls=60,
        )
        seen_norm_urls = {normalize_canonical_url(a.get("link", "")) for a in raw_candidates if a.get("link")}
        for ga in gnews_items:
            nu = normalize_canonical_url(ga.get("link", ""))
            if nu and nu in seen_norm_urls:
                continue
            if nu:
                seen_norm_urls.add(nu)
            raw_candidates.append(ga)
            ms = metrics_by_source.get(ga.get("source", ""))
            if ms is not None:
                ms["discovered"] += 1
                st = ga.get("relevance_status")
                if st == "substantive":
                    ms["substantive"] += 1
                elif st == "borderline_review":
                    ms["borderline"] += 1
                else:
                    ms["excluded"] += 1
    except Exception as exc:
        logger.warning(f"Batched Google News Indian sweep failed: {format_exc(exc, 180)}")

    # Phase 3: Selective full-text hydration ONLY for net-new (not yet hydrated) substantive/borderline items
    if raw_candidates:
        try:
            cand_for_hydrate = [
                a for a in raw_candidates
                if a.get("relevance_status") != "excluded" or a.get("_precision_search")
            ]
            already_hydrated = get_existing_indian_hydrated_ids(
                [a.get("canonical_id", "") for a in cand_for_hydrate]
            )
            net_new_to_hydrate = [
                a for a in cand_for_hydrate
                if a.get("canonical_id") not in already_hydrated
                and "news.google.com" not in (a.get("link") or "").lower()
            ]
            # Prioritize newest items first, cap per cycle to stay fast
            net_new_to_hydrate.sort(
                key=lambda x: x["published_dt"] if isinstance(x.get("published_dt"), datetime.datetime) else now_npt,
                reverse=True,
            )
            hydrate_batch = net_new_to_hydrate[:40]
            if hydrate_batch:
                batch_fetch_full_content(hydrate_batch, max_workers=12, summarize_english=False)
                for x in hydrate_batch:
                    fc = (x.get("full_content") or "").strip()
                    if len(fc) > 120:
                        re_eval = evaluate_indian_article_nepal_relevance(
                            title=x.get("title", ""),
                            summary=x.get("summary", ""),
                            full_content=fc,
                            link=x.get("link", ""),
                            source=x.get("source", ""),
                            threshold=relevance_threshold,
                        )
                        if re_eval["nepal_relevance_score"] > float(x.get("nepal_relevance_score", 0.0)):
                            _apply_indian_eval(x, re_eval)
        except Exception as exc:
            logger.warning(f"Indian selective hydration failed: {format_exc(exc, 180)}")

    # Strip internal scratch flag before persisting
    for a in raw_candidates:
        a.pop("_precision_search", None)

    # Persist all candidate Indian articles (substantive, borderline_review, excluded) in central DB
    if raw_candidates:
        try:
            ingest_indian_articles_batch(raw_candidates)
        except Exception as exc:
            logger.warning(f"ingest_indian_articles_batch failed: {format_exc(exc, 180)}")

    # Record per-outlet Indian discovery health telemetry (UTC-aware)
    try:
        record_indian_source_health(list(metrics_by_source.values()))
    except Exception as exc:
        logger.warning(f"record_indian_source_health failed: {format_exc(exc, 180)}")

    if not return_all_stored:
        return raw_candidates

    # Filter strictly by the Nepal-relevance confidence threshold before displaying in feed
    seen_links = set()
    filtered_feed = []
    for art in raw_candidates:
        score = float(art.get("nepal_relevance_score", 0.0))
        status = art.get("relevance_status", "excluded")
        norm_url = normalize_canonical_url(art.get("link", "")) or art.get("title", "")
        if norm_url in seen_links:
            continue

        if score >= relevance_threshold or (include_borderline and status == "borderline_review"):
            seen_links.add(norm_url)
            filtered_feed.append(art)

    # Reconcile with stored substantive Indian articles in Supabase so previously discovered valid stories persist
    try:
        stored_substantive = get_stored_indian_articles(
            status_filter=None if include_borderline else "substantive",
            min_score=BORDERLINE_NEPAL_RELEVANCE_FLOOR if include_borderline else relevance_threshold,
            limit=250,
        )
        for sa in stored_substantive:
            re_eval = evaluate_indian_article_nepal_relevance(
                title=sa.get("title", ""),
                summary=sa.get("summary", ""),
                full_content=sa.get("full_content", ""),
                link=sa.get("link", ""),
                source=sa.get("source", ""),
                threshold=relevance_threshold,
            )
            _apply_indian_eval(sa, re_eval)

            if sa["nepal_relevance_score"] < (BORDERLINE_NEPAL_RELEVANCE_FLOOR if include_borderline else relevance_threshold):
                continue

            norm_url = normalize_canonical_url(sa.get("link", "")) or sa.get("title", "")
            if norm_url not in seen_links:
                seen_links.add(norm_url)
                filtered_feed.append(sa)
    except Exception as exc:
        logger.warning(f"Indian feed DB reconciliation failed: {format_exc(exc, 180)}")

    filtered_feed.sort(
        key=lambda x: x["published_dt"] if isinstance(x.get("published_dt"), datetime.datetime) else now_npt,
        reverse=True,
    )
    return filtered_feed


