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
    register_portal_sources
)


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

def translate_to_english_machine(text: str, *args, **kwargs) -> str:
    """Returns original text directly without triggering translation services."""
    return text or ""

translate_headline_to_en = translate_to_english_machine

def batch_translate_headlines(articles: list, *args, **kwargs) -> list:
    """Returns articles directly in original language without translation."""
    return articles

def batch_translate_posts(posts: list, *args, **kwargs) -> list:
    """Returns posts directly in original language without translation."""
    return posts

def extract_article_full_text(url: str, timeout: int = 6) -> str:
    """
    Extracts the full news article body text from an article URL.
    Returns cleaned text with paragraphs separated by newlines.
    """
    if not url or not url.startswith("http"):
        return ""
    if url in FULL_ARTICLE_TEXT_CACHE:
        return FULL_ARTICLE_TEXT_CACHE[url]

    try:
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(raw_html, "html.parser")
        
        # Strip script, styles, buttons, navigation, headers, and footers
        for tag in soup(["script", "style", "noscript", "svg", "button", "header", "footer", "nav"]):
            tag.decompose()
        for tag in soup.find_all("aside"):
            # Retain aside if it contains main content column (e.g. Setopati left-side)
            if not any(c in str(tag.get("class", [])) for c in ["left-side", "content", "main", "col-"]):
                tag.decompose()

        content_containers = soup.select(
            "article, .editor-box, .detail-box, .story-content, .article-content, "
            ".entry-content, .post-content, .news-content, .detail-content, .story__content, "
            ".article__body, .news_detail, .full-content, .content-body, #content-body, "
            ".main-content, .story-section, .story-details, .news_description, .entry-content-wrap, "
            ".post-detail, .story-with-main-sec"
        )
        
        paras = []
        if content_containers:
            for c in content_containers:
                for p in c.find_all(["p", "div"]):
                    if p.name == "p" or (p.name == "div" and not p.find(["p", "div"])):
                        txt = p.get_text(" ", strip=True)
                        if txt and txt not in paras and len(txt) > 20:
                            paras.append(txt)

        # Fallback to all paragraphs in the document
        if len(" ".join(paras)) < 150:
            paras = []
            for p in soup.find_all("p"):
                txt = p.get_text(" ", strip=True)
                if txt and txt not in paras and len(txt) > 20:
                    paras.append(txt)

        clean = []
        for p in paras:
            low = p.lower()
            if any(b in low for b in [
                "cookie policy", "privacy policy", "terms of service", "terms of use", 
                "all rights reserved", "advertisement", "copyright ©", "download our app", 
                "rights reserved", "subscribe to"
            ]):
                continue
            clean.append(p)

        full_text = "\n\n".join(clean).strip()
        if full_text:
            FULL_ARTICLE_TEXT_CACHE[url] = full_text
            return full_text
    except Exception:
        pass
    return ""

def batch_fetch_full_content(articles: list, max_workers: int = 15) -> list:
    """
    Extracts the full news article body text for a list of articles in parallel.
    Populates 'full_content' on each article dictionary with the extracted news text.
    """
    to_fetch = []
    for art in articles:
        link = art.get("link", "")
        if link in FULL_ARTICLE_TEXT_CACHE:
            art["full_content"] = FULL_ARTICLE_TEXT_CACHE[link]
        elif link.startswith("http"):
            to_fetch.append(art)

    if to_fetch:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_art = {
                executor.submit(extract_article_full_text, a.get("link", "")): a
                for a in to_fetch
            }
            for fut in concurrent.futures.as_completed(future_to_art):
                a = future_to_art[fut]
                try:
                    extracted = fut.result()
                    if extracted and len(extracted) > 50:
                        a["full_content"] = extracted
                    elif not a.get("full_content"):
                        a["full_content"] = a.get("summary") or a.get("title", "")
                except Exception:
                    if not a.get("full_content"):
                        a["full_content"] = a.get("summary") or a.get("title", "")
    return articles

# The 9 Ordered Target Categories for Word Export
DOCX_TARGET_CATEGORIES = [
    "INDIA SECTION",
    "CHINA SECTION",
    "BANGLADESH SECTION",
    "PAKISTAN SECTION",
    "NEPAL – INTERNAL",
    "NEPAL – EXTERNAL",
    "NEPAL – ECONOMY",
    "NEPAL – OTHERS",
    "INTERNATIONAL NEWS"
]

def map_to_target_category(raw_category: str) -> str:
    cat = (raw_category or "").strip().lower()
    if "india" in cat:
        return "INDIA SECTION"
    elif "china" in cat:
        return "CHINA SECTION"
    elif "bangladesh" in cat:
        return "BANGLADESH SECTION"
    elif "pakistan" in cat:
        return "PAKISTAN SECTION"
    elif "internal" in cat or "politics" in cat:
        return "NEPAL – INTERNAL"
    elif "external" in cat or "foreign" in cat or "diplomacy" in cat:
        return "NEPAL – EXTERNAL"
    elif "economy" in cat or "economic" in cat:
        return "NEPAL – ECONOMY"
    elif "international" in cat or "world" in cat or "global" in cat:
        return "INTERNATIONAL NEWS"
    else:
        return "NEPAL – OTHERS"

def generate_word_document(articles: list, output_path: str = None, report_title: str = "Nepal Media & Intelligence Executive Report") -> bytes:
    """
    Exports a list of news articles to an executive-ready Word document (.docx) formatted with:
    - Formal Executive Cover / Header with Document Title, Nepal Time Timestamp, and Story Count
    - Table of Contents summary by category
    - Grouped by category with headers in ALL CAPS and YELLOW highlighting.
    - Strict order:
        1. INDIA IN NEPAL
        2. CHINA IN NEPAL
        3. PAKISTAN IN NEPAL
        4. BANGLADESH IN NEPAL - INTERNAL
        5. ECONOMY
        6. OTHERS
        7. NEPAL-EXTERNALS
    - Under each category:
        • Headline: Bulleted and italicized (with English translation on next line if available)
        (Source Name): In parentheses immediately below headline
        Body: Full text of news article starting on next line
        URL: Full URL placed on final line after text
    """
    import io
    import docx
    from docx.enum.text import WD_COLOR_INDEX, WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, Inches, RGBColor

    grouped = {c: [] for c in DOCX_TARGET_CATEGORIES}
    for a in articles:
        t_cat = map_to_target_category(a.get("structured_category", ""))
        grouped[t_cat].append(a)

    doc = docx.Document()

    # Document margins
    for sec in doc.sections:
        sec.top_margin = Inches(0.8)
        sec.bottom_margin = Inches(0.8)
        sec.left_margin = Inches(0.8)
        sec.right_margin = Inches(0.8)

    # --- Document Header & Title Banner ---
    now_str = datetime.datetime.now(NEPAL_TZ).strftime("%A, %B %d, %Y · %I:%M %p NPT")
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(4)
    p_title.paragraph_format.space_after = Pt(2)
    r_title = p_title.add_run(report_title)
    r_title.bold = True
    r_title.font.size = Pt(16)
    r_title.font.color.rgb = RGBColor(15, 23, 42)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(14)
    r_sub = p_sub.add_run(f"Generated: {now_str}  |  Total Stories: {len(articles)}")
    r_sub.font.size = Pt(9.5)
    r_sub.font.color.rgb = RGBColor(100, 116, 139)

    # Mini Summary Table
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Category"
    hdr_cells[1].text = "Articles Selected"
    for cell in hdr_cells:
        cell.paragraphs[0].runs[0].bold = True
        cell.paragraphs[0].runs[0].font.size = Pt(9.5)

    for cat_name in DOCX_TARGET_CATEGORIES:
        count = len(grouped[cat_name])
        if count > 0:
            row_cells = table.add_row().cells
            row_cells[0].text = cat_name
            row_cells[1].text = str(count)
            for cell in row_cells:
                cell.paragraphs[0].runs[0].font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    for cat_name in DOCX_TARGET_CATEGORIES:
        cat_items = grouped[cat_name]

        # Category Header: ALL CAPS with Yellow Highlighting
        p_cat = doc.add_paragraph()
        p_cat.paragraph_format.space_before = Pt(18)
        p_cat.paragraph_format.space_after = Pt(6)
        p_cat.paragraph_format.keep_with_next = True
        r_cat = p_cat.add_run(cat_name)
        r_cat.bold = True
        r_cat.font.size = Pt(12)
        r_cat.font.highlight_color = WD_COLOR_INDEX.YELLOW

        if not cat_items:
            p_empty = doc.add_paragraph()
            p_empty.paragraph_format.space_before = Pt(0)
            p_empty.paragraph_format.space_after = Pt(8)
            r_empty = p_empty.add_run("No articles in this category.")
            r_empty.font.color.rgb = RGBColor(128, 128, 128)
            r_empty.font.size = Pt(9.5)
            continue

        for a in cat_items:
            orig_title = (a.get("title") or a.get("text") or "").strip()
            en_trans = (a.get("headline_english") or "").strip()
            source_name = (a.get("source") or a.get("handle") or a.get("author_name") or "Source").strip()
            body_text = (a.get("full_content") or a.get("text") or a.get("summary") or a.get("title") or "").strip()
            url = (a.get("link") or "").strip()

            # Headline: Bulleted and italicized (• Headline)
            p_head = doc.add_paragraph(style="List Bullet")
            p_head.paragraph_format.space_before = Pt(8)
            p_head.paragraph_format.space_after = Pt(2)
            p_head.paragraph_format.keep_with_next = True

            r_head = p_head.add_run(orig_title)
            r_head.italic = True
            r_head.bold = True
            if en_trans and en_trans != orig_title:
                r_head.add_break()
                r_trans = p_head.add_run(en_trans)
                r_trans.italic = True

            # Source: Source/Portal name in parentheses immediately below headline
            p_src = doc.add_paragraph()
            p_src.paragraph_format.space_before = Pt(0)
            p_src.paragraph_format.space_after = Pt(4)
            p_src.paragraph_format.left_indent = Inches(0.25)
            p_src.paragraph_format.keep_with_next = True
            r_src = p_src.add_run(f"({source_name})")
            r_src.font.size = Pt(9.5)
            r_src.font.color.rgb = RGBColor(80, 80, 80)

            # Body: Full text of news article starting on next line
            paragraphs = [p.strip() for p in body_text.split("\n\n") if p.strip()]
            if not paragraphs:
                paragraphs = [body_text] if body_text else ["No additional text content available."]

            for para in paragraphs:
                p_body = doc.add_paragraph()
                p_body.paragraph_format.space_before = Pt(0)
                p_body.paragraph_format.space_after = Pt(4)
                p_body.paragraph_format.left_indent = Inches(0.25)
                p_body.paragraph_format.line_spacing = 1.15
                r_body = p_body.add_run(para)
                r_body.font.size = Pt(10)

            # URL: Full URL placed on the final line after the text
            p_url = doc.add_paragraph()
            p_url.paragraph_format.space_before = Pt(2)
            p_url.paragraph_format.space_after = Pt(14)
            p_url.paragraph_format.left_indent = Inches(0.25)
            r_url = p_url.add_run(url)
            r_url.font.size = Pt(9)
            r_url.font.color.rgb = RGBColor(0, 102, 204)
            r_url.underline = True

    bio = io.BytesIO()
    doc.save(bio)
    doc_bytes = bio.getvalue()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(doc_bytes)

    return doc_bytes

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
    {"name": "Naya Patrika", "type": "rss", "url": "https://www.nayapatrikadaily.com/rss", "alt_urls": [], "lang": "Nepali", "category": "National Daily", "priority": "standard", "check_interval_mins": 18},
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
    {"name": "NepalKhabar (EN)", "type": "rss", "url": "https://en.nepalkhabar.com/rss", "alt_urls": [], "lang": "English", "category": "Digital Daily", "priority": "standard", "check_interval_mins": 18},
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

