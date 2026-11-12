"""
executive_docx_exporter.py
Reference-Based Executive Word Document (.docx) Generation Engine
for the Nepal Media & Intelligence Monitor (Analytics & Export).

Master Reference Template:
    NEPAL DAILY NEWS DIGEST – 5th November 2026.docx
    (stored at templates/NEPAL_DAILY_NEWS_DIGEST_TEMPLATE.docx)

Reproduces the exact document format, structure, section sequence,
typography, colors, shading, numbering, margins, headers, footers,
red horizontal lines, and dynamic page numbering of the reference DOCX.
"""

import os
import io
import re
import html
import json
import datetime
import zoneinfo
import urllib.request
import urllib.parse
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE

NEPAL_TZ = zoneinfo.ZoneInfo("Asia/Kathmandu")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATHS = [
    os.path.join(BASE_DIR, "templates", "NEPAL_DAILY_NEWS_DIGEST_TEMPLATE.docx"),
    "/Users/pobpkf/Downloads/NEPAL DAILY NEWS DIGEST-5th November  2026.docx",
]

# Master section sequence for NEPAL DAILY NEWS DIGEST
# Note: Any section with 0 articles is automatically omitted.
REFERENCE_NEWS_SECTIONS = [
    "INDIA IN NEPAL",
    "CHINA IN NEPAL",
    "PAKISTAN IN NEPAL",
    "BANGLADESH IN NEPAL",
    "NEPAL-INTERNAL POLITICS",
    "NEPAL-EXTERNAL",
    "ECONOMY",
]
TRENDING_SECTION_TITLE = "Today’s Top Trending News"

# Clean editorial source name mapping matching reference document conventions
SOURCE_NAME_MAP = {
    "OnlineKhabar (EN)": "Onlinekhabar",
    "OnlineKhabar (NP)": "Onlinekhabar",
    "OnlineKhabar": "Onlinekhabar",
    "NepalKhabar (EN)": "Nepalkhabar",
    "NepalKhabar": "Nepalkhabar",
    "Khabarhub (EN)": "Khabarhub",
    "Khabarhub (NP)": "Khabarhub",
    "Khabarhub": "Khabarhub",
    "Ratopati (EN)": "Ratopati",
    "Ratopati": "Ratopati",
    "Setopati (EN)": "Setopati",
    "Setopati": "Setopati",
    "Republica": "My Republica",
    "My Republica": "My Republica",
    "The Kathmandu Post": "The Kathmandu Post",
    "The Himalayan Times": "The Himalayan Times",
    "The Rising Nepal": "The Rising Nepal",
    "The Annapurna Express": "The Annapurna Express",
    "Annapurna Post": "Annapurna Post",
    "Nepali Times": "Nepali Times",
    "New Business Age": "New Business Age",
    "eKantipur": "eKantipur",
    "Gorkhapatra Online": "Gorkhapatra",
    "Nagarik News": "Nagarik News",
    "Naya Patrika": "Naya Patrika",
}

_TRANSLATION_CACHE: Dict[str, str] = {}


def _has_devanagari(text: str) -> bool:
    """Returns True if text contains Devanagari characters."""
    if not text:
        return False
    return any(0x0900 <= ord(ch) <= 0x097F for ch in text)


