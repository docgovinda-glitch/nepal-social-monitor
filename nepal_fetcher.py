"""
nepal_fetcher.py
High-performance news & social media fetcher for Nepal.
1. Monitors 34 leading online newspapers and digital portals in Nepal (both Nepali and English).
2. Classifies content under 8 structured geo-political categories.
3. Dedicated monitoring of Nepal coverage across Top Indian Media (English & Hindi).
"""

import os
import datetime
import zoneinfo
import urllib.request
import urllib.parse
import ssl
import concurrent.futures
import re
import html
import json
from typing import Dict, Any, List, Optional
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
    get_indian_media_audit_stats
)

# Default configurable Nepal relevance confidence threshold for Indian Media feed
DEFAULT_NEPAL_RELEVANCE_THRESHOLD = float(os.getenv("INDIA_MEDIA_RELEVANCE_THRESHOLD", "0.65"))
BORDERLINE_NEPAL_RELEVANCE_FLOOR = 0.40


# Nepal Timezone (UTC +5:45)
NEPAL_TZ = zoneinfo.ZoneInfo("Asia/Kathmandu")
SSL_CTX = ssl._create_unverified_context()
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Full article news text in-memory cache
FULL_ARTICLE_TEXT_CACHE = {}
# Published date in-memory cache
ARTICLE_DATE_CACHE = {}

def extract_article_full_text(url: str, timeout: int = 8) -> str:
    """
    Extracts the complete news article body text from an article URL.
    Returns cleaned text with all article paragraphs separated by double newlines.
    """
    if not url or not url.startswith("http"):
        return ""
    if url in FULL_ARTICLE_TEXT_CACHE and len(FULL_ARTICLE_TEXT_CACHE[url]) > 600:
        return FULL_ARTICLE_TEXT_CACHE[url]

    try:
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(raw_html, "html.parser")
        
        # Strip script, styles, buttons, navigation, headers, footers, comments, and related widgets
        for tag in soup(["script", "style", "noscript", "svg", "button", "header", "footer", "nav", "form", "iframe"]):
            tag.decompose()
        for noisy in soup.select(
            ".comments, #comments, .comment-box, .comment-section, .related-news, .trending-news, "
            ".popular-news, .share-box, .social-share, .author-box, .login-box, .signup-box, "
            ".ok-conv-box, .post-navigation, .breadcrumb, .tags, .tag-list, .advertisement, .ad-box"
        ):
            noisy.decompose()
        for tag in soup.find_all("aside"):
            # Retain aside if it contains main content column (e.g. Setopati left-side)
            if not any(c in str(tag.get("class", [])) for c in ["left-side", "content", "main", "col-"]):
                tag.decompose()

        content_containers = soup.select(
            ".ok18-single-post-content-wrap, .editor-box, .detail-box, .story-content, .article-content, "
            ".entry-content, .post-content, .news-content, .detail-content, .story__content, "
            ".article__body, .news_detail, .full-content, .content-body, #content-body, "
            ".main-content, .story-section, .story-details, .news_description, .entry-content-wrap, "
            ".post-detail, .story-with-main-sec, article"
        )
        
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

        # Fallback to all paragraphs in the document
        if len(" ".join(paras)) < 250:
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
        ]
        skip_phrases = [
            "cookie policy", "privacy policy", "terms of service", "terms of use",
            "all rights reserved", "advertisement", "copyright ©", "download our app",
            "rights reserved", "subscribe to", "news summary generated by ok ai",
            "वा इमेल/सोसल मिडियामार्फत् लगइन",
        ]

        clean = []
        for p in paras:
            low = p.lower()
            if any(m in low for m in stop_markers):
                break
            if any(b in low for b in skip_phrases):
                continue
            clean.append(p)

        full_text = "\n\n".join(clean).strip()
        if full_text:
            FULL_ARTICLE_TEXT_CACHE[url] = full_text
            return full_text
    except Exception:
        pass
    return ""

def batch_fetch_full_content(articles: list, max_workers: int = 25) -> list:
    """
    Extracts the full news article body text for a list of articles in parallel.
    Populates 'full_content' on each article dictionary with the complete extracted news text.
    """
    to_fetch = []
    for art in articles:
        link = art.get("link", "")
        existing_fc = (art.get("full_content") or "").strip()
        summary = (art.get("summary") or "").strip()
        if link in FULL_ARTICLE_TEXT_CACHE and len(FULL_ARTICLE_TEXT_CACHE[link]) > max(len(existing_fc), 600):
            art["full_content"] = FULL_ARTICLE_TEXT_CACHE[link]
        elif link.startswith("http") and (len(existing_fc) < 700 or existing_fc == summary or "\n\n" not in existing_fc):
            to_fetch.append(art)

    if to_fetch:
        newly_enriched = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_art = {
                executor.submit(extract_article_full_text, a.get("link", "")): a
                for a in to_fetch
            }
            for fut in concurrent.futures.as_completed(future_to_art):
                a = future_to_art[fut]
                try:
                    extracted = fut.result()
                    existing_fc = (a.get("full_content") or a.get("summary") or "").strip()
                    if extracted and len(extracted) > len(existing_fc):
                        a["full_content"] = extracted
                        newly_enriched.append(a)
                    elif not a.get("full_content"):
                        a["full_content"] = existing_fc or a.get("title", "")
                except Exception:
                    if not a.get("full_content"):
                        a["full_content"] = a.get("summary") or a.get("title", "")
        if newly_enriched:
            try:
                from nepal_news_store import persist_enriched_full_content
                persist_enriched_full_content(newly_enriched)
            except Exception:
                pass
    return articles

# The 9 Structured Categories (Geographically and Thematically Organised)
STRUCTURED_CATEGORIES = [
    "India Section",
    "China Section",
    "Bangladesh Section",
    "Pakistan Section",
    "Nepal – Internal",
    "Nepal – External",
    "Nepal – Economy",
    "Nepal – Others",
    "International News"
]

CATEGORY_ICONS = {
    "India Section": "🇮🇳",
    "China Section": "🇨🇳",
    "Bangladesh Section": "🇧🇩",
    "Pakistan Section": "🇵🇰",
    "Nepal – Internal": "🇳🇵",
    "Nepal – External": "🌐",
    "Nepal – Economy": "📈",
    "Nepal – Others": "📌",
    "International News": "🌍"
}