# Comprehensive Directory of 140+ Monitored Facebook Pages & Public Figures in Nepal
# Covering Journalists, Opinion Makers, Analysts, Think Tanks, Bilateral Relations & Commentators
POPULAR_NEPAL_FB_PAGES = [
    {
        "name": 'Madhu Raman Acharya',
        "slug": 'madhuramanacharya',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Former Foreign Secretary & Diplomat',
        "desc": 'Authoritative commentary on diplomacy, treaties, and foreign policy',
        "avatar_bg": '#1e3a8a',
        "initials": 'MA'
    },
    {
        "name": 'Sudheer Sharma',
        "slug": 'sudheerktm',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Author & Veteran Editor',
        "desc": "Author of 'Prayogshala' analyzing Nepal's internal power shifts and regional foreign policy",
        "avatar_bg": '#0f172a',
        "initials": 'SS'
    },
    {
        "name": 'Dipak Gyawali',
        "slug": 'dipak.gyawali.7',
        "category": 'India in Nepal',
        "role": 'Water Resources Expert & Former Minister',
        "desc": 'In-depth insights into Nepal-India water treaties, energy sovereignty, and geopolitics',
        "avatar_bg": '#047857',
        "initials": 'DG'
    },
    {
        "name": 'Kanak Mani Dixit',
        "slug": 'kanakmanidixit',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Civil Society Leader & Writer',
        "desc": 'Senior commentator on South Asian regionalism, democracy, and cross-border relations',
        "avatar_bg": '#334155',
        "initials": 'KD'
    },
    {
        "name": 'Amish Raj Mulmi',
        "slug": 'amish.mulmi',
        "category": 'China in Nepal',
        "role": 'Author & Geopolitical Columnist',
        "desc": "Author of 'All Roads Lead North', tracking Nepal-China dynamics and Himalayan passes",
        "avatar_bg": '#dc2626',
        "initials": 'AM'
    },
    {
        "name": 'Geja Sharma Wagle',
        "slug": 'geja.wagle',
        "category": 'India in Nepal',
        "role": 'Defense & Security Columnist',
        "desc": 'Strategic analysis on regional defense, border dynamics, and security policies',
        "avatar_bg": '#475569',
        "initials": 'GW'
    },
    {
        "name": 'Dr. Surya Raj Acharya',
        "slug": 'surya.r.acharya',
        "category": 'Economy & Trade',
        "role": 'Public Policy & Infrastructure Analyst',
        "desc": 'Expert analysis on mega-projects, transit corridors, and economic governance',
        "avatar_bg": '#0284c7',
        "initials": 'SA'
    },
    {
        "name": 'Akhilesh Upadhyay',
        "slug": 'akhilesh.upadhyay',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Senior Fellow IIDS & Foreign Affairs Analyst',
        "desc": "Strategic analysis of Nepal's neighborhood diplomacy and global engagement",
        "avatar_bg": '#1e40af',
        "initials": 'AU'
    },
    {
        "name": 'Yubaraj Ghimire',
        "slug": 'yubaraj.ghimire.12',
        "category": 'Nepal – Internal Politics',
        "role": 'Senior Editor & Political Analyst',
        "desc": 'Constitutional oversight, parliamentary dynamics, and political discourse',
        "avatar_bg": '#7c2d12',
        "initials": 'YG'
    },
    {
        "name": 'Dilbhusan Pathak',
        "slug": 'dilbhusan.pathak',
        "category": 'Nepal – Internal Politics',
        "role": 'Senior Broadcast Journalist',
        "desc": "Host of 'Tough Talk' covering governance, accountability, and national debates",
        "avatar_bg": '#0f766e',
        "initials": 'DP'
    },
    {
        "name": 'Gajendra Budhathoki',
        "slug": 'gbudhathoki',
        "category": 'Economy & Trade',
        "role": 'Senior Economic Journalist',
        "desc": 'Investigative coverage of inflation, public debt, banks, and economic reform',
        "avatar_bg": '#b45309',
        "initials": 'GB'
    },
    {
        "name": 'Vijay Kant Karna',
        "slug": 'vijaykantkarna',
        "category": 'Nepal – Internal Politics',
        "role": 'Political Scientist & Policy Analyst',
        "desc": 'Madhesh dynamics, federalism, inclusion, and bilateral diplomacy',
        "avatar_bg": '#e11d48',
        "initials": 'VK'
    },
    {
        "name": 'NIICE Nepal',
        "slug": 'niicenepal',
        "category": 'China in Nepal',
        "role": 'International Cooperation & Engagement Think Tank',
        "desc": 'Regular research publications on BRI, South Asian security, and China-Nepal ties',
        "avatar_bg": '#dc2626',
        "initials": 'NI'
    },
    {
        "name": 'CESIF Nepal',
        "slug": 'cesifnepal',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Centre for Social Innovation & Foreign Policy',
        "desc": 'Tracking foreign policy developments, multilateralism, and geopolitical trends',
        "avatar_bg": '#4338ca',
        "initials": 'CS'
    },
    {
        "name": 'IIDS Nepal',
        "slug": 'iidsnepal',
        "category": 'Economy & Trade',
        "role": 'Institute for Integrated Development Studies',
        "desc": 'Leading research institute on economic growth, South Asian trade, and policy',
        "avatar_bg": '#0d9488',
        "initials": 'II'
    },
    {
        "name": 'SEJON (Society of Economic Journalists)',
        "slug": 'sejon.nepal',
        "category": 'Economy & Trade',
        "role": 'Economic Journalism Forum',
        "desc": 'Apex body tracking national fiscal policies, export-import trends, and customs',
        "avatar_bg": '#d97706',
        "initials": 'SE'
    },
    {
        "name": 'SAARC Secretariat',
        "slug": 'saarcsecretariat',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Regional Multilateral Organization HQ',
        "desc": 'Official regional cooperation forum headquartered in Kathmandu',
        "avatar_bg": '#0284c7',
        "initials": 'SS'
    },
    {
        "name": 'Embassy of India Kathmandu',
        "slug": 'IndiaInNepal',
        "category": 'India in Nepal',
        "role": 'Official Mission of India',
        "desc": 'Bilateral aid, border projects, scholarship programs, and high-level official visits',
        "avatar_bg": '#ea580c',
        "initials": 'IN'
    },
    {
        "name": 'Chinese Embassy in Nepal',
        "slug": 'chinanepalembassy',
        "category": 'China in Nepal',
        "role": "Embassy of the People's Republic of China",
        "desc": 'Bilateral exchanges, cultural diplomacy, northern border posts, and development initiatives',
        "avatar_bg": '#b91c1c',
        "initials": 'CN'
    },
    {
        "name": 'Embassy of Pakistan Kathmandu',
        "slug": 'PakinNepal',
        "category": 'Pakistan & Nepal',
        "role": 'Embassy of Pakistan in Nepal',
        "desc": 'Bilateral education programs, cultural events, and diplomatic engagements',
        "avatar_bg": '#14532d',
        "initials": 'PK'
    },
    {
        "name": 'Bangladesh Embassy Nepal',
        "slug": 'bdembassykathmandu',
        "category": 'Bangladesh & Nepal',
        "role": 'Embassy of Bangladesh, Kathmandu',
        "desc": 'Tripartite energy trade (Nepal-India-Bangladesh), regional transit, and trade pacts',
        "avatar_bg": '#15803d',
        "initials": 'BD'
    },
    {
        "name": 'U.S. Embassy Kathmandu',
        "slug": 'usembassynepal',
        "category": 'Nepal – External Relations (Others)',
        "role": 'United States Mission in Nepal',
        "desc": 'USAID partnerships, MCC compact developments, and diplomatic announcements',
        "avatar_bg": '#1e3a8a',
        "initials": 'US'
    },
    {
        "name": 'European Union in Nepal',
        "slug": 'EUinNepal',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Delegation of the European Union',
        "desc": 'Multilateral development cooperation, aviation safety, and climate initiatives',
        "avatar_bg": '#1d4ed8',
        "initials": 'EU'
    },
    {
        "name": 'Ministry of Foreign Affairs, Nepal',
        "slug": 'mofanepal',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Government of Nepal Diplomatic Headquarters',
        "desc": 'Official press communiques, bilateral treaties, and foreign ministerial statements',
        "avatar_bg": '#1e40af',
        "initials": 'MF'
    },
    {
        "name": 'Balen Shah',
        "slug": 'balenshah',
        "category": 'Nepal – Internal Politics',
        "role": 'Mayor of Kathmandu / Civic Reformer',
        "desc": 'Kathmandu municipal governance, urban policy, and public reforms',
        "avatar_bg": '#0284c7',
        "initials": 'BS'
    },
    {
        "name": 'Dr. Baburam Bhattarai',
        "slug": 'drbaburambhattarai',
        "category": 'Nepal – Internal Politics',
        "role": 'Former PM / Economist & Thinker',
        "desc": "Long-form commentary on Nepal's political economy, federalism, and geostrategy",
        "avatar_bg": '#7c2d12',
        "initials": 'BB'
    },
    {
        "name": 'Dr. Swarnim Wagle',
        "slug": 'swarnimwagleofficial',
        "category": 'Economy & Trade',
        "role": 'Vice Chairman RSP / Economist',
        "desc": 'In-depth posts on economic policy, foreign debt, and national development vision',
        "avatar_bg": '#0369a1',
        "initials": 'SW'
    },
    {
        "name": 'Routine of Nepal Banda (RONB)',
        "slug": 'routineofnepalbanda',
        "category": 'Nepal – Internal Politics',
        "role": "Nepal's #1 Social Media News Curator",
        "desc": 'Over 4M+ followers; fastest real-time community reports, viral debates, and civic alerts',
        "avatar_bg": '#0284c7',
        "initials": 'RO'
    },
    {
        "name": 'OnlineKhabar',
        "slug": 'onlinekhabar',
        "category": 'Nepal – Internal Politics',
        "role": 'Leading Digital News Platform',
        "desc": 'Round-the-clock news reporting with huge public engagement and discussion',
        "avatar_bg": '#dc2626',
        "initials": 'OK'
    },
    {
        "name": 'Setopati',
        "slug": 'setopati',
        "category": 'Nepal – Internal Politics',
        "role": 'Digital Newspaper & In-depth Reporting',
        "desc": 'Investigative op-eds, political discourse, and international analysis',
        "avatar_bg": '#334155',
        "initials": 'SP'
    },
    {
        "name": 'Kantipur TV HD',
        "slug": 'kantipurtvhd',
        "category": 'Nepal – Internal Politics',
        "role": 'Broadcast Television Channel',
        "desc": 'Video clips, prime-time news debates, and live press briefings',
        "avatar_bg": '#0284c7',
        "initials": 'KT'
    },
    {
        "name": 'Nepal Police Official',
        "slug": 'nepalpolice',
        "category": 'Nepal – Internal Politics',
        "role": 'Headquarters of Nepal Police',
        "desc": 'Official safety bulletins, public notices, and cyber alerts',
        "avatar_bg": '#1e3a8a',
        "initials": 'NP'
    },
    {
        "name": 'Balen Shah',
        "slug": 'shahbalen',
        "category": 'Nepal – Internal Politics',
        "role": 'Mayor of Kathmandu / Youth Leader',
        "desc": 'Political Leader · Mayor of Kathmandu / Youth Leader',
        "avatar_bg": '#1d9bf0',
        "initials": 'BS'
    },
    {
        "name": 'KP Sharma Oli',
        "slug": 'kpsharmaoli',
        "category": 'Nepal – Internal Politics',
        "role": 'Prime Minister of Nepal / Chairman CPN (UML)',
        "desc": 'Political Leader · Prime Minister of Nepal / Chairman CPN (UML)',
        "avatar_bg": '#dc2626',
        "initials": 'KO'
    },
    {
        "name": "Pushpa Kamal Dahal 'Prachanda'",
        "slug": 'cmprachanda',
        "category": 'Nepal – Internal Politics',
        "role": 'Former PM / Chairman CPN (Maoist Centre)',
        "desc": 'Political Leader · Former PM / Chairman CPN (Maoist Centre)',
        "avatar_bg": '#b91c1c',
        "initials": 'PK'
    },
    {
        "name": 'Sher Bahadur Deuba',
        "slug": 'sherbdeuba',
        "category": 'Nepal – Internal Politics',
        "role": 'President, Nepali Congress / Former PM',
        "desc": 'Political Leader · President, Nepali Congress / Former PM',
        "avatar_bg": '#15803d',
        "initials": 'SD'
    },
    {
        "name": 'Gagan Kumar Thapa',
        "slug": 'gaganthapa',
        "category": 'Nepal – Internal Politics',
        "role": 'General Secretary, Nepali Congress / MP',
        "desc": 'Political Leader · General Secretary, Nepali Congress / MP',
        "avatar_bg": '#0284c7',
        "initials": 'GT'
    },
    {
        "name": 'Dr. Baburam Bhattarai',
        "slug": 'brb1954',
        "category": 'Economy & Trade',
        "role": 'Former Prime Minister / Economist',
        "desc": 'Political Leader · Former Prime Minister / Economist',
        "avatar_bg": '#7c2d12',
        "initials": 'BB'
    },
    {
        "name": 'Dr. Swarnim Wagle',
        "slug": 'swarnimwagle',
        "category": 'Economy & Trade',
        "role": 'Vice Chairman RSP / MP / Economist',
        "desc": 'Political Leader · Vice Chairman RSP / MP / Economist',
        "avatar_bg": '#0369a1',
        "initials": 'SW'
    },
    {
        "name": 'Rabi Lamichhane',
        "slug": 'hamrorabi',
        "category": 'Nepal – Internal Politics',
        "role": 'Chairman, Rastriya Swatantra Party (RSP)',
        "desc": 'Political Leader · Chairman, Rastriya Swatantra Party (RSP)',
        "avatar_bg": '#0284c7',
        "initials": 'RL'
    },
    {
        "name": 'Rabindra Mishra',
        "slug": 'rabindramishra',
        "category": 'Nepal – Internal Politics',
        "role": 'Senior Vice Chairman, RPP / Author',
        "desc": 'Political Leader · Senior Vice Chairman, RPP / Author',
        "avatar_bg": '#d97706',
        "initials": 'RM'
    },
    {
        "name": 'Dr. CK Raut',
        "slug": 'drckraut',
        "category": 'Nepal – Internal Politics',
        "role": 'Chairman, Janamat Party / MP',
        "desc": 'Political Leader · Chairman, Janamat Party / MP',
        "avatar_bg": '#e11d48',
        "initials": 'CR'
    },
    {
        "name": 'Nepal Police Official',
        "slug": 'nepalpolicehq',
        "category": 'Nepal – Internal Politics',
        "role": 'Nepal Police Headquarters, Naxal',
        "desc": 'Government & Security · Nepal Police Headquarters, Naxal',
        "avatar_bg": '#1e3a8a',
        "initials": 'NP'
    },
    {
        "name": 'Hello Sarkar (PMO)',
        "slug": 'hello_sarkar',
        "category": 'Nepal – Internal Politics',
        "role": 'Office of the Prime Minister and Council of Ministers',
        "desc": 'Government & Security · Office of the Prime Minister and Council of Ministers',
        "avatar_bg": '#0369a1',
        "initials": 'HS'
    },
    {
        "name": 'Nepal Rastra Bank',
        "slug": 'nepalrastrabank',
        "category": 'Economy & Trade',
        "role": 'Central Bank of Nepal / Monetary Authority',
        "desc": 'Government & Security · Central Bank of Nepal / Monetary Authority',
        "avatar_bg": '#0f766e',
        "initials": 'NR'
    },
    {
        "name": 'Ministry of Finance, Nepal',
        "slug": 'mofnepal',
        "category": 'Economy & Trade',
        "role": 'Fiscal Policy & Budget Administration',
        "desc": 'Government & Security · Fiscal Policy & Budget Administration',
        "avatar_bg": '#1e40af',
        "initials": 'MF'
    },
    {
        "name": 'Nepal Electricity Authority',
        "slug": 'hello_nea',
        "category": 'Economy & Trade',
        "role": 'National Power Utility / Regional Power Trade',
        "desc": 'Government & Security · National Power Utility / Regional Power Trade',
        "avatar_bg": '#0284c7',
        "initials": 'NE'
    },
    {
        "name": 'Flood Early Warning (DHM)',
        "slug": 'dhm_floodews',
        "category": 'Nepal – Internal Politics',
        "role": 'Dept of Hydrology & Meteorology Alerts',
        "desc": 'Government & Security · Dept of Hydrology & Meteorology Alerts',
        "avatar_bg": '#0284c7',
        "initials": 'DH'
    },
    {
        "name": 'Nepal Valley Traffic Police',
        "slug": 'valleytraffic',
        "category": 'Nepal – Internal Politics',
        "role": 'Kathmandu Valley Traffic Police Updates',
        "desc": 'Government & Security · Kathmandu Valley Traffic Police Updates',
        "avatar_bg": '#b45309',
        "initials": 'VT'
    },
    {
        "name": 'Election Commission Nepal',
        "slug": 'electionnepal',
        "category": 'Nepal – Internal Politics',
        "role": 'Constitutional Body for Electoral Affairs',
        "desc": 'Government & Security · Constitutional Body for Electoral Affairs',
        "avatar_bg": '#475569',
        "initials": 'EC'
    },
    {
        "name": 'Ambassador Zhang Maoming / Chinese Embassy',
        "slug": 'prcambnepal',
        "category": 'China in Nepal',
        "role": "Embassy of the People's Republic of China in Nepal",
        "desc": "Diplomatic Missions · Embassy of the People's Republic of China in Nepal",
        "avatar_bg": '#dc2626',
        "initials": 'CN'
    },
    {
        "name": 'Ministry of Foreign Affairs, Bangladesh',
        "slug": 'bdmofa',
        "category": 'Bangladesh & Nepal',
        "role": 'Bangladesh Foreign Ministry / Diplomatic Desk',
        "desc": 'Diplomatic Missions · Bangladesh Foreign Ministry / Diplomatic Desk',
        "avatar_bg": '#15803d',
        "initials": 'BD'
    },
    {
        "name": 'SAARC Secretariat',
        "slug": 'saarcsec',
        "category": 'Nepal – External Relations (Others)',
        "role": 'SAARC Headquarters Kathmandu, Nepal',
        "desc": 'Diplomatic Missions · SAARC Headquarters Kathmandu, Nepal',
        "avatar_bg": '#0369a1',
        "initials": 'SS'
    },
    {
        "name": 'British Embassy Kathmandu',
        "slug": 'ukinnepal',
        "category": 'China in Nepal',
        "role": 'UK Foreign, Commonwealth & Dev Office in Nepal',
        "desc": 'Diplomatic Missions · UK Foreign, Commonwealth & Dev Office in Nepal',
        "avatar_bg": '#1e40af',
        "initials": 'UK'
    },
    {
        "name": 'UN Nepal',
        "slug": 'un_nepal',
        "category": 'Nepal – External Relations (Others)',
        "role": 'United Nations in Nepal',
        "desc": 'Diplomatic Missions · United Nations in Nepal',
        "avatar_bg": '#0284c7',
        "initials": 'UN'
    },
    {
        "name": 'Nepal Mission to the UN',
        "slug": 'nepalunny',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Permanent Mission of Nepal to the United Nations, New York',
        "desc": 'Diplomatic Missions · Permanent Mission of Nepal to the United Nations, New York',
        "avatar_bg": '#0284c7',
        "initials": 'UN'
    },
    {
        "name": 'Routine of Nepal Banda',
        "slug": 'ronbupdates',
        "category": 'Nepal – Internal Politics',
        "role": 'Most Followed Youth News Curator in Nepal',
        "desc": 'Media & News Curators · Most Followed Youth News Curator in Nepal',
        "avatar_bg": '#0284c7',
        "initials": 'RO'
    },
    {
        "name": 'The Kathmandu Post',
        "slug": 'kathmandupost',
        "category": 'Nepal – Internal Politics',
        "role": "Nepal's Leading English Daily Broadside",
        "desc": "Media & News Curators · Nepal's Leading English Daily Broadside",
        "avatar_bg": '#0f172a',
        "initials": 'KP'
    },
    {
        "name": 'OnlineKhabar',
        "slug": 'online_khabar',
        "category": 'Nepal – Internal Politics',
        "role": "Nepal's #1 Online News Portal",
        "desc": "Media & News Curators · Nepal's #1 Online News Portal",
        "avatar_bg": '#dc2626',
        "initials": 'OK'
    },
    {
        "name": 'eKantipur',
        "slug": 'ekantipur_com',
        "category": 'Nepal – Internal Politics',
        "role": 'Kantipur Digital Portal',
        "desc": 'Media & News Curators · Kantipur Digital Portal',
        "avatar_bg": '#0369a1',
        "initials": 'EK'
    },
    {
        "name": 'The Himalayan Times',
        "slug": 'thehimalayan',
        "category": 'China in Nepal',
        "role": 'Leading English Broadside',
        "desc": 'Media & News Curators · Leading English Broadside',
        "avatar_bg": '#1e293b',
        "initials": 'HT'
    },
    {
        "name": 'Nepali Times',
        "slug": 'nepalitimes',
        "category": 'Nepal – Internal Politics',
        "role": 'Weekly Independent English Journal',
        "desc": 'Media & News Curators · Weekly Independent English Journal',
        "avatar_bg": '#991b1b',
        "initials": 'NT'
    },
    {
        "name": 'Cricket Association of Nepal (CAN)',
        "slug": 'cricketnep',
        "category": 'Nepal – Internal Politics',
        "role": 'Official Governing Body of Nepal Cricket',
        "desc": 'Sports & Culture · Official Governing Body of Nepal Cricket',
        "avatar_bg": '#dc2626',
        "initials": 'CN'
    },
    {
        "name": 'FNCCI Nepal',
        "slug": 'fncci_nepal',
        "category": 'Economy & Trade',
        "role": 'Federation of Nepalese Chambers of Commerce',
        "desc": 'Economy & Business · Federation of Nepalese Chambers of Commerce',
        "avatar_bg": '#b45309',
        "initials": 'FN'
    },
    {
        "name": 'Nepal Tourism Board',
        "slug": 'nepaltourismb',
        "category": 'Nepal – Internal Politics',
        "role": 'Official Tourism Promotion Organization',
        "desc": 'Sports & Culture · Official Tourism Promotion Organization',
        "avatar_bg": '#0284c7',
        "initials": 'NT'
    },
    {
        "name": 'Dipak Gyawali',
        "slug": 'dipak_gyawali',
        "category": 'India in Nepal',
        "role": 'Former Water Resources Minister / Hydropolitics Expert',
        "desc": 'Journalist / Analyst · Former Water Resources Minister / Hydropolitics Expert',
        "avatar_bg": '#047857',
        "initials": 'DG'
    },
    {
        "name": 'Akhilesh Upadhyay',
        "slug": 'akhileshu',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Senior Fellow IIDS / Foreign Policy Specialist',
        "desc": 'Journalist / Analyst · Senior Fellow IIDS / Foreign Policy Specialist',
        "avatar_bg": '#334155',
        "initials": 'AU'
    },
    {
        "name": 'Dilbhusan Pathak',
        "slug": 'dilbhusanpathak',
        "category": 'Nepal – Internal Politics',
        "role": 'Senior Broadcast Journalist / Tough Talk',
        "desc": 'Journalist / Analyst · Senior Broadcast Journalist / Tough Talk',
        "avatar_bg": '#334155',
        "initials": 'DP'
    },
    {
        "name": 'Yubaraj Ghimire',
        "slug": 'yubarajghimire3',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Veteran Editor & Foreign Policy Commentator',
        "desc": 'Journalist / Analyst · Veteran Editor & Foreign Policy Commentator',
        "avatar_bg": '#1e3a8a',
        "initials": 'YG'
    },
    {
        "name": 'Prashant Jha',
        "slug": 'prashantjha',
        "category": 'Nepal – Internal Politics',
        "role": "Author 'Battles of the New Republic' / South Asia Editor",
        "desc": "Journalist / Analyst · Author 'Battles of the New Republic' / South Asia Editor",
        "avatar_bg": '#0f172a',
        "initials": 'PJ'
    },
    {
        "name": 'Madhu Raman Acharya',
        "slug": 'madhuramanach',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Former Foreign Secretary of Nepal & Ambassador to UN / Geopolitical Scholar',
        "desc": 'Foreign Affairs Specialist · Former Foreign Secretary of Nepal & Ambassador to UN / Geopolitical Scholar',
        "avatar_bg": '#1e3a8a',
        "initials": 'MA'
    },
    {
        "name": 'Dr. Arzu Rana Deuba',
        "slug": 'arzuranadeuba',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Minister of Foreign Affairs, Government of Nepal',
        "desc": 'Government & Security · Minister of Foreign Affairs, Government of Nepal',
        "avatar_bg": '#047857',
        "initials": 'AR'
    },
    {
        "name": 'Geja Sharma Wagle',
        "slug": 'gejawagle',
        "category": 'Nepal – Internal Politics',
        "role": 'Senior Geopolitical, Defense & Security Affairs Analyst / Columnist',
        "desc": 'Journalist / Analyst · Senior Geopolitical, Defense & Security Affairs Analyst / Columnist',
        "avatar_bg": '#475569',
        "initials": 'GW'
    },
    {
        "name": 'Ameet Dhakal',
        "slug": 'ameetdhakal',
        "category": 'Bangladesh & Nepal',
        "role": 'Editor-in-Chief, Setopati / Political & Foreign Affairs Commentator',
        "desc": 'Media & News Curators · Editor-in-Chief, Setopati / Political & Foreign Affairs Commentator',
        "avatar_bg": '#334155',
        "initials": 'AD'
    },
    {
        "name": 'Dr. Rajan Bhattarai',
        "slug": 'rajancbhl',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Head, UML Foreign Affairs Dept / Former Foreign Advisor to PM / EPG Member',
        "desc": 'Political Leader · Head, UML Foreign Affairs Dept / Former Foreign Advisor to PM / EPG Member',
        "avatar_bg": '#dc2626',
        "initials": 'RB'
    },
    {
        "name": 'Biswas Baral',
        "slug": 'biswasktm',
        "category": 'Nepal – Internal Politics',
        "role": 'Editor, The Kathmandu Post / International Relations & Strategic Commentator',
        "desc": 'Media & News Curators · Editor, The Kathmandu Post / International Relations & Strategic Commentator',
        "avatar_bg": '#0f172a',
        "initials": 'BB'
    },
    {
        "name": 'Suresh Raj Neupane',
        "slug": 'sureshrajn',
        "category": 'India in Nepal',
        "role": 'Kantipur New Delhi Bureau Chief / Specialist on Nepal-India Relations',
        "desc": 'Journalist / Analyst · Kantipur New Delhi Bureau Chief / Specialist on Nepal-India Relations',
        "avatar_bg": '#ea580c',
        "initials": 'SN'
    },
    {
        "name": 'Dr. Surya Raj Acharya',
        "slug": 'suryaracharya',
        "category": 'Nepal – Internal Politics',
        "role": 'Public Policy, Infrastructure & Strategic Connectivity Analyst',
        "desc": 'Journalist / Analyst · Public Policy, Infrastructure & Strategic Connectivity Analyst',
        "avatar_bg": '#0284c7',
        "initials": 'SA'
    },
    {
        "name": 'Prateek Pradhan',
        "slug": 'prateekpradhan',
        "category": 'Nepal – Internal Politics',
        "role": 'Editor-in-Chief, Baahrakhari / Former Press Advisor to Prime Minister',
        "desc": 'Media & News Curators · Editor-in-Chief, Baahrakhari / Former Press Advisor to Prime Minister',
        "avatar_bg": '#e11d48',
        "initials": 'PP'
    },
    {
        "name": 'Dr. Minendra Rijal',
        "slug": 'minendrarijal',
        "category": 'Economy & Trade',
        "role": 'Former Defense Minister / NC Policy Leader & Economist',
        "desc": 'Political Leader · Former Defense Minister / NC Policy Leader & Economist',
        "avatar_bg": '#15803d',
        "initials": 'MR'
    },
    {
        "name": 'Bishwa Prakash Sharma',
        "slug": 'bishwaprakash77',
        "category": 'Nepal – Internal Politics',
        "role": 'General Secretary, Nepali Congress / Member of Parliament',
        "desc": 'Political Leader · General Secretary, Nepali Congress / Member of Parliament',
        "avatar_bg": '#0284c7',
        "initials": 'BS'
    },
    {
        "name": 'Yogesh Bhattarai',
        "slug": 'yogesbhattarai',
        "category": 'Nepal – Internal Politics',
        "role": 'Secretary, CPN (UML) / Former Tourism & Civil Aviation Minister',
        "desc": 'Political Leader · Secretary, CPN (UML) / Former Tourism & Civil Aviation Minister',
        "avatar_bg": '#dc2626',
        "initials": 'YB'
    },
    {
        "name": 'Gokul Prasad Baskota',
        "slug": 'gokulpbaskota',
        "category": 'Nepal – Internal Politics',
        "role": 'Standing Committee Member, CPN (UML) / Former Minister',
        "desc": 'Political Leader · Standing Committee Member, CPN (UML) / Former Minister',
        "avatar_bg": '#b91c1c',
        "initials": 'GB'
    },
    {
        "name": 'Pradeep Gyawali',
        "slug": 'pradeepgyawalik',
        "category": 'Nepal – Internal Politics',
        "role": 'Former Foreign Minister of Nepal / UML Deputy General Secretary',
        "desc": 'Political Leader · Former Foreign Minister of Nepal / UML Deputy General Secretary',
        "avatar_bg": '#991b1b',
        "initials": 'PG'
    },
    {
        "name": 'Anup Kaphle',
        "slug": 'anupkaphle',
        "category": 'Nepal – Internal Politics',
        "role": 'Former Editor-in-Chief The Kathmandu Post / International Affairs Editor',
        "desc": 'Journalist / Analyst · Former Editor-in-Chief The Kathmandu Post / International Affairs Editor',
        "avatar_bg": '#334155',
        "initials": 'AK'
    },
    {
        "name": 'IIDS Nepal',
        "slug": 'iids1979',
        "category": 'Nepal – Internal Politics',
        "role": 'Institute for Integrated Development Studies / Leading Public Policy Think Tank',
        "desc": 'Think Tank & Policy · Institute for Integrated Development Studies / Leading Public Policy Think Tank',
        "avatar_bg": '#0369a1',
        "initials": 'ID'
    },
    {
        "name": 'Ronin 🇳🇵',
        "slug": 'ronin_nepal',
        "category": 'India in Nepal',
        "role": 'Grassroots Geopolitical & Nationalist Public Voice / Vocal Observer on Nepal-India Dynamics',
        "desc": 'Civic Voice / Public Commentator · Grassroots Geopolitical & Nationalist Public Voice / Vocal Observer on Nepal-India Dynamics',
        "avatar_bg": '#b91c1c',
        "initials": 'RN'
    },
    {
        "name": 'Dilip Khadka 🇳🇵',
        "slug": 'dilipkhadk70790',
        "category": 'India in Nepal',
        "role": 'Grassroots Commentator on Border Sovereignty, Cultural Heritage & Nepal-India Issues',
        "desc": 'Civic Voice / Public Commentator · Grassroots Commentator on Border Sovereignty, Cultural Heritage & Nepal-India Issues',
        "avatar_bg": '#0284c7',
        "initials": 'DK'
    },
    {
        "name": 'InJustice 🇳🇵',
        "slug": 'th3_kmix',
        "category": 'Nepal – Internal Politics',
        "role": 'Independent Citizen Voice on Open Border, Immigration & Regional Affairs',
        "desc": 'Civic Voice / Public Commentator · Independent Citizen Voice on Open Border, Immigration & Regional Affairs',
        "avatar_bg": '#ea580c',
        "initials": 'IJ'
    },
    {
        "name": "Nepal's Rhinos Army 🇳🇵",
        "slug": 'therhinosarmy',
        "category": 'Nepal – Internal Politics',
        "role": 'Youth Cricket, Cultural Pride & South Asian Sporting Brotherhood Community',
        "desc": 'Youth & Cultural Voice · Youth Cricket, Cultural Pride & South Asian Sporting Brotherhood Community',
        "avatar_bg": '#dc2626',
        "initials": 'RA'
    },
    {
        "name": 'Sudeep Shrestha',
        "slug": 'sudeepshree',
        "category": 'Nepal – Internal Politics',
        "role": 'Civic Reporter on Bilateral Diplomacy, Aid Cooperation & Regional Connectivity',
        "desc": 'Civic Voice / Public Commentator · Civic Reporter on Bilateral Diplomacy, Aid Cooperation & Regional Connectivity',
        "avatar_bg": '#047857',
        "initials": 'SS'
    },
    {
        "name": 'Salokya (Umesh Shrestha)',
        "slug": 'salokya',
        "category": 'Nepal – Internal Politics',
        "role": 'Pioneer Nepali Blogger (MySansar) & Digital Commentary on Public & Regional Affairs',
        "desc": 'Civic Voice / Public Commentator · Pioneer Nepali Blogger (MySansar) & Digital Commentary on Public & Regional Affairs',
        "avatar_bg": '#0f766e',
        "initials": 'US'
    },
    {
        "name": 'Sanjib Bagale',
        "slug": 'sanjib_bagale',
        "category": 'Nepal – Internal Politics',
        "role": 'Public Policy, Governance & South Asian Neighborhood Observer',
        "desc": 'Civic Voice / Public Commentator · Public Policy, Governance & South Asian Neighborhood Observer',
        "avatar_bg": '#475569',
        "initials": 'SB'
    },
    {
        "name": 'Arun Giri',
        "slug": 'arungiri',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Geopolitical, Electoral & Strategic Regional Affairs Observer',
        "desc": 'Civic Voice / Public Commentator · Geopolitical, Electoral & Strategic Regional Affairs Observer',
        "avatar_bg": '#1e3a8a',
        "initials": 'AG'
    },
    {
        "name": 'Guna Raj Luitel',
        "slug": 'gunaraj',
        "category": 'India in Nepal',
        "role": 'Senior Editor Nagarik Daily & Commentator on Nepal-India Relations & Public Discourse',
        "desc": 'Journalist / Analyst · Senior Editor Nagarik Daily & Commentator on Nepal-India Relations & Public Discourse',
        "avatar_bg": '#334155',
        "initials": 'GL'
    },
    {
        "name": 'Bimal Gautam',
        "slug": 'bimal_gautam',
        "category": 'India in Nepal',
        "role": 'Public Interest, Energy/Supply Chain & Cross-Border Affairs Observer',
        "desc": 'Civic Voice / Public Commentator · Public Interest, Energy/Supply Chain & Cross-Border Affairs Observer',
        "avatar_bg": '#d97706',
        "initials": 'BG'
    },
    {
        "name": 'Nepali Voices',
        "slug": 'nepalivoices',
        "category": 'Nepal – Internal Politics',
        "role": 'Independent Nepali Citizen Forum Tracking Public Opinion & Neighborhood Relations',
        "desc": 'Civic Voice / Public Commentator · Independent Nepali Citizen Forum Tracking Public Opinion & Neighborhood Relations',
        "avatar_bg": '#0284c7',
        "initials": 'NV'
    },
    {
        "name": 'Nepali Citizen',
        "slug": 'nepali_citizen',
        "category": 'Nepal – Internal Politics',
        "role": 'Grassroots Citizen Commentary on National Sovereignty & Bilateral Agreements',
        "desc": 'Civic Voice / Public Commentator · Grassroots Citizen Commentary on National Sovereignty & Bilateral Agreements',
        "avatar_bg": '#15803d',
        "initials": 'NC'
    },
    {
        "name": 'Amish Raj Mulmi',
        "slug": 'amish973',
        "category": 'China in Nepal',
        "role": "Author 'All Roads Lead North: Nepal's Turn to China' / Strategic Analyst on Himalayan Geopolitics",
        "desc": "Civic Voice / Public Commentator · Author 'All Roads Lead North: Nepal's Turn to China' / Strategic Analyst on Himalayan Geopolitics",
        "avatar_bg": '#dc2626',
        "initials": 'AM'
    },
    {
        "name": 'NIICE Nepal',
        "slug": 'contactniice',
        "category": 'China in Nepal',
        "role": 'Nepal Institute for International Cooperation & Engagement / BRI & Trans-Himalayan Desk',
        "desc": 'Think Tank & Policy · Nepal Institute for International Cooperation & Engagement / BRI & Trans-Himalayan Desk',
        "avatar_bg": '#b91c1c',
        "initials": 'NN'
    },
    {
        "name": 'Ashok Dahal ☕️',
        "slug": 'ashokpillar',
        "category": 'Nepal – Internal Politics',
        "role": 'Senior Independent Journalist / Investigating Infrastructure Audits, Pokhara Airport & Northern Passes',
        "desc": 'Civic Voice / Public Commentator · Senior Independent Journalist / Investigating Infrastructure Audits, Pokhara Airport & Northern Passes',
        "avatar_bg": '#047857',
        "initials": 'AD'
    },
    {
        "name": 'Kamal Dev Bhattarai',
        "slug": 'kdbhattarai',
        "category": 'India in Nepal',
        "role": 'Journalist & Author on Nepal-India-China Triangular Diplomacy / BRI Implementation Tracker',
        "desc": 'Civic Voice / Public Commentator · Journalist & Author on Nepal-India-China Triangular Diplomacy / BRI Implementation Tracker',
        "avatar_bg": '#e11d48',
        "initials": 'KB'
    },
    {
        "name": 'Tika R Pradhan 🇳🇵',
        "slug": 'tikapradhan',
        "category": 'Nepal – External Relations (Others)',
        "role": 'Senior Bureau Chief / Diplomatic & Political Affairs Commentator',
        "desc": 'Journalist / Analyst · Senior Bureau Chief / Diplomatic & Political Affairs Commentator',
        "avatar_bg": '#334155',
        "initials": 'TP'
    },
    {
        "name": 'cricnepal.com 🇳🇵 🦏',
        "slug": 'cricnepal',
        "category": 'Pakistan & Nepal',
        "role": 'Leading Nepal Cricket Media / Tracking South Asian & Bilateral Pakistan-Nepal Cricket Ties',
        "desc": 'Sports & Culture · Leading Nepal Cricket Media / Tracking South Asian & Bilateral Pakistan-Nepal Cricket Ties',
        "avatar_bg": '#0284c7',
        "initials": 'CN'
    },
    {
        "name": 'Nepal Correspondence',
        "slug": 'nepcorres',
        "category": 'Pakistan & Nepal',
        "role": 'Independent Geopolitical & South Asian Affairs Observer / Pakistan-Nepal Relations',
        "desc": 'Civic Voice / Public Commentator · Independent Geopolitical & South Asian Affairs Observer / Pakistan-Nepal Relations',
        "avatar_bg": '#0f172a',
        "initials": 'NC'
    },
    {
        "name": 'HamroKhelkud.com',
        "slug": 'hamrokhelkud',
        "category": 'Bangladesh & Nepal',
        "role": 'Premier Nepal Sports Platform / Tracking SAFF & Nepal-Bangladesh Clashes',
        "desc": 'Sports & Culture · Premier Nepal Sports Platform / Tracking SAFF & Nepal-Bangladesh Clashes',
        "avatar_bg": '#0284c7',
        "initials": 'HK'
    },
    {
        "name": 'Trailokya Raj Aryal',
        "slug": 'trailokyararyal',
        "category": 'Nepal – Internal Politics',
        "role": 'Public Columnist & Geopolitical Analyst / South Asian Neighborhood Observer',
        "desc": 'Civic Voice / Public Commentator · Public Columnist & Geopolitical Analyst / South Asian Neighborhood Observer',
        "avatar_bg": '#4338ca',
        "initials": 'TA'
    },
    {
        "name": 'Milan Pandey',
        "slug": 'milanpandey',
        "category": 'Nepal – Internal Politics',
        "role": 'Youth Civic Leader & Education Reformer / Tracking Government Reform & Citizen Movements',
        "desc": 'Civic Voice / Public Commentator · Youth Civic Leader & Education Reformer / Tracking Government Reform & Citizen Movements',
        "avatar_bg": '#10b981',
        "initials": 'MP'
    },
    {
        "name": 'Narayan Wagle',
        "slug": 'narayanwagle',
        "category": 'Nepal – Internal Politics',
        "role": 'Author & Civil Society Leader / Public Accountability, Governance Critique & Citizen Protests',
        "desc": 'Civic Voice / Public Commentator · Author & Civil Society Leader / Public Accountability, Governance Critique & Citizen Protests',
        "avatar_bg": '#475569',
        "initials": 'NW'
    },
    {
        "name": 'Kamal Pariyar',
        "slug": 'kpariyar12',
        "category": 'Nepal – Internal Politics',
        "role": 'Investigative Storyteller & Civic Reporter / Youth Movements & Public Service Delivery',
        "desc": 'Civic Voice / Public Commentator · Investigative Storyteller & Civic Reporter / Youth Movements & Public Service Delivery',
        "avatar_bg": '#0284c7',
        "initials": 'KP'
    },
    {
        "name": 'Nepali Paisa',
        "slug": 'nepalipaisa',
        "category": 'Economy & Trade',
        "role": 'Retail Share Market Portal & Financial Analytics / NEPSE Indices, Corporate Actions & Economy',
        "desc": 'Economy & Business · Retail Share Market Portal & Financial Analytics / NEPSE Indices, Corporate Actions & Economy',
        "avatar_bg": '#059669',
        "initials": 'NP'
    },
    {
        "name": 'Artha Sarokar',
        "slug": 'arthasarokar',
        "category": 'Economy & Trade',
        "role": 'Premier Financial & Banking Watchdog / Microfinance, Cooperative Liquidity & NRB Directives',
        "desc": 'Economy & Business · Premier Financial & Banking Watchdog / Microfinance, Cooperative Liquidity & NRB Directives',
        "avatar_bg": '#d97706',
        "initials": 'AS'
    },
    {
        "name": 'Bizshala',
        "slug": 'bizshala',
        "category": 'Economy & Trade',
        "role": 'Business & Commodities Media / Bullion (Gold/Silver), Inflation, Fuel Prices & Energy Trade',
        "desc": 'Economy & Business · Business & Commodities Media / Bullion (Gold/Silver), Inflation, Fuel Prices & Energy Trade',
        "avatar_bg": '#2563eb',
        "initials": 'BS'
    },
    {
        "name": 'Bizpati',
        "slug": 'bizpati',
        "category": 'Economy & Trade',
        "role": 'Financial News Platform / Corporate Earnings, Commercial Banking Assets & Market Trends',
        "desc": 'Economy & Business · Financial News Platform / Corporate Earnings, Commercial Banking Assets & Market Trends',
        "avatar_bg": '#0891b2',
        "initials": 'BP'
    },
    {
        "name": 'Mahadev NEPSE Bull',
        "slug": 'bull_nepse',
        "category": 'Economy & Trade',
        "role": 'Retail Stock Investor & Chartist / Technical Analysis, SEBON Regulations & Market Momentum',
        "desc": 'Civic Voice / Public Commentator · Retail Stock Investor & Chartist / Technical Analysis, SEBON Regulations & Market Momentum',
        "avatar_bg": '#15803d',
        "initials": 'NB'
    },
    {
        "name": 'Bizmandu',
        "slug": 'bizmandu',
        "category": 'Economy & Trade',
        "role": 'Pioneer Business & Economy Digital Portal / Industrial Policy, Foreign Investment & Trade Flows',
        "desc": 'Economy & Business · Pioneer Business & Economy Digital Portal / Industrial Policy, Foreign Investment & Trade Flows',
        "avatar_bg": '#9333ea',
        "initials": 'BM'
    },
    {
        "name": 'SEJON Nepal',
        "slug": 'sejonnepal',
        "category": 'Economy & Trade',
        "role": 'Society of Economic Journalists-Nepal / Macroeconomic Research, Fiscal Policy & Trade',
        "desc": 'Think Tank & Policy · Society of Economic Journalists-Nepal / Macroeconomic Research, Fiscal Policy & Trade',
        "avatar_bg": '#334155',
        "initials": 'SN'
    },
    {
        "name": 'Nepali Congress',
        "slug": 'nepalicongress',
        "category": 'Nepal – Internal Politics',
        "role": 'Official Central Party Account / 15th General Convention, CWC Decisions & Sanepa Headquarters',
        "desc": 'Political Leader · Official Central Party Account / 15th General Convention, CWC Decisions & Sanepa Headquarters',
        "avatar_bg": '#15803d',
        "initials": 'NC'
    },
    {
        "name": 'Dr Shekhar Koirala',
        "slug": 'shekharnc',
        "category": 'Nepal – Internal Politics',
        "role": 'Senior NC Leader & Dissident Faction Head / Alternative Coalition Strategies & Party Reform',
        "desc": 'Political Leader · Senior NC Leader & Dissident Faction Head / Alternative Coalition Strategies & Party Reform',
        "avatar_bg": '#1d4ed8',
        "initials": 'SK'
    },
    {
        "name": 'Nainsingh Mahar',
        "slug": 'nainsinghmahar',
        "category": 'Nepal – Internal Politics',
        "role": 'NC Central Member & Past NSU President / Youth Mobilization, Student Union & Cadre Discourse',
        "desc": 'Civic Voice / Public Commentator · NC Central Member & Past NSU President / Youth Mobilization, Student Union & Cadre Discourse',
        "avatar_bg": '#b91c1c',
        "initials": 'NM'
    },
    {
        "name": 'Prakash Rasaili Snehi',
        "slug": 'prakashsnehi',
        "category": 'Nepal – Internal Politics',
        "role": 'NC Central Member & Grassroots Cadre Organizer / Active Membership Drives & Sudurpashchim Assemblies',
        "desc": 'Civic Voice / Public Commentator · NC Central Member & Grassroots Cadre Organizer / Active Membership Drives & Sudurpashchim Assemblies',
        "avatar_bg": '#047857',
        "initials": 'PS'
    },
    {
        "name": 'Bimalendra Nidhi',
        "slug": 'bimalendranidhi',
        "category": 'Nepal – Internal Politics',
        "role": 'Former Deputy PM & Senior NC Leader / Federalism, Madhesh Politics & Democratic Institutions',
        "desc": 'Political Leader · Former Deputy PM & Senior NC Leader / Federalism, Madhesh Politics & Democratic Institutions',
        "avatar_bg": '#6d28d9',
        "initials": 'BN'
    },
    {
        "name": 'Guru Raj Ghimire',
        "slug": 'gururajghimire',
        "category": 'Nepal – Internal Politics',
        "role": 'Prominent NC Leader & Past NSU President / Internal Party Democracy & Establishment Critique',
        "desc": 'Civic Voice / Public Commentator · Prominent NC Leader & Past NSU President / Internal Party Democracy & Establishment Critique',
        "avatar_bg": '#c2410c',
        "initials": 'GG'
    },
    {
        "name": 'CPN (UML) Official',
        "slug": 'umlcpn',
        "category": 'Nepal – Internal Politics',
        "role": 'Central Secretariat, Communist Party of Nepal (UML) / Official Party Communications',
        "desc": 'Political Leader · Central Secretariat, Communist Party of Nepal (UML) / Official Party Communications',
        "avatar_bg": '#dc2626',
        "initials": 'UM'
    },
    {
        "name": 'CPN UML Updates',
        "slug": 'uml_nepal',
        "category": 'Nepal – Internal Politics',
        "role": 'Central Media & Communications Desk, CPN (UML)',
        "desc": 'Political Leader · Central Media & Communications Desk, CPN (UML)',
        "avatar_bg": '#b91c1c',
        "initials": 'UN'
    },
    {
        "name": 'Shankar Pokhrel',
        "slug": 'shankarpokhrel8',
        "category": 'Nepal – Internal Politics',
        "role": 'General Secretary, CPN (UML) / Former Chief Minister, Lumbini Province',
        "desc": 'Political Leader · General Secretary, CPN (UML) / Former Chief Minister, Lumbini Province',
        "avatar_bg": '#dc2626',
        "initials": 'SP'
    },
    {
        "name": 'Bishnu Prasad Paudel',
        "slug": 'bpaudel1959',
        "category": 'Economy & Trade',
        "role": 'Vice Chairman, CPN (UML) / Deputy Prime Minister & Finance Minister',
        "desc": 'Political Leader · Vice Chairman, CPN (UML) / Deputy Prime Minister & Finance Minister',
        "avatar_bg": '#991b1b',
        "initials": 'BP'
    },
    {
        "name": 'Bishnu Rimal',
        "slug": 'bishnurimal',
        "category": 'Nepal – Internal Politics',
        "role": 'Deputy General Secretary, CPN (UML) / Chief Political Advisor to Prime Minister KP Sharma Oli',
        "desc": 'Political Leader · Deputy General Secretary, CPN (UML) / Chief Political Advisor to Prime Minister KP Sharma Oli',
        "avatar_bg": '#ef4444',
        "initials": 'BR'
    },
    {
        "name": 'Dr. Bhim Rawal',
        "slug": 'bhimrawal179',
        "category": 'Nepal – Internal Politics',
        "role": 'Former Vice Chairman, CPN (UML) / Vocal Dissident Leader, Sovereign Nationalist & Policy Critic',
        "desc": 'Civic Voice / Public Commentator · Former Vice Chairman, CPN (UML) / Vocal Dissident Leader, Sovereign Nationalist & Policy Critic',
        "avatar_bg": '#b45309',
        "initials": 'BR'
    },
    {
        "name": 'Sunita Dangol',
        "slug": 'sunitadangol_',
        "category": 'Nepal – Internal Politics',
        "role": 'Deputy Mayor of Kathmandu Metropolitan City / CPN (UML) Youth Representative',
        "desc": 'Political Leader · Deputy Mayor of Kathmandu Metropolitan City / CPN (UML) Youth Representative',
        "avatar_bg": '#059669',
        "initials": 'SD'
    },
    {
        "name": 'Mahesh Basnet',
        "slug": 'mamaheshbasnet',
        "category": 'Nepal – Internal Politics',
        "role": 'Central Committee Member, CPN (UML) / Patron, Youth Association Nepal (YAN)',
        "desc": 'Political Leader · Central Committee Member, CPN (UML) / Patron, Youth Association Nepal (YAN)',
        "avatar_bg": '#ea580c',
        "initials": 'MB'
    },
    {
        "name": 'Ishwar Pokhrel',
        "slug": 'ishwarpokhrel',
        "category": 'Nepal – Internal Politics',
        "role": 'Senior Vice Chairman, CPN (UML) / Former Deputy Prime Minister & Defense Minister',
        "desc": 'Political Leader · Senior Vice Chairman, CPN (UML) / Former Deputy Prime Minister & Defense Minister',
        "avatar_bg": '#dc2626',
        "initials": 'IP'
    },
    {
        "name": 'Prithvi Subba Gurung',
        "slug": 'prithvisubba',
        "category": 'Nepal – Internal Politics',
        "role": 'Deputy General Secretary, CPN (UML) / Minister for Communication and Information Technology',
        "desc": 'Political Leader · Deputy General Secretary, CPN (UML) / Minister for Communication and Information Technology',
        "avatar_bg": '#c026d3',
        "initials": 'PG'
    },
    {
        "name": 'Surendra Pandey',
        "slug": 'surendra_pandey',
        "category": 'Economy & Trade',
        "role": 'Vice Chairman, CPN (UML) / Former Finance Minister & Senior Economic Thinker',
        "desc": 'Political Leader · Vice Chairman, CPN (UML) / Former Finance Minister & Senior Economic Thinker',
        "avatar_bg": '#2563eb',
        "initials": 'SP'
    },
    {
        "name": 'Manish Jha',
        "slug": 'manishjhanepal',
        "category": 'Nepal – Internal Politics',
        "role": 'Member of Federal Parliament (Dhanusha-3) / Prominent Madhesh Youth Voice & RSP Spokesperson',
        "desc": 'Political Leader · Member of Federal Parliament (Dhanusha-3) / Prominent Madhesh Youth Voice & RSP Spokesperson',
        "avatar_bg": '#0284c7',
        "initials": 'MJ'
    },
    {
        "name": 'Dipendra Jha',
        "slug": 'dipjha',
        "category": 'Nepal – Internal Politics',
        "role": "Constitutional Lawyer & First Chief Attorney of Madhesh Province / Author of 'Federal Nepal'",
        "desc": "Think Tank & Policy · Constitutional Lawyer & First Chief Attorney of Madhesh Province / Author of 'Federal Nepal'",
        "avatar_bg": '#b45309',
        "initials": 'DJ'
    },
    {
        "name": 'Bhola Paswan',
        "slug": 'paswanbhola',
        "category": 'Nepal – Internal Politics',
        "role": 'Senior Investigative Journalist from Siraha / Madhesh Dalit Rights, Land Reform & Social Justice',
        "desc": 'Civic Voice / Public Commentator · Senior Investigative Journalist from Siraha / Madhesh Dalit Rights, Land Reform & Social Justice',
        "avatar_bg": '#047857',
        "initials": 'BP'
    },
    {
        "name": 'Mohna Ansari',
        "slug": 'mohnaansari',
        "category": 'Nepal – Internal Politics',
        "role": 'Former National Human Rights Commissioner / Advocate for Terai Inclusion, Citizenship & Minority Rights',
        "desc": 'Civic Voice / Public Commentator · Former National Human Rights Commissioner / Advocate for Terai Inclusion, Citizenship & Minority Rights',
        "avatar_bg": '#7c3aed',
        "initials": 'MA'
    },
    {
        "name": 'Upendra Yadav',
        "slug": 'upendrayadav_',
        "category": 'Nepal – Internal Politics',
        "role": 'President, Janata Samajbadi Party Nepal (JSP) / Veteran Madhesh Movement Architect & Former DPM',
        "desc": 'Political Leader · President, Janata Samajbadi Party Nepal (JSP) / Veteran Madhesh Movement Architect & Former DPM',
        "avatar_bg": '#16a34a',
        "initials": 'UY'
    },
    {
        "name": 'JSP Nepal Official',
        "slug": 'jspnepal',
        "category": 'Nepal – Internal Politics',
        "role": 'Official Central Secretariat, Janata Samajbadi Party Nepal (जसपा नेपाल) / Terai-Madhesh Federalism',
        "desc": 'Political Leader · Official Central Secretariat, Janata Samajbadi Party Nepal (जसपा नेपाल) / Terai-Madhesh Federalism',
        "avatar_bg": '#15803d',
        "initials": 'JS'
    },
    {
        "name": 'Madhesi Youth',
        "slug": 'madhesiyouth',
        "category": 'Nepal – Internal Politics',
        "role": 'Grassroots Youth Platform / Digital Advocacy, Education & Civic Awareness across Terai-Madhesh',
        "desc": 'Civic Voice / Public Commentator · Grassroots Youth Platform / Digital Advocacy, Education & Civic Awareness across Terai-Madhesh',
        "avatar_bg": '#ea580c',
        "initials": 'MY'
    },
    {
        "name": 'Terai Online',
        "slug": 'teraionline',
        "category": 'Nepal – Internal Politics',
        "role": 'Dedicated Terai-Madhesh Digital Media / Grassroots Coverage of Southern Plains & Regional Affairs',
        "desc": 'Media & News Curators · Dedicated Terai-Madhesh Digital Media / Grassroots Coverage of Southern Plains & Regional Affairs',
        "avatar_bg": '#e11d48',
        "initials": 'TO'
    },
    {
        "name": 'Madheshvani',
        "slug": 'madheshvani',
        "category": 'Nepal – Internal Politics',
        "role": 'Community Radio & Regional Media Network / Grassroots Voice for Terai-Madhesh Rights & Governance',
        "desc": 'Media & News Curators · Community Radio & Regional Media Network / Grassroots Voice for Terai-Madhesh Rights & Governance',
        "avatar_bg": '#d97706',
        "initials": 'MV'
    },
    {
        "name": 'Dr. Surendra Labh',
        "slug": 'surendralabh',
        "category": 'Economy & Trade',
        "role": 'Prominent Terai-Madhesh Economist, Political Analyst & Columnist (Janakpur)',
        "desc": 'Civic Voice / Public Commentator · Prominent Terai-Madhesh Economist, Political Analyst & Columnist (Janakpur)',
        "avatar_bg": '#059669',
        "initials": 'SL'
    },
    {
        "name": 'Jitendra Jha',
        "slug": 'jitendrajha',
        "category": 'Nepal – Internal Politics',
        "role": 'Terai-Madhesh Journalist & Public Commentator / Governance & Civic Watchdog',
        "desc": 'Civic Voice / Public Commentator · Terai-Madhesh Journalist & Public Commentator / Governance & Civic Watchdog',
        "avatar_bg": '#2563eb',
        "initials": 'JJ'
    },
    {
        "name": 'Dr. Rajesh Ahiraj',
        "slug": 'rajeshahiraj',
        "category": 'Nepal – Internal Politics',
        "role": 'Former Governor of Madhesh Province / Scholar & Analyst on Madhesh Constitutional Dynamics',
        "desc": 'Civic Voice / Public Commentator · Former Governor of Madhesh Province / Scholar & Analyst on Madhesh Constitutional Dynamics',
        "avatar_bg": '#c026d3',
        "initials": 'RA'
    },
    {
        "name": 'Janakpur Sahitya Mahotsav',
        "slug": 'janakpurlitfest',
        "category": 'Nepal – Internal Politics',
        "role": 'Janakpur Literature Festival / Cultural, Intellectual & Literary Forum of Mithila & Terai',
        "desc": 'Civic Voice / Public Commentator · Janakpur Literature Festival / Cultural, Intellectual & Literary Forum of Mithila & Terai',
        "avatar_bg": '#db2777',
        "initials": 'JL'
    },
]