def _translate_ne_to_en(text: str, timeout: int = 5) -> str:
    """Translates Nepali (Devanagari) text into clean English for executive digest uniformity."""
    clean = (text or "").strip()
    if not clean or not _has_devanagari(clean):
        return clean
    if clean in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[clean]

    # Split long bodies into chunks <= 1800 chars for reliable translation
    chunks = []
    if len(clean) <= 1800:
        chunks = [clean]
    else:
        paras = clean.split("\n\n")
        cur = ""
        for p in paras:
            if len(cur) + len(p) + 2 <= 1800:
                cur = f"{cur}\n\n{p}" if cur else p
            else:
                if cur:
                    chunks.append(cur)
                cur = p[:1800]
        if cur:
            chunks.append(cur)

    translated_chunks = []
    for chunk in chunks:
        try:
            url = (
                "https://translate.googleapis.com/translate_a/single?client=gtx&sl=ne&tl=en&dt=t&q="
                + urllib.parse.quote(chunk)
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                out = "".join(seg[0] for seg in data[0] if seg and seg[0])
                translated_chunks.append(out.strip() if out else chunk)
        except Exception:
            translated_chunks.append(chunk)

    result = "\n\n".join(translated_chunks).strip()
    _TRANSLATION_CACHE[clean] = result
    return result


def format_editorial_source(raw_source: str, link: str = "") -> str:
    """Formats the portal/source name to match the reference document's (Source Name) style."""
    src = (raw_source or "").strip()
    if src in SOURCE_NAME_MAP:
        return SOURCE_NAME_MAP[src]
    # Strip (EN) / (NP) suffixes and @handles
    src = re.sub(r"\s*\((?:EN|NP)\)\s*$", "", src, flags=re.IGNORECASE).strip()
    if src in SOURCE_NAME_MAP:
        return SOURCE_NAME_MAP[src]
    if not src and link:
        low = link.lower()
        if "kathmandupost" in low:
            return "The Kathmandu Post"
        if "thehimalayantimes" in low:
            return "The Himalayan Times"
        if "myrepublica" in low:
            return "My Republica"
        if "onlinekhabar" in low:
            return "Onlinekhabar"
        if "khabarhub" in low:
            return "Khabarhub"
        if "nepalkhabar" in low:
            return "Nepalkhabar"
        if "ratopati" in low:
            return "Ratopati"
        if "setopati" in low:
            return "Setopati"
        if "risingnepal" in low:
            return "The Rising Nepal"
        if "theannapurnaexpress" in low:
            return "The Annapurna Express"
    return src or "Nepal Media"


def classify_article_to_reference_section(article: Dict[str, Any]) -> str:
    """
    Maps an article to one of the 7 ordered digest news sections:
      1. INDIA IN NEPAL
      2. CHINA IN NEPAL
      3. PAKISTAN IN NEPAL
      4. BANGLADESH IN NEPAL
      5. NEPAL-INTERNAL POLITICS
      6. NEPAL-EXTERNAL
      7. ECONOMY
    """
    raw_cat = (article.get("structured_category") or article.get("category") or article.get("primary_section") or "").strip().lower()
    stream = (article.get("stream") or "").strip().lower()
    title = (article.get("headline_english") or article.get("title") or article.get("text") or "").strip().lower()
    summary = (article.get("summary") or article.get("full_content") or "").strip().lower()[:600]
    combined = f"{title} {summary}"

    # 1. BANGLADESH IN NEPAL
    if "bangladesh" in raw_cat or any(k in combined for k in ["bangladesh", "dhaka", "yunus"]):
        return "BANGLADESH IN NEPAL"

    # 2. PAKISTAN IN NEPAL
    if "pakistan" in raw_cat or any(k in combined for k in ["pakistan", "pakistani", "islamabad", "lahore", "karachi"]):
        return "PAKISTAN IN NEPAL"

    # 3. CHINA IN NEPAL
    if "china" in raw_cat or any(k in combined for k in ["china", "chinese", "beijing", "xizang", "tibet", "bri "]):
        return "CHINA IN NEPAL"

    # 4. INDIA IN NEPAL (Indian Press stream or explicit India/Indian bilateral stories)
    has_india_kw = any(
        k in combined
        for k in [
            "india", "indian", "new delhi", "misri", "modi", "jaishankar",
            "lainchaur", "indo-nepal", "nepal-india", "bharatiya", "uttar pradesh", "bihar",
        ]
    )
    if stream == "indian press" or ("india" in raw_cat and has_india_kw) or any(
        k in title for k in ["india", "indian", "new delhi", "misri", "modi", "jaishankar", "indo-nepal", "nepal-india"]
    ):
        return "INDIA IN NEPAL"

    # 5. ECONOMY
    if (
        "economy" in raw_cat
        or "economic" in raw_cat
        or any(
            k in combined
            for k in [
                "economy", "economic", "sebon", "nepse", "stock market", "capital market",
                "oil corporation", "noc ", "petroleum", "hydropower", "megawatt", "mw ",
                "rastra bank", "nrb", "banking", "monetary", "fiscal", "budget", "revenue",
                "tax", "export", "import", "trade deficit", "remittance", "inflation",
                "investment", "industrial", "chamber of commerce", "fncci", "cni",
                "data centre", "erp system", "gold price", "interest rate", "loan",
            ]
        )
    ):
        return "ECONOMY"

    # 6. NEPAL-EXTERNAL
    if (
        "external" in raw_cat
        or "international" in raw_cat
        or any(
            k in combined
            for k in [
                "ambassador", "embassy", "foreign policy", "diplomat", "diplomatic",
                "bilateral", "united nations", "israel", "washington", "cop31", "bimstec", "saarc",
                "european union", "middle east", "gulf", "uae", "qatar", "malaysia",
                "foreign minister", "ministry of foreign affairs", "mofa", "envoy",
            ]
        )
    ):
        return "NEPAL-EXTERNAL"

    # 7. Default to NEPAL-INTERNAL POLITICS
    return "NEPAL-INTERNAL POLITICS"


def _title_tokens(title: str) -> set:
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "into", "over",
        "after", "before", "under", "nepal", "nepali", "says", "said", "will",
        "govt", "government", "minister", "prime", "news", "today", "amid",
    }
    words = re.findall(r"[a-z0-9]{3,}", (title or "").lower())
    return {w for w in words if w not in stop}