# Curated Top 34 Nepal Online News Portals (Enriched with multi-channel feeds & adaptive intervals)
TOP_NEPAL_NEWS_PORTALS = [
    # Top Nepali Mainstream Daily & Digital Portals (22)
    {"name": "eKantipur", "type": "html", "url": "https://ekantipur.com/", "alt_urls": ["https://ekantipur.com/news", "https://ekantipur.com/national", "https://ekantipur.com/business"], "lang": "Nepali", "category": "National Daily", "priority": "high", "check_interval_mins": 8},
    {"name": "OnlineKhabar (NP)", "type": "rss", "url": "https://www.onlinekhabar.com/feed", "alt_urls": ["https://www.onlinekhabar.com/content/news/feed"], "lang": "Nepali", "category": "General News", "priority": "high", "check_interval_mins": 8},
    {"name": "Setopati", "type": "rss", "url": "https://www.setopati.com/feed", "alt_urls": ["https://www.setopati.com/politics/feed"], "lang": "Nepali", "category": "National", "priority": "high", "check_interval_mins": 8},
    {"name": "Ratopati", "type": "rss", "url": "https://www.ratopati.com/feed", "alt_urls": ["https://www.ratopati.com/category/politics/feed"], "lang": "Nepali", "category": "Breaking News", "priority": "high", "check_interval_mins": 8},
    {"name": "Annapurna Post", "type": "rss", "url": "https://annapurnapost.com/rss", "alt_urls": ["https://annapurnapost.com/rss/desh"], "lang": "Nepali", "category": "National Daily", "priority": "high", "check_interval_mins": 8},
    {"name": "Nagarik News", "type": "rss", "url": "https://nagariknews.nagariknetwork.com/feed", "alt_urls": [], "lang": "Nepali", "category": "National Daily", "priority": "high", "check_interval_mins": 8},
    {"name": "Naya Patrika", "type": "html", "url": "https://www.nayapatrikadaily.com/", "alt_urls": ["https://www.nayapatrikadaily.com/rss"], "lang": "Nepali", "category": "National Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "NepalKhabar", "type": "rss", "url": "https://nepalkhabar.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Digital Daily", "priority": "high", "check_interval_mins": 8},
    {"name": "Gorkhapatra Online", "type": "rss", "url": "https://gorkhapatraonline.com/rss", "alt_urls": [], "lang": "Nepali", "category": "National / State", "priority": "standard", "check_interval_mins": 18},
    {"name": "News of Nepal", "type": "rss", "url": "https://newsofnepal.com/feed", "alt_urls": [], "lang": "Nepali", "category": "National Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "Nepal Press", "type": "rss", "url": "https://www.nepalpress.com/feed/", "alt_urls": [], "lang": "Nepali", "category": "Digital News", "priority": "standard", "check_interval_mins": 18},
    {"name": "Baahrakhari", "type": "rss", "url": "https://baahrakhari.com/feed", "alt_urls": [], "lang": "Nepali", "category": "National", "priority": "standard", "check_interval_mins": 18},
    {"name": "Himal Press", "type": "rss", "url": "https://himalpress.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Politics & In-depth", "priority": "standard", "check_interval_mins": 18},
    {"name": "Deshsanchar", "type": "rss", "url": "https://deshsanchar.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Current Affairs", "priority": "standard", "check_interval_mins": 18},
    {"name": "Shilapatra", "type": "rss", "url": "https://shilapatra.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Opinion & Society", "priority": "standard", "check_interval_mins": 18},
    {"name": "Nepal Live", "type": "rss", "url": "https://nepallive.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Politics", "priority": "standard", "check_interval_mins": 18},
    {"name": "Nepal Aaja", "type": "html", "url": "https://nepalaaja.com/", "alt_urls": [], "lang": "Nepali", "category": "Digital Media", "priority": "standard", "check_interval_mins": 18},
    {"name": "Nepal News", "type": "rss", "url": "https://nepalnews.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Digital Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "Image Khabar", "type": "rss", "url": "https://imagekhabar.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Digital Media", "priority": "standard", "check_interval_mins": 18},
    {"name": "Khabarhub (NP)", "type": "rss", "url": "https://khabarhub.com/feed/", "alt_urls": [], "lang": "Nepali", "category": "Current Affairs", "priority": "standard", "check_interval_mins": 18},
    {"name": "TechPana", "type": "rss", "url": "https://techpana.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Tech & Innovation", "priority": "low", "check_interval_mins": 40},
    {"name": "ArthaSarokar", "type": "rss", "url": "https://arthasarokar.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Economy & Banking", "priority": "low", "check_interval_mins": 40},

    # Top English Mainstream Daily & Digital Portals (12)
    {"name": "The Kathmandu Post", "type": "rss", "url": "https://kathmandupost.com/rss", "alt_urls": ["https://kathmandupost.com/national/rss", "https://kathmandupost.com/money/rss"], "lang": "English", "category": "National Daily", "priority": "high", "check_interval_mins": 8},
    {"name": "The Himalayan Times", "type": "html", "url": "https://thehimalayantimes.com/", "alt_urls": ["https://thehimalayantimes.com/nepal"], "lang": "English", "category": "National Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "MyRepublica", "type": "rss", "url": "https://myrepublica.nagariknetwork.com/feeds", "alt_urls": [], "lang": "English", "category": "National Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "OnlineKhabar (EN)", "type": "rss", "url": "https://english.onlinekhabar.com/feed", "alt_urls": [], "lang": "English", "category": "National", "priority": "standard", "check_interval_mins": 18},
    {"name": "The Annapurna Express", "type": "rss", "url": "https://theannapurnaexpress.com/rss", "alt_urls": [], "lang": "English", "category": "Weekly In-depth", "priority": "low", "check_interval_mins": 40},
    {"name": "Setopati (EN)", "type": "html", "url": "https://en.setopati.com/", "alt_urls": [], "lang": "English", "category": "National", "priority": "standard", "check_interval_mins": 18},
    {"name": "Rising Nepal Daily", "type": "rss", "url": "https://risingnepaldaily.com/rss", "alt_urls": [], "lang": "English", "category": "National Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "NepalKhabar (EN)", "type": "html", "url": "https://en.nepalkhabar.com/", "alt_urls": ["https://en.nepalkhabar.com/rss"], "lang": "English", "category": "Digital Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "Ratopati (EN)", "type": "rss", "url": "https://english.ratopati.com/feed", "alt_urls": [], "lang": "English", "category": "Current Affairs", "priority": "standard", "check_interval_mins": 18},
    {"name": "Khabarhub (EN)", "type": "rss", "url": "https://english.khabarhub.com/feed/", "alt_urls": [], "lang": "English", "category": "National", "priority": "standard", "check_interval_mins": 18},
    {"name": "Nepali Times", "type": "rss", "url": "https://nepalitimes.com/feed", "alt_urls": [], "lang": "English", "category": "Independent Journalism", "priority": "low", "check_interval_mins": 40},
    {"name": "Nepal News (EN)", "type": "rss", "url": "https://english.nepalnews.com/feed", "alt_urls": [], "lang": "English", "category": "Digital Daily", "priority": "standard", "check_interval_mins": 18},
]

# Top Prominent Indian Media Outlets covering Nepal (18 Prominent Outlets)
TOP_INDIAN_MEDIA_SOURCES = [
    # Premier National English Dailies
    {"name": "The Indian Express", "type": "topic_html", "url": "https://indianexpress.com/about/nepal/", "lang": "English", "desc": "Premier investigative & political national daily"},
    {"name": "The Hindu", "type": "rss", "url": "https://www.thehindu.com/news/international/feeder/default.rss", "lang": "English", "desc": "Premier broadsheet for diplomacy & foreign affairs"},
    {"name": "The Tribune", "type": "topic_html", "url": "https://www.tribuneindia.com/topic/nepal", "lang": "English", "desc": "Northern national daily covering Gorkha regiments & Himalayan borders"},

    # Global TV & Broadcast News Networks
    {"name": "India Today", "type": "topic_html", "url": "https://www.indiatoday.in/topic/nepal", "lang": "English", "desc": "Premier national broadcast & digital newsroom"},
    {"name": "ABP Live", "type": "topic_html", "url": "https://news.abplive.com/topic/nepal", "lang": "English", "desc": "Major national broadcast network covering South Asian politics"},
    {"name": "NDTV", "type": "rss", "url": "https://feeds.feedburner.com/ndtvnews-world-news", "lang": "English", "desc": "Leading national broadcast & digital news network"},

    # Financial & Trade Dailies
    {"name": "Livemint", "type": "topic_html", "url": "https://www.livemint.com/topic/nepal", "lang": "English", "desc": "Premier business daily covering bilateral trade & energy"},
    {"name": "Business Standard", "type": "topic_html", "url": "https://www.business-standard.com/topic/nepal", "lang": "English", "desc": "Leading financial daily covering treaties & hydropower"},
    {"name": "Financial Express", "type": "topic_html", "url": "https://www.financialexpress.com/about/nepal/", "lang": "English", "desc": "Leading financial daily covering bilateral investment & infrastructure"},
    {"name": "Moneycontrol", "type": "topic_html", "url": "https://www.moneycontrol.com/news/tags/nepal.html", "lang": "English", "desc": "Network18 premier financial portal covering cross-border markets"},

    # Strategic Analysis & Digital Journalism
    {"name": "Outlook India", "type": "topic_html", "url": "https://www.outlookindia.com/topic/nepal", "lang": "English", "desc": "Premier current affairs & political analysis journal"},
    {"name": "The Quint", "type": "topic_html", "url": "https://www.thequint.com/topic/nepal", "lang": "English", "desc": "Independent digital journalism & South Asia fact-checking"},
    {"name": "Swarajya", "type": "topic_html", "url": "https://swarajyamag.com/topic/nepal", "lang": "English", "desc": "Strategic affairs, defense & Himalayan geopolitics analysis"},
    {"name": "OneIndia", "type": "topic_html", "url": "https://www.oneindia.com/topic/nepal", "lang": "English", "desc": "Major digital news network covering regional developments"},

    # High-Circulation Hindi National & Border Dailies
    {"name": "Amar Ujala", "type": "topic_html", "url": "https://www.amarujala.com/tags/nepal", "lang": "Hindi", "desc": "Leading Hindi daily covering UP/Uttarakhand-Nepal border"},
    {"name": "Live Hindustan", "type": "topic_html", "url": "https://www.livehindustan.com/tags/nepal/", "lang": "Hindi", "desc": "Hindustan Times Media premier Hindi daily"},
    {"name": "Jansatta", "type": "topic_html", "url": "https://www.jansatta.com/about/nepal/", "lang": "Hindi", "desc": "Indian Express Group leading Hindi national daily"},
    {"name": "Prabhat Khabar", "type": "topic_html", "url": "https://www.prabhatkhabar.com/topic/nepal", "lang": "Hindi", "desc": "Leading Hindi daily covering Bihar-Nepal border region"}
]

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

def parse_snippet_to_datetime(raw_text: str, now_npt: datetime.datetime):
    """Extracts a genuine datetime from a short text snippet, relative phrase, or Nepali byline."""
    if not raw_text:
        return None
    txt = raw_text.strip()
    
    # 1. Normalize Devanagari numerals to ASCII digits
    norm_txt = txt.translate(NEP_DEVANAGARI_DIGITS)

    # 2. Match Nepali relative date phrases (e.g., २ घण्टा अघि, १५ मिनेट अघि, ३ दिन अघि)
    m_nep_rel = re.search(r'(\d+)\s*(?:घण्टा|घन्टा|hr|hours?)\s*अघि', norm_txt)
    if m_nep_rel:
        return now_npt - datetime.timedelta(hours=int(m_nep_rel.group(1)))
    m_nep_min = re.search(r'(\d+)\s*(?:मिनेट|min|minutes?)\s*अघि', norm_txt)
    if m_nep_min:
        return now_npt - datetime.timedelta(minutes=int(m_nep_min.group(1)))
    m_nep_day = re.search(r'(\d+)\s*(?:दिन|days?)\s*अघि', norm_txt)
    if m_nep_day:
        return now_npt - datetime.timedelta(days=int(m_nep_day.group(1)))
    m_nep_week = re.search(r'(\d+)\s*(?:हप्ता|साता|weeks?)\s*अघि', norm_txt)
    if m_nep_week:
        return now_npt - datetime.timedelta(days=int(m_nep_week.group(1)) * 7)
    m_nep_month = re.search(r'(\d+)\s*(?:महिना|months?)\s*अघि', norm_txt)
    if m_nep_month:
        return now_npt - datetime.timedelta(days=int(m_nep_month.group(1)) * 30)
    m_nep_year = re.search(r'(\d+)\s*(?:वर्ष|बर्ष|years?)\s*अघि', norm_txt)
    if m_nep_year:
        return now_npt - datetime.timedelta(days=int(m_nep_year.group(1)) * 365)
    m_nep_sec = re.search(r'(\d+)\s*(?:सेकेन्ड|सेकेण्ड|sec|seconds?)\s*अघि', norm_txt)
    if m_nep_sec:
        return now_npt - datetime.timedelta(seconds=int(m_nep_sec.group(1)))
    if re.search(r'\bहिजो\b', norm_txt):
        return now_npt - datetime.timedelta(days=1)
    if re.search(r'\bअस्ति\b', norm_txt):
        return now_npt - datetime.timedelta(days=2)

    # 3. Match English relative date phrases
    rel = REL_DATE_REGEX.search(norm_txt)
    if rel:
        v = int(rel.group(1))
        u = rel.group(2).lower()
        if "sec" in u: return now_npt - datetime.timedelta(seconds=v)
        if "min" in u: return now_npt - datetime.timedelta(minutes=v)
        if "hr" in u or "hour" in u: return now_npt - datetime.timedelta(hours=v)
        if "day" in u: return now_npt - datetime.timedelta(days=v)
        if "week" in u: return now_npt - datetime.timedelta(days=v * 7)
        if "month" in u: return now_npt - datetime.timedelta(days=v * 30)

    # 4. Match Nepali Bikram Sambat dates (e.g. कात्तिक २४, २०८३ or २४ कार्तिक २०८३)
    bs_month_idx_map = {
        'बैशाख': 1, 'वैशाख': 1, 'जेठ': 2, 'असार': 3, 'साउन': 4, 'श्रावण': 4, 'भदौ': 5, 'भाद्र': 5,
        'असोज': 6, 'आश्विन': 6, 'कार्तिक': 7, 'कात्तिक': 7, 'मंसिर': 8,
        'पुस': 9, 'पुष': 9, 'पौष': 9, 'माघ': 10, 'फागुन': 11, 'फाल्गुन': 11, 'चैत': 12, 'चैत्र': 12
    }
    for m_name, m_idx in bs_month_idx_map.items():
        if m_name in norm_txt:
            m_bs = re.search(rf'(?:{m_name}\s+(\d{{1,2}})|(\d{{1,2}})\s+{m_name},?)(?:,?\s*(20\d{{2}}))?(?:[^\d]+(\d{{1,2}}):(\d{{2}})(?::(\d{{2}}))?)?', norm_txt)
            if m_bs:
                day_val = int(m_bs.group(1) or m_bs.group(2))
                bs_year = int(m_bs.group(3)) if m_bs.group(3) else 2083
                hr = int(m_bs.group(4)) if m_bs.group(4) else 12
                mn = int(m_bs.group(5)) if m_bs.group(5) else 0
                sc = int(m_bs.group(6)) if m_bs.group(6) else 0
                # Reference anchor: 25 Kartik 2083 BS = Nov 11, 2026
                year_diff_days = (2083 - bs_year) * 365
                month_diff_days = (7 - m_idx) * 30
                day_diff = year_diff_days + month_diff_days + (25 - day_val)
                if day_diff >= 0:
                    cand_dt = now_npt - datetime.timedelta(days=day_diff)
                    return cand_dt.replace(hour=hr, minute=mn, second=sc, microsecond=0)
                else:
                    return now_npt.replace(hour=hr, minute=mn, second=sc, microsecond=0)

    # 5. Clean common formatting artifacts
    clean_txt = re.sub(r"\[IST\]|IST", "+0530", norm_txt)
    clean_txt = re.sub(r"Updated\s*:\s*|Updated On\s*:\s*|Published\s*:\s*|Published Date\s*:\s*|By[^\d]+", "", clean_txt)
    clean_txt = re.sub(r"^[A-Za-z]+(?=\d{2}\s+[A-Za-z]{3}\s+\d{4})", "", clean_txt)
    clean_txt = re.sub(r"([A-Za-z]{3})\.", r"\1", clean_txt)
    clean_txt = clean_txt.replace("p.m.", "PM").replace("a.m.", "AM").replace("|", " ")

    # 6. Check standard regexes
    for rgx in DATE_SNIPPET_REGEXES:
        m = rgx.search(clean_txt)
        if m:
            try:
                dt = dt_parser.parse(m.group(0), fuzzy=True)
                return dt.astimezone(NEPAL_TZ) if dt.tzinfo else dt.replace(tzinfo=NEPAL_TZ)
            except Exception:
                pass
    return None

def extract_date_from_card_or_url(a_tag, href: str, now_npt: datetime.datetime):
    """
    Extracts real publication datetime for an HTML article card:
    1. Memory cache check.
    2. Parent DOM container inspection (up to 6 levels: <time>, date classes, timestamps).
    3. URL path pattern extraction (/YYYY/MM/DD/ or -YYYY-MM-DD-).
    4. Fast article page <meta> tag retrieval (og:article:published_time, datePublished).
    """
    if not href:
        return None
    if href in ARTICLE_DATE_CACHE:
        return ARTICLE_DATE_CACHE[href]

    # 1. Inspect DOM ancestors
    curr = a_tag.parent if a_tag else None
    for _ in range(6):
        if not curr or curr.name in ["body", "html", "header", "nav"]:
            break
        curr_classes = " ".join(curr.get("class") or []).lower()
        if any(bad in curr_classes for bad in ["navbar", "search-overlay", "header", "masthead", "topbar", "footer"]):
            break
        time_tag = curr.find("time")
        if time_tag:
            dt = parse_snippet_to_datetime(time_tag.get("datetime") or time_tag.get_text(strip=True), now_npt)
            if dt:
                ARTICLE_DATE_CACHE[href] = dt
                return dt

        date_elems = curr.find_all(class_=re.compile(r"date|time|meta|updated|publish|oi-article-country|byline", re.I))
        for de in date_elems:
            de_cls = " ".join(de.get("class") or []).lower()
            if any(bad in de_cls for bad in ["navbar", "header", "epaper", "current-date", "today"]):
                continue
            dt = parse_snippet_to_datetime(de.get_text(" ", strip=True), now_npt)
            if dt:
                ARTICLE_DATE_CACHE[href] = dt
                return dt

        for el in curr.find_all(["p", "span", "small"]):
            el_cls = " ".join(el.get("class") or []).lower()
            if any(bad in el_cls for bad in ["navbar", "header", "epaper", "current-date"]):
                continue
            t = el.get_text(" ", strip=True)
            if t and len(t) < 80:
                dt = parse_snippet_to_datetime(t, now_npt)
                if dt:
                    ARTICLE_DATE_CACHE[href] = dt
                    return dt

        curr = curr.parent

    # 2. Check URL patterns
    m_url = re.search(r"/(202[0-9])[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])", href)
    if m_url:
        dt = datetime.datetime(int(m_url.group(1)), int(m_url.group(2)), int(m_url.group(3)), 12, 0, tzinfo=NEPAL_TZ)
        ARTICLE_DATE_CACHE[href] = dt
        return dt

    m_url2 = re.search(r"-(202[0-9])-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])", href)
    if m_url2:
        dt = datetime.datetime(int(m_url2.group(1)), int(m_url2.group(2)), int(m_url2.group(3)), 12, 0, tzinfo=NEPAL_TZ)
        ARTICLE_DATE_CACHE[href] = dt
        return dt

    # 3. Lightweight meta tag check for article pages if URL is HTTP
    if href.startswith("http"):
        try:
            req = urllib.request.Request(href, headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=2.5) as resp:
                chunk = resp.read(120000).decode("utf-8", errors="ignore")
            m_meta = re.search(r"<meta[^>]+(?:article:published_time|datePublished|publish-date|published_time)[^>]+content=[\"\x27]([^\x27\"]+)[\"\x27]", chunk, re.I)
            if not m_meta:
                m_meta = re.search(r"\"(?:datePublished|dateCreated|published_time)\"\s*:\s*\"([^\"]+)\"", chunk)
            if m_meta:
                dt = dt_parser.parse(m_meta.group(1), fuzzy=True)
                dt = dt.astimezone(NEPAL_TZ) if dt.tzinfo else dt.replace(tzinfo=NEPAL_TZ)
                ARTICLE_DATE_CACHE[href] = dt
                return dt

            # Explicit check for specific article publication time classes first (avoid header/epaper dates)
            m_news_time = re.search(r'class=["\x27][^"\x27]*(?:news-detail-time-text|published-date|pub-date|article-date)[^"\x27]*["\x27][^>]*>(?:<[^>]+>)*\s*([^<\r\n]{4,80})', chunk, re.I)
            if m_news_time and "epaper" not in m_news_time.group(0).lower():
                dt = parse_snippet_to_datetime(m_news_time.group(1).strip(), now_npt)
                if dt:
                    ARTICLE_DATE_CACHE[href] = dt
                    return dt

            # Explicit check for "Published: Nov. 11, 2026, 2:28 p.m." or "Published Date: 2026-11-06 19:10:51"
            m_pub_txt = re.search(r'Published(?:\s*Date)?\s*:\s*</b>\s*([A-Za-z0-9\s,\.:/\-]{6,45})', chunk, re.I)
            if not m_pub_txt:
                m_pub_txt = re.search(r'Published(?:\s*Date)?\s*:\s*([A-Za-z0-9\s,\.:/\-]{6,45})', chunk, re.I)
            if m_pub_txt:
                dt = parse_snippet_to_datetime(m_pub_txt.group(1).strip(), now_npt)
                if dt:
                    ARTICLE_DATE_CACHE[href] = dt
                    return dt

            # Check class elements for post-date / post__meta-date / date (excluding epaper-date)
            m_pub_box = re.search(r'class=["\x27][^"\x27]*(?:post-date|post__meta-date|date)[^"\x27]*["\x27][^>]*>(?:<[^>]+>)*\s*([^<]{5,80})', chunk, re.I)
            if m_pub_box and "epaper" not in m_pub_box.group(0).lower():
                dt = parse_snippet_to_datetime(m_pub_box.group(1).strip(), now_npt)
                if dt:
                    ARTICLE_DATE_CACHE[href] = dt
                    return dt

            # Check <time> tag inner text
            m_time = re.search(r'<time[^>]*>(?:<[^>]+>)*\s*([^<]{5,80})\s*</time>', chunk, re.I)
            if m_time and not "Intl.DateTimeFormat" in m_time.group(1):
                dt = parse_snippet_to_datetime(m_time.group(1).strip(), now_npt)
                if dt:
                    ARTICLE_DATE_CACHE[href] = dt
                    return dt

            # Also check standard snippet regexes across chunk
            for rgx in DATE_SNIPPET_REGEXES:
                m_chunk = rgx.search(chunk[:25000])
                if m_chunk:
                    dt = parse_snippet_to_datetime(m_chunk.group(0), now_npt)
                    if dt:
                        ARTICLE_DATE_CACHE[href] = dt
                        return dt
        except Exception:
            pass

    return None

def parse_to_nepal_time(raw_date_val, now_npt):
    """
    Parses any RSS timestamp, datetime object, or date string and converts it to Nepal Standard Time.
    Never fabricates 'Just now' if date is unlisted or missing.
    """
    if not raw_date_val:
        fallback_dt = now_npt - datetime.timedelta(days=7)
        return fallback_dt, "Date unlisted", "Archived"

    try:
        if isinstance(raw_date_val, datetime.datetime):
            dt = raw_date_val
        else:
            clean_str = re.sub(r"\[IST\]|IST", "+0530", str(raw_date_val))
            clean_str = re.sub(r"Updated\s*:\s*|Updated On\s*:\s*|Published\s*:\s*|By[^\d]+", "", clean_str)
            clean_str = clean_str.replace("|", " ")
            dt = dt_parser.parse(clean_str, fuzzy=True)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=NEPAL_TZ)
        else:
            dt = dt.astimezone(NEPAL_TZ)
        
        diff = now_npt - dt
        seconds = diff.total_seconds()

        # Clamp future clock skew to current time
        if seconds < 0:
            dt = now_npt
            diff = datetime.timedelta(seconds=0)
            seconds = 0
            rel_time = "Just now"
        elif seconds < 120:
            rel_time = "Just now"
        elif seconds < 3600:
            mins = int(seconds / 60)
            rel_time = f"{mins} mins ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            rel_time = f"{hours}h {mins}m ago" if mins > 0 else f"{hours}h ago"
        elif seconds < 86400 * 30:
            days = int(seconds / 86400)
            rel_time = f"{days}d ago"
        else:
            days = int(seconds / 86400)
            rel_time = f"{days}d ago"

        exact_time = dt.strftime("%b %d, %I:%M %p NPT")
        return dt, rel_time, exact_time
    except Exception:
        fallback_dt = now_npt - datetime.timedelta(days=7)
        return fallback_dt, "Date unlisted", "Archived"

def fetch_single_portal(portal, now_npt, max_entries: int = 50):
    """
    Fetches articles from a single online news portal (RSS, category feeds, or direct HTML).
    Guarantees deep article discovery without arbitrary limits, normalizes canonical URLs,
    extracts rich metadata, and updates persistent checkpoints and health metrics.
    """
    import time
    t0 = time.time()
    items = []
    seen_links = set()

    def process_rss_content(content_bytes, p_info):
        parsed_items = []
        feed = feedparser.parse(content_bytes)
        for entry in feed.entries[:max_entries]:
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
                "link": raw_link,
                "canonical_url": norm_link,
                "summary": clean_summary,
                "full_content": full_content,
                "published_dt": pub_dt,
                "relative_time": rel_time,
                "exact_time": exact_time,
                "is_viral": is_viral
            })
        return parsed_items

    try:
        if portal["type"] == "rss":
            req = urllib.request.Request(portal["url"], headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=3.5) as response:
                content = response.read()
            items.extend(process_rss_content(content, portal))

            # If primary feed yielded few articles, check configured alt_urls (category feeds)
            if len(items) < 8 and portal.get("alt_urls"):
                for alt_url in portal.get("alt_urls", []):
                    if len(items) >= max_entries:
                        break
                    try:
                        alt_req = urllib.request.Request(alt_url, headers=DEFAULT_HEADERS)
                        with urllib.request.urlopen(alt_req, context=SSL_CTX, timeout=2.5) as alt_resp:
                            alt_content = alt_resp.read()
                        items.extend(process_rss_content(alt_content, portal))
                    except Exception:
                        pass
        else:
            # HTML discovery mode (eKantipur, The Himalayan Times, Setopati EN, Nepal Aaja)
            req = urllib.request.Request(portal["url"], headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=3.5) as response:
                html_raw = response.read().decode("utf-8", errors="ignore")

            soup = BeautifulSoup(html_raw, "html.parser")
            seen_titles = set()
            for a in soup.find_all("a", href=True):
                txt = " ".join(a.get_text(" ", strip=True).split())
                href = a["href"].strip()
                if len(txt) >= 20 and txt not in seen_titles:
                    # Skip links inside navbars, headers, footers, search overlays, or trending search drawers
                    anc_tags = {p.name for p in a.parents if hasattr(p, "name")}
                    if "nav" in anc_tags or "header" in anc_tags or "footer" in anc_tags:
                        continue
                    anc_classes = " ".join(" ".join(p.get("class") or []) for p in a.parents if hasattr(p, "get")).lower()
                    if any(skip_cls in anc_classes for skip_cls in ["search-overlay", "trending-scroll", "navbar", "nav-menu", "main-menu", "header-menu", "footer"]):
                        continue
                    if any(skip_p in href.lower() for skip_p in ["/author/", "/tag/", "/category/", "/topic/", "/morearticles/", "/page/", "/hong-kong-home", "/entertainment"]):
                        continue
                    if any(k in txt.lower() for k in ["privacy", "terms", "contact us", "about us", "advertise", "epaper", "login", "more articles", "see more"]):
                        continue
                    if href.startswith("/"):
                        href = portal["url"].rstrip("/") + href
                    elif not href.startswith("http"):
                        continue

                    norm_link = normalize_canonical_url(href)
                    if norm_link in seen_links:
                        continue

                    seen_titles.add(txt)
                    seen_links.add(norm_link)
                    
                    art_summary = txt
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
                    cls_res = classify_article_editorial(txt, art_summary, portal["name"], art_summary)
                    classified_cat = cls_res["primary_section"]
                    headline_en = txt if portal.get("lang") == "English" else ""
                    canonical_id = generate_canonical_id(portal["name"], norm_link, txt)

                    items.append({
                        "canonical_id": canonical_id,
                        "source": portal["name"],
                        "language": portal.get("lang", "Nepali"),
                        "portal_category": portal.get("category", "General News"),
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
                    if len(items) >= max_entries:
                        break

        # Persist discovered batch into durable SQLite news store
        latency = round(time.time() - t0, 3)
        if items:
            batch_upsert_articles(items, portal["name"], latency_secs=latency)
    except Exception as e:
        latency = round(time.time() - t0, 3)
        record_source_error(portal["name"], str(e), latency_secs=latency)

    return items

def fetch_top_nepal_media(max_workers: int = 25, force_refresh: bool = False):
    """
    Fetches real-time news items across all 34 Top Nepal Online News Portals in parallel.
    If force_refresh=False and the SQLite store already holds recent articles, returns them
    immediately in <50ms while the background daemon keeps the store continuously synced.
    """
    now_npt = datetime.datetime.now(NEPAL_TZ)
    all_articles = []

    # Fast path: serve immediately from SQLite store unless explicit refresh is requested
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

    # Ensure source registry is synced
    try:
        register_portal_sources(TOP_NEPAL_NEWS_PORTALS)
    except Exception:
        pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_single_portal, p, now_npt) for p in TOP_NEPAL_NEWS_PORTALS]
        for f in concurrent.futures.as_completed(futures):
            all_articles.extend(f.result())

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
    r'visual stories|click here|read more|advertisement|sponsored)\b',
    re.IGNORECASE
)

_NEPAL_CORE_SUBJECT_RE = re.compile(
    r'(\bnepal\b|\bnepali\b|\bnepalese\b|\bkathmandu\b|\bpAPokhara\b|\bpokhara\b|\bbirgunj\b|\bbiratnagar\b|'
    r'\bjanakpur\b|\blumbini\b|\bchitwan\b|\bbhairahawa\b|\bdhangadhi\b|\bnepalgunj\b|\bmadhesh\b|'
    r'\bsingha durbar\b|\bsheetal niwas\b|\bbaluwatar\b|\bkp sharma oli\b|\bk\.?\s*p\.?\s*oli\b|\boli\b|'
    r'\bprachanda\b|\bpushpa kamal dahal\b|\bsher bahadur deuba\b|\bdeuba\b|\bbalen shah\b|\bbalen\b|'
    r'\brabi lamichhane\b|\bgagan thapa\b|\bram chandra paudel\b|\barzu rana\b|'
    r'\bindo-nepal\b|\bnepal-india\b|\bkalapani\b|\blipulekh\b|\blimpiyadhura\b|\bsusta\b|'
    r'\bpashupatinath\b|\bmuktinath\b|\bsagarmatha\b|\beverest\b|\bkoshi\b|\bgandak\b|\bmahakali\b|'
    r'\bpancheshwar\b|\barun-?3\b|\barun iii\b|\bupper karnali\b|\bwest seti\b|'
    r'नेपाल|नेपाली|काठमांडू|काठमाण्डौ|काठमाडौँ|पोखरा|बीरगंज|वीरगन्ज|जनकपुर|लुम्बिनी|लुंबिनी|'
    r'ओली|केपी ओली|प्रचंड|प्रचण्ड|देउवा|बालेन|कालापानी|लिपुलेख|लिम्पियाधुरा|कोशी|गण्डक|महाकाली|पशुपतिनाथ)',
    re.IGNORECASE
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
        if parsed_path.endswith(("/topic/nepal", "/tags/nepal", "/about/nepal", "/topic/india-nepal-relations", "/nepal")):
            return {
                "nepal_relevance_score": 0.0,
                "relevance_status": "excluded",
                "relevance_reason": "Index/tag landing page URL rather than an article",
                "nepal_dimensions": [],
                "is_substantive": False,
            }

    # Step 2: Check core Nepal anchors across Headline, Body, and URL slug
    title_matches = _NEPAL_CORE_SUBJECT_RE.findall(clean_title)
    body_text_only = clean_body if clean_body != clean_title else ""
    body_matches = _NEPAL_CORE_SUBJECT_RE.findall(body_text_only)
    url_has_nepal = bool(re.search(r'(nepal|kathmandu|kalapani|lipulekh|oli|prachanda|pokhara|madhesh|gorkha|koshi)', clean_link))

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
        score += 0.46
        reasons.append("Nepal explicitly anchored in headline")
    elif url_has_nepal:
        score += 0.28
        reasons.append("Nepal in article URL slug")
    elif len(body_matches) >= 2:
        score += 0.25
        reasons.append("Multiple Nepal references in article body")
    else:
        score += 0.14
        reasons.append("Single passing mention of Nepal in body")

    # B. Thematic pillar depth
    if matched_dimensions:
        dim_boost = min(0.36, 0.16 + 0.07 * (len(matched_dimensions) - 1) + min(0.08, pillar_hit_count * 0.02))
        score += dim_boost
        reasons.append(f"Contextual pillars: {', '.join(matched_dimensions)}")
    elif len(title_matches) >= 1:
        # Headline is explicitly about Nepal even if specific pillar keywords are general news
        score += 0.20
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

    if _PURE_INDIAN_DOMESTIC_NOISE_RE.search(combined_text):
        if len(title_matches) == 0:
            score -= 0.35
            reasons.append("Penalized: domestic Indian entertainment/sports/finance noise")
        else:
            score -= 0.15

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


def fetch_single_indian_media(src, now_npt, relevance_threshold: float = DEFAULT_NEPAL_RELEVANCE_THRESHOLD):
    """
    Fetches candidate articles from prominent Indian media outlets and applies
    contextual Nepal-relevance classification to each candidate.
    Retains substantive, borderline_review, and a sample of excluded articles for central DB persistence,
    while `fetch_nepal_in_indian_media` filters strictly before displaying in the India Media feed.
    """
    items = []
    seen = set()
    excluded_kept = 0
    try:
        req = urllib.request.Request(src["url"], headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=3.5) as resp:
            data = resp.read()

        if src.get("type") == "rss":
            feed = feedparser.parse(data)
            for e in feed.entries:
                raw_title = e.get("title", "").strip()
                summary_raw = e.get("summary", "") or e.get("description", "")
                link_url = e.get("link", "#")

                clean_title = re.sub(r'\s*-\s*[^-]+$', '', raw_title).strip() or raw_title
                if not clean_title or clean_title in seen or _NAV_BOILERPLATE_RE.search(clean_title):
                    continue

                clean_sum = re.sub(r'<[^>]+>', ' ', summary_raw)
                clean_sum = html.unescape(clean_sum)
                clean_sum = re.sub(r'\s+', ' ', clean_sum).strip() or clean_title

                rel_eval = evaluate_indian_article_nepal_relevance(
                    title=clean_title,
                    summary=clean_sum,
                    full_content=clean_sum,
                    link=link_url,
                    source=src["name"],
                    threshold=relevance_threshold,
                )
                if rel_eval["relevance_status"] == "excluded":
                    if excluded_kept >= 4:
                        continue
                    excluded_kept += 1

                seen.add(clean_title)

                pub_raw = e.get("published", "") or e.get("updated", "")
                if not pub_raw and link_url and link_url.startswith("http"):
                    pub_raw = extract_date_from_card_or_url(None, link_url, now_npt)
                pub_dt, rel_time, exact_time = parse_to_nepal_time(pub_raw, now_npt)

                cls_res = classify_article_editorial(clean_title, clean_sum, src["name"], clean_sum)
                if "India Section" not in cls_res["sections"]:
                    cls_res["sections"].insert(0, "India Section")

                items.append({
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
                    "title": clean_title,
                    "headline_english": clean_title if src["lang"] == "English" else "",
                    "link": link_url,
                    "summary": clean_sum[:280] + ("..." if len(clean_sum) > 280 else ""),
                    "full_content": clean_sum,
                    "published_dt": pub_dt,
                    "relative_time": rel_time,
                    "exact_time": exact_time,
                    "nepal_relevance_score": rel_eval["nepal_relevance_score"],
                    "relevance_status": rel_eval["relevance_status"],
                    "relevance_reason": rel_eval["relevance_reason"],
                    "nepal_dimensions": rel_eval["nepal_dimensions"],
                })
        else:
            soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
            # Remove header, nav, footer, and scripts that pollute topic pages with general Indian domestic links
            for nav_tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                nav_tag.decompose()

            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                # If the anchor wraps both a heading (h1-h4) and a paragraph/summary, separate them cleanly
                heading_el = a.find(["h1", "h2", "h3", "h4"])
                p_inside = a.find("p")
                if heading_el and heading_el.get_text(strip=True):
                    txt = heading_el.get_text(" ", strip=True)
                else:
                    # Clone or extract text excluding inner <p> so headline isn't glued to body snippet
                    if p_inside and p_inside.get_text(strip=True):
                        p_txt = p_inside.get_text(" ", strip=True)
                        full_a_txt = a.get_text(" ", strip=True)
                        txt = full_a_txt.replace(p_txt, "").strip() or full_a_txt
                    else:
                        txt = a.get_text(" ", strip=True)

                if len(txt) <= 22 or _NAV_BOILERPLATE_RE.search(txt):
                    continue

                clean_txt = re.sub(r'\s+', ' ', txt).strip()
                if clean_txt in seen or clean_txt.startswith("{"):
                    continue

                # Fix relative URLs first so URL slug inspection works accurately
                if href.startswith("/"):
                    if "amarujala" in src["url"]:
                        href = "https://www.amarujala.com" + href
                    elif "swarajya" in src["url"]:
                        href = "https://swarajyamag.com" + href
                    elif "oneindia" in src["url"]:
                        href = "https://www.oneindia.com" + href
                    elif "hindustan" in src["url"]:
                        href = "https://www.livehindustan.com" + href
                    elif "thequint" in src["url"]:
                        href = "https://www.thequint.com" + href
                    elif "prabhatkhabar" in src["url"]:
                        href = "https://www.prabhatkhabar.com" + href
                    elif "indiatoday" in src["url"]:
                        href = "https://www.indiatoday.in" + href
                    elif "indianexpress" in src["url"]:
                        href = "https://indianexpress.com" + href
                    elif "jansatta" in src["url"]:
                        href = "https://www.jansatta.com" + href

                # Extract surrounding card snippet if available for richer semantic evaluation
                card_snippet = ""
                if p_inside and p_inside.get_text(strip=True):
                    card_snippet = re.sub(r'\s+', ' ', p_inside.get_text(" ", strip=True)).strip()
                else:
                    parent_card = a.find_parent(["article", "li", "div"])
                    if parent_card:
                        p_tag = parent_card.find("p")
                        if p_tag:
                            card_snippet = re.sub(r'\s+', ' ', p_tag.get_text(" ", strip=True)).strip()

                summary_text = card_snippet if (card_snippet and card_snippet != clean_txt) else clean_txt

                rel_eval = evaluate_indian_article_nepal_relevance(
                    title=clean_txt,
                    summary=summary_text,
                    full_content=summary_text,
                    link=href,
                    source=src["name"],
                    threshold=relevance_threshold,
                )
                if rel_eval["relevance_status"] == "excluded":
                    if excluded_kept >= 4 or "Navigation/boilerplate" in rel_eval["relevance_reason"] or "Index/tag landing" in rel_eval["relevance_reason"]:
                        continue
                    excluded_kept += 1

                seen.add(clean_txt)

                parsed_dt = extract_date_from_card_or_url(a, href, now_npt)
                art_dt, rel_time, exact_time = parse_to_nepal_time(parsed_dt, now_npt)

                cls_res = classify_article_editorial(clean_txt, summary_text, src["name"], summary_text)
                if "India Section" not in cls_res["sections"]:
                    cls_res["sections"].insert(0, "India Section")

                items.append({
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
                    "title": clean_txt,
                    "headline_english": clean_txt if src["lang"] == "English" else "",
                    "link": href,
                    "summary": summary_text[:280] + ("..." if len(summary_text) > 280 else ""),
                    "full_content": summary_text,
                    "published_dt": art_dt,
                    "relative_time": rel_time,
                    "exact_time": exact_time,
                    "nepal_relevance_score": rel_eval["nepal_relevance_score"],
                    "relevance_status": rel_eval["relevance_status"],
                    "relevance_reason": rel_eval["relevance_reason"],
                    "nepal_dimensions": rel_eval["nepal_dimensions"],
                })
                if sum(1 for x in items if x["relevance_status"] == "substantive") >= 15:
                    break
    except Exception:
        pass
    return items


def fetch_nepal_in_indian_media(
    max_workers: int = 18,
    relevance_threshold: float = DEFAULT_NEPAL_RELEVANCE_THRESHOLD,
    include_borderline: bool = False,
    force_refresh: bool = False,
):
    """
    Fetches real-time Nepal news across Top Indian Media Outlets, retains all
    discovered candidate articles (substantive, borderline_review, excluded) in the
    central SQLite database (`indian_media_articles`), and returns ONLY articles
    that meet the substantive Nepal-relevance threshold for the India Media feed.
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
        except Exception:
            pass

    raw_candidates = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_single_indian_media, s, now_npt, relevance_threshold)
            for s in TOP_INDIAN_MEDIA_SOURCES
        ]
        for f in concurrent.futures.as_completed(futures):
            try:
                raw_candidates.extend(f.result())
            except Exception:
                pass

    # Persist all candidate Indian articles (substantive, borderline_review, excluded) in central DB
    if raw_candidates:
        try:
            ingest_indian_articles_batch(raw_candidates)
        except Exception:
            pass

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

    # Reconcile with stored substantive Indian articles in SQLite so previously discovered valid stories persist
    try:
        stored_substantive = get_stored_indian_articles(
            status_filter=None if include_borderline else "substantive",
            min_score=BORDERLINE_NEPAL_RELEVANCE_FLOOR if include_borderline else relevance_threshold,
            limit=250,
        )
        for sa in stored_substantive:
            # Re-verify with current classifier in case older DB rows predate strict rules
            re_eval = evaluate_indian_article_nepal_relevance(
                title=sa.get("title", ""),
                summary=sa.get("summary", ""),
                full_content=sa.get("full_content", ""),
                link=sa.get("link", ""),
                source=sa.get("source", ""),
                threshold=relevance_threshold,
            )
            sa["nepal_relevance_score"] = re_eval["nepal_relevance_score"]
            sa["relevance_status"] = re_eval["relevance_status"]
            sa["relevance_reason"] = re_eval["relevance_reason"]
            sa["nepal_dimensions"] = re_eval["nepal_dimensions"]

            if sa["nepal_relevance_score"] < (BORDERLINE_NEPAL_RELEVANCE_FLOOR if include_borderline else relevance_threshold):
                continue

            norm_url = normalize_canonical_url(sa.get("link", "")) or sa.get("title", "")
            if norm_url not in seen_links:
                seen_links.add(norm_url)
                filtered_feed.append(sa)
    except Exception:
        pass

    filtered_feed.sort(
        key=lambda x: x["published_dt"] if isinstance(x.get("published_dt"), datetime.datetime) else now_npt,
        reverse=True,
    )
    return filtered_feed