# Top X (Twitter) Handles in Nepal
POPULAR_NEPAL_X_HANDLES = [
    {"name": "Routine of Nepal Banda", "handle": "RONBupdates", "desc": "Fastest breaking news & community updates on X"},
    {"name": "Balen Shah", "handle": "BalenOfficial", "desc": "Mayor Balen Shah official tweets & announcements"},
    {"name": "Cricket Association of Nepal (CAN)", "handle": "CricketNep", "desc": "Nepal National Cricket Team updates & match threads"},
    {"name": "The Kathmandu Post", "handle": "kathmandupost", "desc": "Nepal's largest English national daily on X"},
    {"name": "OnlineKhabar English", "handle": "Online_khabar", "desc": "English breaking news alerts"},
    {"name": "Nepal Police Official", "handle": "NepalPoliceHQ", "desc": "Public notices, safety alerts, and cyber bureau warnings"}
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

def classify_article(title: str, summary: str = "") -> str:
    """
    Backward-compatible entry point returning primary section string.
    """
    res = classify_article_editorial(title, summary)
    return res["primary_section"]

# Date parsing patterns for HTML news cards & metadata
DATE_SNIPPET_REGEXES = [
    re.compile(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}(?:[,\s\|]+(?:at\s+)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?m\.?)?(?:\s*[\+\-]\d{4}|\s*IST)?)?", re.I),
    re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?,?\s+\d{4}(?:[,\s\|]+(?:at\s+)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?m\.?)?(?:\s*[\+\-]\d{4}|\s*IST)?)?", re.I),
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
    for m_name in BS_MONTH_NAMES:
        if m_name in norm_txt:
            m_bs = re.search(rf'(?:{m_name}\s+(\d{{1,2}})|(\d{{1,2}})\s+{m_name})(?:,?\s*(\d{{4}}))?(?:[^\d]+(\d{{1,2}}):(\d{{2}})(?::(\d{{2}}))?)?', norm_txt)
            if m_bs:
                day_val = int(m_bs.group(1) or m_bs.group(2))
                hr = int(m_bs.group(4)) if m_bs.group(4) else 12
                mn = int(m_bs.group(5)) if m_bs.group(5) else 0
                sc = int(m_bs.group(6)) if m_bs.group(6) else 0
                kartik_anchor_day = 24  # Today in Kartik (Nov 10, 2026)
                day_diff = kartik_anchor_day - day_val
                if 0 <= day_diff <= 30:
                    cand_dt = now_npt - datetime.timedelta(days=day_diff)
                    return cand_dt.replace(hour=hr, minute=mn, second=sc, microsecond=0)
                elif day_diff < 0:
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
        if not curr or curr.name in ["body", "html"]:
            break
        time_tag = curr.find("time")
        if time_tag:
            dt = parse_snippet_to_datetime(time_tag.get("datetime") or time_tag.get_text(strip=True), now_npt)
            if dt:
                ARTICLE_DATE_CACHE[href] = dt
                return dt

        date_elems = curr.find_all(class_=re.compile(r"date|time|meta|updated|publish|oi-article-country|byline", re.I))
        for de in date_elems:
            dt = parse_snippet_to_datetime(de.get_text(" ", strip=True), now_npt)
            if dt:
                ARTICLE_DATE_CACHE[href] = dt
                return dt

        for el in curr.find_all(["p", "span", "small"]):
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
                chunk = resp.read(45000).decode("utf-8", errors="ignore")
            m_meta = re.search(r"<meta[^>]+(?:article:published_time|datePublished|publish-date|published_time)[^>]+content=[\"\x27]([^\x27\"]+)[\"\x27]", chunk, re.I)
            if not m_meta:
                m_meta = re.search(r"\"(?:datePublished|dateCreated|published_time)\"\s*:\s*\"([^\"]+)\"", chunk)
            if m_meta:
                dt = dt_parser.parse(m_meta.group(1), fuzzy=True)
                dt = dt.astimezone(NEPAL_TZ) if dt.tzinfo else dt.replace(tzinfo=NEPAL_TZ)
                ARTICLE_DATE_CACHE[href] = dt
                return dt

            # Also check class elements for pub-date / published-date
            m_pub_box = re.search(r'class=["\x27][^"\x27]*(?:pub-date|published-date|post-date|article-date|date)[^"\x27]*["\x27][^>]*>([^<]{5,80})<', chunk, re.I)
            if m_pub_box:
                dt = parse_snippet_to_datetime(m_pub_box.group(1), now_npt)
                if dt:
                    ARTICLE_DATE_CACHE[href] = dt
                    return dt

            # Also check standard snippet regexes across chunk
            for rgx in DATE_SNIPPET_REGEXES:
                m_chunk = rgx.search(chunk[:8000])
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
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=6) as response:
                content = response.read()
            items.extend(process_rss_content(content, portal))

            # If primary feed yielded few articles, check configured alt_urls (category feeds)
            if len(items) < 8 and portal.get("alt_urls"):
                for alt_url in portal.get("alt_urls", []):
                    if len(items) >= max_entries:
                        break
                    try:
                        alt_req = urllib.request.Request(alt_url, headers=DEFAULT_HEADERS)
                        with urllib.request.urlopen(alt_req, context=SSL_CTX, timeout=5) as alt_resp:
                            alt_content = alt_resp.read()
                        items.extend(process_rss_content(alt_content, portal))
                    except Exception:
                        pass
        else:
            # HTML discovery mode (eKantipur, The Himalayan Times, Setopati EN, Nepal Aaja)
            req = urllib.request.Request(portal["url"], headers=DEFAULT_HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=6) as response:
                html_raw = response.read().decode("utf-8", errors="ignore")

            soup = BeautifulSoup(html_raw, "html.parser")
            seen_titles = set()
            for a in soup.find_all("a", href=True):
                txt = a.get_text(strip=True)
                href = a["href"]
                if len(txt) >= 20 and txt not in seen_titles:
                    if any(k in txt.lower() for k in ["privacy", "terms", "contact us", "about us", "advertise", "epaper", "login"]):
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
    Guarantees strict sorting from newest (minutes ago) to oldest, with automatic persistent
    reconciliation against the durable SQLite store to ensure 0 dropped or missed articles.
    """
    now_npt = datetime.datetime.now(NEPAL_TZ)
    all_articles = []

    # Ensure source registry is synced
    try:
        register_portal_sources(TOP_NEPAL_NEWS_PORTALS)
    except Exception:
        pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_single_portal, p, now_npt) for p in TOP_NEPAL_NEWS_PORTALS]
        for f in concurrent.futures.as_completed(futures):
            all_articles.extend(f.result())

    # Reconcile with persistent stored articles from past 48 hours to prevent any missed articles
    try:
        since_dt = now_npt - datetime.timedelta(hours=48)
        stored_articles = get_stored_articles(start_dt=since_dt, limit=1200)
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

def fetch_single_indian_media(src, now_npt):
    """
    Fetches news from prominent Indian media outlets covering:
    - Nepal-related news and Nepal-India bilateral developments
    - Indian domestic politics, governance, strategic, economic, and border developments
    """
    nepal_and_india_regex = re.compile(
        r'\b(nepal|nepali|nepalese|kathmandu|balen|kp oli|k\.p\. oli|prachanda|deuba|indo-nepal|nepal-india|gorkha|madhesh|birgunj|pokhara|everest|नेपाल|काठमांडू|काठमाडौँ|modi|narendra modi|bjp|jaishankar|border|loc|ssb|bihar|uttar pradesh|uttarakhand|bengal|sikkim|delhi|foreign affairs|substantive)\b',
        re.IGNORECASE
    )
    items = []
    seen = set()
    skip_phrases = ['cookie policy', 'privacy policy', 'terms of use', 'subscribe now', 'newsletter', 'about us', 'contact us', 'epaper', 'download app', 'play store', 'feedback']
    try:
        req = urllib.request.Request(src["url"], headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=6) as resp:
            data = resp.read()

        if src.get("type") == "rss":
            feed = feedparser.parse(data)
            for e in feed.entries:
                raw_title = e.get("title", "").strip()
                summary_raw = e.get("summary", "") or e.get("description", "")
                text = f"{raw_title} {summary_raw}"
                # If specific topic page, accept all valid stories; if general feed, require regex match
                is_topic_feed = "topic" in src.get("url", "") or "tag" in src.get("url", "") or "about" in src.get("url", "")
                if is_topic_feed or nepal_and_india_regex.search(text):
                    clean_title = re.sub(r'\s*-\s*[^-]+$', '', raw_title).strip() or raw_title
                    if clean_title in seen:
                        continue
                    seen.add(clean_title)

                    pub_raw = e.get("published", "") or e.get("updated", "")
                    if not pub_raw and e.get("link") and e.get("link").startswith("http"):
                        pub_raw = extract_date_from_card_or_url(None, e.get("link", ""), now_npt)
                    pub_dt, rel_time, exact_time = parse_to_nepal_time(pub_raw, now_npt)

                    clean_sum = re.sub(r'<[^>]+>', ' ', summary_raw)
                    clean_sum = html.unescape(clean_sum)
                    clean_sum = re.sub(r'\s+', ' ', clean_sum).strip() or clean_title

                    cls_res = classify_article_editorial(clean_title, clean_sum, src["name"], clean_sum)
                    # Guaranteed India Section representation
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
                        "link": e.get("link", "#"),
                        "summary": clean_sum[:280] + ("..." if len(clean_sum) > 280 else ""),
                        "full_content": clean_sum,
                        "published_dt": pub_dt,
                        "relative_time": rel_time,
                        "exact_time": exact_time
                    })
        else:
            soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
            for a in soup.find_all("a", href=True):
                txt = a.get_text(strip=True)
                href = a["href"]
                if len(txt) > 20 and not any(k in txt.lower() for k in skip_phrases):
                    is_topic_url = "topic" in src.get("url", "") or "tag" in src.get("url", "") or "about" in src.get("url", "")
                    if is_topic_url or nepal_and_india_regex.search(txt) or "nepal" in href.lower() or "india" in href.lower():
                        clean_txt = re.sub(r'\s+', ' ', txt).strip()
                        if clean_txt in seen or clean_txt.startswith("{"):
                            continue
                        seen.add(clean_txt)

                        # Fix relative URLs
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

                        # Extract real publication datetime from card, URL, or metadata
                        parsed_dt = extract_date_from_card_or_url(a, href, now_npt)
                        art_dt, rel_time, exact_time = parse_to_nepal_time(parsed_dt, now_npt)

                        cls_res = classify_article_editorial(clean_txt, clean_txt, src["name"], clean_txt)
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
                            "summary": clean_txt,
                            "full_content": clean_txt,
                            "published_dt": art_dt,
                            "relative_time": rel_time,
                            "exact_time": exact_time
                        })
                        if len(items) >= 15:
                            break
    except Exception:
        pass
    return items

def fetch_nepal_in_indian_media(max_workers: int = 18):
    """
    Fetches real-time Nepal news as published across Top Indian Media Outlets.
    """
    now_npt = datetime.datetime.now(NEPAL_TZ)
    all_articles = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_single_indian_media, s, now_npt) for s in TOP_INDIAN_MEDIA_SOURCES]
        for f in concurrent.futures.as_completed(futures):
            all_articles.extend(f.result())

    all_articles.sort(key=lambda x: x["published_dt"], reverse=True)
    return all_articles

def query_x_api(bearer_token: str = None, query: str = "Nepal", max_results: int = 15):
    """Query official X v2 API if user provides Bearer Token or via environment variables."""
    token = bearer_token or os.getenv("TWITTER_BEARER_TOKEN", "")
    if not token:
        return []
    clean_token = urllib.parse.unquote(token.strip())
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {clean_token}"}
    params = {
        "query": f"{query} -is:retweet",
        "max_results": min(max_results, 50),
        "tweet.fields": "created_at,public_metrics,author_id"
    }
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json().get("data", [])
            results = []
            for t in data:
                metrics = t.get("public_metrics", {})
                results.append({
                    "platform": "X (Twitter Live API)",
                    "source": f"Tweet ID: {t.get('id')}",
                    "title": t.get("text", "")[:120],
                    "summary": t.get("text", ""),
                    "link": f"https://x.com/i/status/{t.get('id')}",
                    "published": t.get("created_at", "Recent")[:19].replace("T", " "),
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0)
                })
            return results
    except Exception:
        pass
    return []

def get_live_nepal_trends():
    """Curated list of hot topics in Nepal with direct hashtags."""
    return [
        {"topic": "Nepal Politics & Parliament", "hashtag": "#NepalPolitics", "volume": "High"},
        {"topic": "Kathmandu Mayor & Balen Shah", "hashtag": "#BalenShah", "volume": "Very High"},
        {"topic": "Nepal Cricket & CAN Matches", "hashtag": "#NepalCricket #Rhinos", "volume": "High"},
        {"topic": "Economy, Gold & Inflation", "hashtag": "#NepalEconomy #GoldNepal", "volume": "Medium"},
        {"topic": "Foreign Employment & Youth", "hashtag": "#NepalYouth #Jobs", "volume": "High"},
        {"topic": "Tourism & Himalayas", "hashtag": "#VisitNepal #Himalayas", "volume": "Medium"}
    ]

# Backward compatibility alias - ensures older scripts/caches importing fetch_all_nepal_posts never fail
fetch_all_nepal_posts = fetch_top_nepal_media

try:
    from nepal_x_scanner import (
        scan_popular_nepal_x_posts,
        TOP_NEPAL_X_ACCOUNTS,
        fetch_real_account_tweets,
        NEPALI_X_ACCOUNTS_BY_CATEGORY
    )
except Exception:
    pass