def deduplicate_and_cluster_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicates identical URLs/titles and groups closely related coverage into
    `related_links` on the lead article (matching the reference doc's 'More related news:' feature).
    Also prioritizes native English articles as lead stories when available.
    """
    # Sort so English portal articles with rich content come first within each topic
    def _quality_key(a: Dict[str, Any]) -> Tuple[int, int]:
        title = a.get("title") or ""
        content = a.get("full_content") or a.get("summary") or ""
        is_en = 0 if _has_devanagari(title) else 1
        return (is_en, len(content))

    sorted_arts = sorted(articles, key=_quality_key, reverse=True)
    clusters: List[Dict[str, Any]] = []
    seen_links = set()

    for art in sorted_arts:
        raw_t = (art.get("headline_english") or art.get("title") or art.get("text") or "").strip()
        # Skip raw scoreboard ticker widgets (e.g., 'NPL Match 22 · Nov 12...')
        if re.search(r"NPL\s+(?:Live\s+)?Match\s+\d+\s*·", raw_t, flags=re.IGNORECASE):
            continue
        link = (art.get("link") or "").strip()
        if link and link in seen_links:
            continue
        if link:
            seen_links.add(link)

        headline = (art.get("headline_english") or art.get("title") or art.get("text") or "").strip()
        tokens = _title_tokens(headline)

        matched_cluster = None
        if len(tokens) >= 3:
            for cl in clusters:
                cl_tokens = cl.get("_tokens", set())
                if not cl_tokens:
                    continue
                overlap = len(tokens & cl_tokens)
                union = len(tokens | cl_tokens)
                if overlap >= 4 or (union > 0 and (overlap / union) >= 0.55):
                    matched_cluster = cl
                    break

        if matched_cluster is not None:
            if link and link != matched_cluster.get("link") and link not in matched_cluster["related_links"]:
                matched_cluster["related_links"].append(link)
        else:
            item_copy = dict(art)
            item_copy["related_links"] = list(art.get("related_links") or [])
            item_copy["_tokens"] = tokens
            clusters.append(item_copy)

    return clusters


# ==========================================
# LOW-LEVEL OPENXML (OXML) BUILDERS
# ==========================================

def _make_rPr(
    bold: bool = False,
    italic: bool = False,
    color: Optional[str] = None,
    shd_fill: Optional[str] = None,
    rStyle: Optional[str] = None,
    sz: int = 26,
) -> OxmlElement:
    """Creates a <w:rPr> element matching the reference document's exact Times New Roman 13pt formatting."""
    rPr = OxmlElement("w:rPr")
    if rStyle:
        rs = OxmlElement("w:rStyle")
        rs.set(qn("w:val"), rStyle)
        rPr.append(rs)

    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), "Times New Roman")
    rFonts.set(qn("w:hAnsi"), "Times New Roman")
    rFonts.set(qn("w:cs"), "Times New Roman")
    rPr.append(rFonts)

    if bold:
        rPr.append(OxmlElement("w:b"))
    if italic:
        rPr.append(OxmlElement("w:i"))
    if color:
        c = OxmlElement("w:color")
        c.set(qn("w:val"), color)
        rPr.append(c)

    sz_el = OxmlElement("w:sz")
    sz_el.set(qn("w:val"), str(sz))
    rPr.append(sz_el)

    szCs_el = OxmlElement("w:szCs")
    szCs_el.set(qn("w:val"), str(sz))
    rPr.append(szCs_el)

    if shd_fill:
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), shd_fill)
        rPr.append(shd)

    return rPr


def _make_section_heading_p(title_text: str, use_left_indent: bool = False) -> OxmlElement:
    """
    Builds a section heading <w:p> matching P0006/P0427/P0459/P1240/P1257/P1339:
    - Times New Roman, 13pt (sz=26), Bold, Red (FF0000), Shading (F0F2F3)
    - spacing before=44, line=276, lineRule=auto
    - ind firstLine=720 (or left=720 for Today's Top Trending News), jc=both
    """
    p = OxmlElement("w:p")
    pPr = OxmlElement("w:pPr")

    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "44")
    spacing.set(qn("w:line"), "276")
    spacing.set(qn("w:lineRule"), "auto")
    pPr.append(spacing)

    ind = OxmlElement("w:ind")
    if use_left_indent:
        ind.set(qn("w:left"), "720")
    else:
        ind.set(qn("w:firstLine"), "720")
    pPr.append(ind)

    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "both")
    pPr.append(jc)

    pPr.append(_make_rPr(bold=True, color="FF0000", shd_fill="F0F2F3", sz=26))
    p.append(pPr)

    r = OxmlElement("w:r")
    r.append(_make_rPr(bold=True, color="FF0000", shd_fill="F0F2F3", sz=26))
    t = OxmlElement("w:t")
    if title_text.endswith(" ") or title_text.startswith(" "):
        t.set(qn("xml:space"), "preserve")
    t.text = title_text
    r.append(t)
    p.append(r)
    return p


def _make_empty_spacer_p(
    left_indent: Optional[int] = 720,
    justify: bool = True,
    bold: bool = False,
    italic: bool = False,
    red_shaded: bool = False,
) -> OxmlElement:
    """Builds an empty spacing paragraph matching the reference document's exact spacer paragraphs."""
    p = OxmlElement("w:p")
    pPr = OxmlElement("w:pPr")

    if red_shaded:
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:before"), "44")
        spacing.set(qn("w:line"), "276")
        spacing.set(qn("w:lineRule"), "auto")
        pPr.append(spacing)

    if left_indent is not None:
        ind = OxmlElement("w:ind")
        ind.set(qn("w:left"), str(left_indent))
        pPr.append(ind)

    if justify:
        jc = OxmlElement("w:jc")
        jc.set(qn("w:val"), "both")
        pPr.append(jc)

    if red_shaded:
        pPr.append(_make_rPr(bold=True, color="FF0000", shd_fill="F0F2F3", sz=26))
    else:
        pPr.append(_make_rPr(bold=bold, italic=italic, sz=26))

    p.append(pPr)
    return p


def _make_headline_bullet_p(headline_text: str, num_id: int = 1) -> OxmlElement:
    """
    Builds a bulleted article headline <w:p> matching P0008 (numId=2) and P0031+ (numId=1):
    - Style: ListParagraph
    - numPr: ilvl=0, numId=1 (or 2 for the very first story)
    - Font: Times New Roman, 13pt (sz=26), Bold + Italic
    """
    p = OxmlElement("w:p")
    pPr = OxmlElement("w:pPr")

    pStyle = OxmlElement("w:pStyle")
    pStyle.set(qn("w:val"), "ListParagraph")
    pPr.append(pStyle)

    numPr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    numId_el = OxmlElement("w:numId")
    numId_el.set(qn("w:val"), str(num_id))
    numPr.append(ilvl)
    numPr.append(numId_el)
    pPr.append(numPr)

    pPr.append(_make_rPr(bold=True, italic=True, sz=26))
    p.append(pPr)

    r = OxmlElement("w:r")
    r.append(_make_rPr(bold=True, italic=True, sz=26))
    t = OxmlElement("w:t")
    t.text = headline_text.strip()
    r.append(t)
    p.append(r)
    return p


def _make_source_p(source_name: str) -> OxmlElement:
    """
    Builds the (Source Name) attribution paragraph immediately below the headline:
    - Style: Normal, ind left=720
    - Font: Times New Roman, 13pt (sz=26), Regular
    """
    p = OxmlElement("w:p")
    pPr = OxmlElement("w:pPr")
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "720")
    pPr.append(ind)
    pPr.append(_make_rPr(bold=False, italic=False, sz=26))
    p.append(pPr)

    r = OxmlElement("w:r")
    r.append(_make_rPr(bold=False, italic=False, sz=26))
    t = OxmlElement("w:t")
    t.text = f"({source_name})"
    r.append(t)
    p.append(r)
    return p


def _make_body_p(text: str, bold: bool = False) -> OxmlElement:
    """
    Builds a body paragraph <w:p> matching P0011+:
    - Style: Normal, ind left=720, jc=both
    - Font: Times New Roman, 13pt (sz=26), Regular (or Bold for in-article subheadings)
    """
    p = OxmlElement("w:p")
    pPr = OxmlElement("w:pPr")

    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "720")
    pPr.append(ind)

    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "both")
    pPr.append(jc)

    pPr.append(_make_rPr(bold=bold, italic=False, sz=26))
    p.append(pPr)

    r = OxmlElement("w:r")
    r.append(_make_rPr(bold=bold, italic=False, sz=26))
    t = OxmlElement("w:t")
    t.text = text.strip()
    r.append(t)
    p.append(r)
    return p


def _make_hyperlink_p(doc_part, url: str) -> OxmlElement:
    """
    Builds a clickable URL hyperlink paragraph matching P0023:
    - Style: Normal, ind left=720, jc=both
    - Contains <w:hyperlink r:id="rId..." w:history="1"> with rStyle="Hyperlink", Times New Roman, 13pt (sz=26)
    """
    clean_url = (url or "").strip()
    p = OxmlElement("w:p")
    pPr = OxmlElement("w:pPr")

    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "720")
    pPr.append(ind)

    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "both")
    pPr.append(jc)

    pPr.append(_make_rPr(bold=False, italic=False, sz=26))
    p.append(pPr)

    if clean_url:
        r_id = doc_part.relate_to(clean_url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), r_id)
        hyperlink.set(qn("w:history"), "1")

        r = OxmlElement("w:r")
        r.append(_make_rPr(bold=False, italic=False, rStyle="Hyperlink", sz=26))
        t = OxmlElement("w:t")
        t.text = clean_url
        r.append(t)
        hyperlink.append(r)
        p.append(hyperlink)

    return p


def _make_trending_item_p(headline_text: str) -> OxmlElement:
    """
    Builds a numbered item in 'Today’s Top Trending News' matching P1341–P1350:
    - Style: ListParagraph
    - numPr: ilvl=0, numId=3 (decimal numbering 1., 2., 3., ...)
    - Font: Times New Roman, 13pt (sz=26), Regular
    """
    p = OxmlElement("w:p")
    pPr = OxmlElement("w:pPr")

    pStyle = OxmlElement("w:pStyle")
    pStyle.set(qn("w:val"), "ListParagraph")
    pPr.append(pStyle)

    numPr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    numId_el = OxmlElement("w:numId")
    numId_el.set(qn("w:val"), "3")
    numPr.append(ilvl)
    numPr.append(numId_el)
    pPr.append(numPr)

    pPr.append(_make_rPr(bold=False, italic=False, sz=26))
    p.append(pPr)

    r = OxmlElement("w:r")
    r.append(_make_rPr(bold=False, italic=False, sz=26))
    t = OxmlElement("w:t")
    t.text = headline_text.strip()
    r.append(t)
    p.append(r)
    return p


def _clean_article_paragraphs(raw_body: str, fallback_title: str) -> List[str]:
    """Splits and cleans article body text into well-formed editorial paragraphs."""
    txt = html.unescape(raw_body or "").strip()
    if not txt:
        return [fallback_title] if fallback_title else []

    # Normalize line breaks
    raw_paras = re.split(r"\n\s*\n|\r\n\s*\r\n|\n", txt)
    cleaned = []
    seen = set()
    for p in raw_paras:
        p_clean = re.sub(r"\s+", " ", p).strip()
        if not p_clean or len(p_clean) < 15:
            continue
        low = p_clean.lower()
        if any(
            junk in low
            for junk in [
                "cookie policy", "privacy policy", "all rights reserved",
                "subscribe to our", "follow us on", "download our app",
                "click here to", "also read:", "related news:",
            ]
        ):
            continue
        if p_clean in seen:
            continue
        seen.add(p_clean)
        cleaned.append(p_clean)

    if not cleaned:
        cleaned = [re.sub(r"\s+", " ", txt).strip()]
    # Cap overly long scrapes to 12 crisp editorial paragraphs
    return cleaned[:12]


def _prepare_article_for_digest(art: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures an article has clean English headline, English body paragraphs, and formatted source name."""
    raw_title = html.unescape(art.get("headline_english") or art.get("title") or art.get("text") or "").strip()
    if not raw_title or _has_devanagari(raw_title):
        raw_title = _translate_ne_to_en(art.get("title") or art.get("text") or "")
    raw_title = re.sub(r"^[A-Za-z]+\s*:{2,}\s*", "", raw_title).strip()

    raw_body = html.unescape(art.get("full_content") or art.get("summary") or art.get("text") or "").strip()
    if _has_devanagari(raw_body):
        raw_body = _translate_ne_to_en(raw_body)

    link = (art.get("link") or "").strip()
    source_label = format_editorial_source(art.get("source") or art.get("author_name") or "", link)
    paras = _clean_article_paragraphs(raw_body, raw_title)

    return {
        "headline": raw_title,
        "source": source_label,
        "paragraphs": paras,
        "link": link,
        "related_links": [u for u in (art.get("related_links") or []) if u and u != link][:4],
        "section": art.get("_target_section") or classify_article_to_reference_section(art),
    }


def generate_executive_word_digest(
    articles: List[Dict[str, Any]],
    output_path: Optional[str] = None,
    report_date: Optional[datetime.datetime] = None,
    enrich_missing_sections: bool = False,
) -> bytes:
    """
    Generates an Executive Word Document (.docx) using the master reference template
    `NEPAL DAILY NEWS DIGEST – 5th November 2026.docx`.

    Preserves:
    - Cover title block (Section 0) with '   NEPAL DAILY NEWS DIGEST' (28pt Bold Times New Roman)
      and anchored red horizontal line (#D3081B)
    - Reporting Date subtitle (22pt Bold Times New Roman, centered)
    - Continuous section break into Section 1 and second red horizontal line (#D3081B)
    - Headers with 'NEPAL DAILY NEWS DIGEST' (#595959) and embedded border/background VML object
    - Footers with navy blue (#001E5E) dynamic PAGE number badge
    - Exact section sequence:
        1. INDIA IN NEPAL
        2. BANGLADESH IN NEPAL
        3. NEPAL-INTERNAL POLITICS 
        4. NEPAL-EXTERNAL
        5. ECONOMY
        6. Today’s Top Trending News
    """
    template_path = None
    for p in TEMPLATE_PATHS:
        if os.path.exists(p):
            template_path = p
            break
    if not template_path:
        raise FileNotFoundError(
            f"Master reference template not found. Checked: {TEMPLATE_PATHS}"
        )

    doc = docx.Document(template_path)

    # 1. Determine reporting date and update P002 in Section 0
    if report_date is None:
        # Use latest published_dt from articles if available, else current Nepal time
        dts = [
            a.get("published_dt")
            for a in articles
            if isinstance(a.get("published_dt"), datetime.datetime)
        ]
        report_date = max(dts) if dts else datetime.datetime.now(NEPAL_TZ)

    month_str = report_date.strftime("%B ")
    day_str = report_date.strftime("%d")
    year_str = report_date.strftime(", %Y")

    # P002 in the reference template holds the date in 3 runs: ['November ', '05', ', 2026']
    if len(doc.paragraphs) > 2:
        p_date = doc.paragraphs[2]
        if len(p_date.runs) >= 3:
            p_date.runs[0].text = month_str
            p_date.runs[1].text = day_str
            p_date.runs[2].text = year_str
            for extra_r in p_date.runs[3:]:
                extra_r.text = ""
        elif p_date.runs:
            p_date.runs[0].text = f"{month_str}{day_str}{year_str}"
            for extra_r in p_date.runs[1:]:
                extra_r.text = ""

    # 2. Remove old body paragraphs P006..end while preserving P000..P005 and final <w:sectPr>
    body_el = doc._body._body
    all_p = body_el.findall(qn("w:p"))
    for p_el in all_p[6:]:
        body_el.remove(p_el)

    # Remove any tables if present in body
    for tbl_el in body_el.findall(qn("w:tbl")):
        body_el.remove(tbl_el)

    # Prune old external hyperlink relationships from document.xml.rels so no stale links remain
    rels = doc.part.rels
    stale_rids = [
        rid
        for rid, rel in list(rels.items())
        if rel.is_external and rel.reltype == RELATIONSHIP_TYPE.HYPERLINK
    ]
    for rid in stale_rids:
        del rels[rid]

    # 3. Classify & cluster articles into the 5 exact reference sections
    grouped_raw: Dict[str, List[Dict[str, Any]]] = {sec: [] for sec in REFERENCE_NEWS_SECTIONS}
    for art in articles:
        sec = classify_article_to_reference_section(art)
        art_copy = dict(art)
        art_copy["_target_section"] = sec
        grouped_raw[sec].append(art_copy)

    # Optional enrichment from stored database if a reference section has 0 stories
    if enrich_missing_sections and any(len(grouped_raw[s]) == 0 for s in REFERENCE_NEWS_SECTIONS):
        try:
            from nepal_news_store import get_stored_articles, get_stored_indian_articles
            pool = get_stored_articles(limit=300) + get_stored_indian_articles(limit=100)
            # Prioritize English articles for backfill
            pool.sort(key=lambda x: (0 if _has_devanagari(x.get("title", "")) else 1), reverse=True)
            existing_links = {a.get("link") for a in articles if a.get("link")}
            for cand in pool:
                if cand.get("link") in existing_links:
                    continue
                sec = classify_article_to_reference_section(cand)
                if len(grouped_raw[sec]) == 0:
                    c_copy = dict(cand)
                    c_copy["_target_section"] = sec
                    grouped_raw[sec].append(c_copy)
                    existing_links.add(cand.get("link"))
        except Exception:
            pass

    grouped_clusters: Dict[str, List[Dict[str, Any]]] = {}
    for sec in REFERENCE_NEWS_SECTIONS:
        grouped_clusters[sec] = deduplicate_and_cluster_articles(grouped_raw[sec])

    # Fetch missing full content for lead stories if needed
    lead_stories_to_enrich = []
    for sec in REFERENCE_NEWS_SECTIONS:
        for st_item in grouped_clusters[sec]:
            body_cand = (st_item.get("full_content") or st_item.get("summary") or "").strip()
            if len(body_cand) < 120 and (st_item.get("link") or "").startswith("http"):
                lead_stories_to_enrich.append(st_item)

    if lead_stories_to_enrich:
        try:
            from nepal_fetcher import batch_fetch_full_content
            batch_fetch_full_content(lead_stories_to_enrich[:50], max_workers=15)
        except Exception:
            pass

    # Prepare & translate (where needed) in parallel
    prepared_by_section: Dict[str, List[Dict[str, Any]]] = {sec: [] for sec in REFERENCE_NEWS_SECTIONS}
    flat_tasks: List[Tuple[str, Dict[str, Any]]] = []
    for sec in REFERENCE_NEWS_SECTIONS:
        for st_item in grouped_clusters[sec]:
            flat_tasks.append((sec, st_item))

    if flat_tasks:
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            futures = [executor.submit(_prepare_article_for_digest, item) for _, item in flat_tasks]
            for (sec, _), fut in zip(flat_tasks, futures):
                try:
                    prep = fut.result()
                    if prep.get("headline"):
                        prepared_by_section[sec].append(prep)
                except Exception:
                    pass

    # 4. Append all generated paragraphs right before the final <w:sectPr>
    sectPr = body_el.find(qn("w:sectPr"))

    def _append_p(p_el: OxmlElement):
        if sectPr is not None:
            sectPr.addprevious(p_el)
        else:
            body_el.append(p_el)

    first_bullet_in_doc = True
    trending_candidates: List[str] = []

    for sec_idx, sec_title in enumerate(REFERENCE_NEWS_SECTIONS):
        sec_stories = prepared_by_section.get(sec_title, [])
        # Whenever there is no news in that section, simply remove/skip that section and move to the next section
        if not sec_stories:
            continue

        # Section Heading (Red FF0000 bold on F0F2F3 grey fill, firstLine=720)
        _append_p(_make_section_heading_p(sec_title, use_left_indent=False))
        # Empty spacer paragraph below section heading
        _append_p(_make_empty_spacer_p(left_indent=720, justify=True, bold=True, italic=True))

        for story in sec_stories:
            headline = story["headline"]
            source = story["source"]
            paragraphs = story["paragraphs"]
            link = story["link"]
            related_links = story["related_links"]

            if headline and headline not in trending_candidates:
                trending_candidates.append(headline)

            # 1) Bulleted Headline (numId=2 for very first story in doc, numId=1 for all subsequent)
            num_id = 2 if first_bullet_in_doc else 1
            first_bullet_in_doc = False
            _append_p(_make_headline_bullet_p(headline, num_id=num_id))

            # 2) (Source Name) immediately on next paragraph
            _append_p(_make_source_p(source))

            # 3) Empty spacer paragraph before body
            _append_p(_make_empty_spacer_p(left_indent=720, justify=False))

            # 4) Body paragraphs (13pt Regular, left=720, justified) separated by empty spacer paragraphs
            for para_text in paragraphs:
                is_subhead = (
                    len(para_text) < 85
                    and not para_text.endswith(".")
                    and not para_text.endswith('"')
                    and not para_text.endswith("'")
                )
                _append_p(_make_body_p(para_text, bold=is_subhead))
                _append_p(_make_empty_spacer_p(left_indent=720, justify=True))

            # 5) Clickable Article URL Hyperlink
            if link:
                _append_p(_make_hyperlink_p(doc.part, link))
                _append_p(_make_empty_spacer_p(left_indent=720, justify=True))

            # 6) Optional 'More related news:' block matching P0025-P0029
            if related_links:
                _append_p(_make_body_p("More related news:", bold=False))
                for rel_url in related_links:
                    _append_p(_make_hyperlink_p(doc.part, rel_url))
                _append_p(_make_empty_spacer_p(left_indent=720, justify=True))

    # 5. Final Section: 'Today’s Top Trending News' (matching P1339-P1350)
    if trending_candidates:
        _append_p(_make_section_heading_p(TRENDING_SECTION_TITLE, use_left_indent=True))
        _append_p(_make_empty_spacer_p(left_indent=720, justify=True, red_shaded=True))

        # Select representative top trending stories across active digest sections
        top_trending: List[str] = []
        section_quotas = [
            ("INDIA IN NEPAL", 2),
            ("CHINA IN NEPAL", 1),
            ("PAKISTAN IN NEPAL", 1),
            ("BANGLADESH IN NEPAL", 1),
            ("NEPAL-INTERNAL POLITICS", 5),
            ("NEPAL-EXTERNAL", 1),
            ("ECONOMY", 1),
        ]
        for sec_name, quota in section_quotas:
            for st_item in prepared_by_section.get(sec_name, [])[:quota]:
                hl = st_item.get("headline", "")
                if hl and hl not in top_trending:
                    top_trending.append(hl)
        for hl in trending_candidates:
            if len(top_trending) >= 10:
                break
            if hl not in top_trending:
                top_trending.append(hl)

        for tr_headline in top_trending[:10]:
            _append_p(_make_trending_item_p(tr_headline))

        # Trailing spacer paragraphs matching P1351-P1356
        _append_p(_make_empty_spacer_p(left_indent=720, justify=True, red_shaded=True))
        _append_p(_make_empty_spacer_p(left_indent=None, justify=False))

    bio = io.BytesIO()
    doc.save(bio)
    doc_bytes = bio.getvalue()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(doc_bytes)

    return doc_bytes
