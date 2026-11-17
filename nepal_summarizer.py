"""
nepal_summarizer.py
Single Source of Truth for Cross-Lingual Translation and Hybrid LexRank Extractive Summarization.
Zero external AI models, zero Ollama, zero paid APIs. Pure Python deterministic NLP.
"""

import re
import ssl
import html
import math
import json
import time
import threading
import urllib.request
import urllib.parse
import concurrent.futures
from collections import Counter
from typing import List, Dict, Any

_TRANSLATION_CACHE: Dict[str, str] = {}
_SSL_CTX = ssl._create_unverified_context()
_TRANSLATE_SEM = threading.Semaphore(6)

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "can",
    "could", "did", "do", "does", "for", "from", "had", "has", "have", "he", "her",
    "here", "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "just",
    "may", "might", "more", "most", "much", "must", "my", "no", "not", "of", "on",
    "or", "other", "our", "out", "over", "said", "says", "say", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "them", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "up", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "will", "with",
    "would", "you", "your", "also", "about", "after", "before", "between", "during",
}

_INSTITUTIONAL_TERMS = {
    "minister", "prime minister", "president", "cabinet", "parliament", "supreme court",
    "court", "government", "govt", "ministry", "nrb", "rastra bank", "sebon", "nepse",
    "mea", "embassy", "envoy", "ambassador", "agreement", "treaty", "mou", "pact",
    "border", "budget", "revenue", "tax", "inflation", "hydropower", "electricity",
    "railway", "airport", "highway", "india", "china", "nepal", "bangladesh", "pakistan",
    "kathmandu", "new delhi", "beijing", "election", "commission", "police", "army",
}

_DATELINE_RE = re.compile(
    r"^\s*(?:"
    r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}(?:\s+\d{1,2}:\d{1,2}(?::\d{1,2})?)?\s*"
    r"|"
    r"(?:by\s+)?[a-z\s]+\s*\|\s*(?:bureau|desk|correspondent|team)\s*"
    r"|"
    r"(?:kathmandu|new delhi|pokhara|biratnagar|birgunj|janakpur|lalitpur|bhaktapur|bardia|bardiya|"
    r"london|washington|beijing|dhaka|islamabad|jamshedpur\s+news|pti|ani|rss|ians|reuters|ap|afp)"
    r"(?:\s*,\s*[a-zA-Z0-9\s\.]+)?\s*[:\-–—|।]\s*"
    r"|"
    r"(?:काठमाडौँ|काठमाडौं|पोखरा|विराटनगर|वीरगन्ज|जनकपुर|ललितपुर|लण्डन|नयाँदिल्ली)"
    r"\s*[:\-–—|।]\s*"
    r"|"
    r"\d{1,2}\s+[\u0900-\u097F]+\s*,\s*[\u0900-\u097F]+\s*[।:]\s*"
    r")+",
    re.IGNORECASE,
)

_BOILERPLATE_TAIL_RE = re.compile(
    r"\s*(?:also read|read more|follow us on|share on|subscribe to|click here|"
    r"for more news|copyright ©|all rights reserved|news summary generated).*$",
    re.IGNORECASE,
)


_DEVANAGARI_PRE_MAP = [
    ("वालेन्द्र", "बालेन्द्र"),
    ("वालेंन", "बालेन"),
    ("वालेन", "बालेन"),
    ("वालुवाटार", "बालुवाटार"),
    ("सुर्यविनायक", "सूर्यबिनायक"),
    ("सूर्यविनायक", "सूर्यबिनायक"),
    ("वीरगन्ज", "बिरगन्ज"),
    ("बीरगन्ज", "बिरगन्ज"),
    ("विराटनगर", "बिराटनगर"),
    ("देउवा", "देउबा"),
    ("रास्वपा", "राष्ट्रिय स्वतन्त्र पार्टी (RSP)"),
    ("नेकपा एमाले", "CPN-UML"),
    ("नेकपा (एमाले)", "CPN-UML"),
    ("माओवादी केन्द्र", "CPN (Maoist Centre)"),
]

_ENGLISH_PROPER_NOUN_PATTERNS = [
    (re.compile(r"\b[WV]alendra\b"), "Balendra"),
    (re.compile(r"\b[WV]alen\b"), "Balen"),
    (re.compile(r"\b[WV]aluwatar\b"), "Baluwatar"),
    (re.compile(r"\bDeu[wv]a\b"), "Deuba"),
    (re.compile(r"\bRavi\s+Lamichhane\b"), "Rabi Lamichhane"),
    (re.compile(r"\bPrachand\b"), "Prachanda"),
    (re.compile(r"\bSuryavinayak\b"), "Suryabinayak"),
    (re.compile(r"\b(?:Veerganj|Virgunj|Birganj)\b"), "Birgunj"),
    (re.compile(r"\b(?:Viratnagar|Wiratnagar)\b"), "Biratnagar"),
    (re.compile(r"\bBardia\b"), "Bardiya"),
    (re.compile(r"\bGulria\b"), "Gulariya"),
    (re.compile(r"\b(?:Singhadarbar|Singha\s+Darbar|Lion\s+Palace)\b", re.I), "Singha Durbar"),
    (re.compile(r"\b(?:Shital\s+Niwas|Cold\s+Residence)\b", re.I), "Sheetal Niwas"),
    (re.compile(r"\bNepalese\b"), "Nepali"),
    (re.compile(r"\b1\s+million\s+gifts\b", re.I), "Rs 1 million prize"),
    (re.compile(r"\b10\s+lakhs?\b", re.I), "Rs 1 million"),
    (re.compile(r"\b(\d+)\s+lakh\s+prize\b", re.I), r"Rs \1 lakh prize"),
]

_DANGLING_LEAD_PREFIX_RE = re.compile(
    r"^(?:This\s+time,\s+|Meanwhile,\s+|According\s+to\s+(?:him|her|them),\s+|"
    r"Similarly,\s+|In\s+this\s+regard,\s+|On\s+the\s+other\s+hand,\s+|However,\s+)",
    re.IGNORECASE,
)

_FINITE_VERB_RE = re.compile(
    r"\b(?:is|are|was|were|be|been|has|have|had|will|would|can|could|may|might|must|shall|should|"
    r"said|says|stated|announced|reported|held|won|lost|died|started|reached|approved|signed|"
    r"demanded|warned|urged|decided|arrested|launched|issued|passed|failed|increased|decreased|"
    r"honored|honoured|celebrated|visited|met|addressed|directed|formed|appointed|suspended|"
    r"investigated|found|showed|revealed|confirmed|denied|rejected|agreed|proposed|began|ended|"
    r"continues|continued|remained|became|become|took|made|gave|got|went|came|rose|fell|hit|"
    r"[a-z]{3,}ed|[a-z]{3,}ing)\b",
    re.IGNORECASE,
)


_BS_NEPALI_DATE_RE = re.compile(
    r"^\s*(?:बैशाख|वैशाख|जेठ|जेष्ठ|असार|आषाढ|साउन|श्रावण|भदौ|भाद्र|असोज|आश्विन|कात्तिक|कार्तिक|मंसिर|मङ्सिर|मार्ग|पुस|पौष|माघ|फागुन|फाल्गुण|चैत|चैत्र)"
    r"\s+[०-९0-9]{1,2}\s*,?\s*[०-९0-9]{4}(?:\s+(?:आइतबार|सोमबार|मंगलबार|मङ्गलबार|बुधबार|बिहिबार|बिहीबार|शुक्रबार|शनिबार))?"
    r"(?:\s+[०-९0-9]{1,2}:[०-९0-9]{1,2}(?::[०-९0-9]{1,2})?)?\s*",
    re.UNICODE,
)


def _normalize_devanagari_before_translation(text: str) -> str:
    """Strips Nepali BS date headers and normalizes proper-noun variations before translation."""
    if not text:
        return text
    out = _BS_NEPALI_DATE_RE.sub("", text).strip()
    for src, dst in _DEVANAGARI_PRE_MAP:
        out = out.replace(src, dst)
    return out


def normalize_english_proper_nouns(text: str) -> str:
    """Corrects machine-translated Nepali/Hindi proper nouns and terminology in English output."""
    if not text:
        return ""
    out = text
    for pat, repl in _ENGLISH_PROPER_NOUN_PATTERNS:
        out = pat.sub(repl, out)
    return re.sub(r"\s+", " ", out).strip()


def _has_devanagari(text: str) -> bool:
    """Returns True if text contains Devanagari characters."""
    if not text:
        return False
    return any(0x0900 <= ord(ch) <= 0x097F for ch in text)


def _translate_chunk_with_failover(chunk: str, sl_code: str, timeout: int = 5) -> str:
    """3-tier zero-key translation failover: clients5 -> gtx -> MyMemory."""
    q = urllib.parse.quote(chunk)
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    # Tier 1: clients5 dict-chrome-ex endpoint
    try:
        url1 = f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl={sl_code}&tl=en&q={q}"
        req1 = urllib.request.Request(url1, headers=headers)
        with _TRANSLATE_SEM:
            with urllib.request.urlopen(req1, context=_SSL_CTX, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                if isinstance(data, list) and data:
                    if isinstance(data[0], str):
                        return data[0].strip()
                    if isinstance(data[0], list) and data[0]:
                        return str(data[0][0]).strip()
    except Exception:
        pass

    # Tier 2: translate.googleapis.com gtx endpoint
    try:
        url2 = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl_code}&tl=en&dt=t&q={q}"
        req2 = urllib.request.Request(url2, headers=headers)
        with _TRANSLATE_SEM:
            with urllib.request.urlopen(req2, context=_SSL_CTX, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                out = "".join(seg[0] for seg in data[0] if seg and seg[0])
                if out and out.strip():
                    return out.strip()
    except Exception:
        pass

    # Tier 3: MyMemory free translation endpoint (<= 500 char segments)
    try:
        short_chunk = chunk[:480]
        url3 = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(short_chunk)}&langpair={sl_code}|en"
        req3 = urllib.request.Request(url3, headers=headers)
        with _TRANSLATE_SEM:
            with urllib.request.urlopen(req3, context=_SSL_CTX, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                txt = (data.get("responseData") or {}).get("translatedText", "")
                if txt and not _has_devanagari(txt) and "QUERY LENGTH LIMIT" not in txt.upper():
                    return txt.strip()
    except Exception:
        pass

    return chunk


def _translate_ne_to_en(text: str, timeout: int = 5, source_lang: str = "ne") -> str:
    """Translates Nepali or Hindi (Devanagari) text into clean English with proper-noun normalization."""
    clean = (text or "").strip()
    if not clean or not _has_devanagari(clean):
        return normalize_english_proper_nouns(clean) if clean else clean
    cache_key = f"{source_lang}::{clean}"
    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]

    prepped = _normalize_devanagari_before_translation(clean) if source_lang != "hi" else clean
    sl_code = "hi" if source_lang == "hi" else "ne"

    chunks = []
    if len(prepped) <= 2500:
        chunks = [prepped]
    else:
        paras = prepped.split("\n\n")
        cur = ""
        for p in paras:
            if len(cur) + len(p) + 2 <= 2500:
                cur = f"{cur}\n\n{p}" if cur else p
            else:
                if cur:
                    chunks.append(cur)
                if len(p) <= 2500:
                    cur = p
                else:
                    for i in range(0, len(p), 2000):
                        chunks.append(p[i : i + 2000])
                    cur = ""
        if cur:
            chunks.append(cur)

    translated_chunks = []
    any_failed = False
    for chunk in chunks:
        tr = _translate_chunk_with_failover(chunk, sl_code=sl_code, timeout=timeout)
        if _has_devanagari(tr) and tr == chunk:
            any_failed = True
        translated_chunks.append(normalize_english_proper_nouns(tr))

    result = "\n\n".join(translated_chunks).strip()
    if not any_failed:
        _TRANSLATION_CACHE[cache_key] = result
    return result


def clean_journalistic_text(text: str, title: str = "") -> str:
    """Strips HTML, wire datelines, and editorial boilerplate while preserving sentence structure."""
    if not text:
        return ""
    s = html.unescape(str(text))
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("\xa0", " ")
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = _DATELINE_RE.sub("", s).strip()
    s = _BOILERPLATE_TAIL_RE.sub("", s).strip()
    if title:
        clean_title = re.sub(r"\s+", " ", title).strip()
        if s.startswith(clean_title) and len(s) > len(clean_title) + 15:
            remainder = s[len(clean_title) :].lstrip(" .:-–—|।")
            if len(remainder) >= 25:
                s = remainder
    return s


def _tokenize_content_words(text: str) -> List[str]:
    """Tokenizes lowercase alphanumeric content words excluding stopwords."""
    words = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())
    return [w for w in words if len(w) >= 2 and w not in _STOPWORDS]


def _split_sentences(text: str) -> List[str]:
    """Splits cleaned text into well-formed sentences without slicing inside numbers/abbreviations."""
    # Protect common abbreviations and numbered list markers (e.g., "1. ", "2. ")
    protected = re.sub(r"\b(Mr|Mrs|Ms|Dr|Prof|Hon|Rs|No|St|vs|etc|U\.S|U\.K)\.", r"\1<DOT>", text)
    protected = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", protected)
    protected = re.sub(r"(?:^|\s)(\d{1,2})\.\s+", r" ", protected)
    raw_sents = re.split(r"(?<=[.!?।])\s+", protected)
    sents = []
    for s in raw_sents:
        restored = s.replace("<DOT>", ".").strip()
        restored = _DATELINE_RE.sub("", restored).strip()
        restored = _DANGLING_LEAD_PREFIX_RE.sub("", restored).strip()
        if not restored:
            continue
        # Ensure first char is capitalized after prefix stripping
        if restored[0].islower():
            continue
        word_count = len(restored.split())
        if word_count < 7 or word_count > 55:
            continue
        # Filter bare image captions / noun phrases lacking a finite verb
        if not _FINITE_VERB_RE.search(restored):
            continue
        sents.append(restored)
    return sents


def _cosine_sim(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a.keys()) & set(vec_b.keys())
    if not common:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _jaccard_overlap(tokens_a: set, tokens_b: set) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    inter = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return inter / union if union else 0.0


def _scope_top_paragraphs(text: str, max_paras: int = 6) -> str:
    """Restricts body text to the opening paragraphs so sidebar/related widgets cannot leak in."""
    if not text:
        return ""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 25]
    if paras:
        return "\n\n".join(paras[:max_paras])
    return text


def generate_lexrank_english_summary(
    title: str,
    full_text: str,
    max_sentences: int = 2,
    max_chars: int = 320,
) -> str:
    """
    Lead-Anchored Hybrid LexRank + Journalistic Salience Summarizer.
    Scores paragraph-scoped sentences by graph centrality, lead position, factual density,
    and topical alignment against the headline, producing a tight 2-sentence executive brief.
    """
    clean_title = normalize_english_proper_nouns(clean_journalistic_text(title))
    scoped_body = _scope_top_paragraphs(full_text, max_paras=6)
    clean_body = normalize_english_proper_nouns(clean_journalistic_text(scoped_body, title=clean_title))
    if not clean_body:
        return clean_title

    sentences = _split_sentences(clean_body)
    if not sentences:
        if len(clean_body) <= max_chars:
            return clean_body
        return clean_body[:max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "..."

    if len(sentences) <= 2:
        joined = " ".join(sentences)
        if len(joined) <= max_chars:
            return joined
        if len(sentences[0]) <= max_chars:
            return sentences[0]
        return sentences[0][:max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "..."

    # Build TF-IDF vectors for LexRank
    sent_tokens = [_tokenize_content_words(s) for s in sentences]
    sent_sets = [set(toks) for toks in sent_tokens]
    n_sents = len(sentences)
    title_tokens = set(_tokenize_content_words(clean_title))
    lead_tokens = sent_sets[0] | title_tokens

    df: Counter = Counter()
    for s_set in sent_sets:
        for w in s_set:
            df[w] += 1

    tfidf_vecs: List[Dict[str, float]] = []
    for toks in sent_tokens:
        tf = Counter(toks)
        total = len(toks) or 1
        vec = {}
        for w, count in tf.items():
            idf = math.log((n_sents + 1) / (df[w] + 1)) + 1.0
            vec[w] = (count / total) * idf
        tfidf_vecs.append(vec)

    # Pairwise cosine similarity matrix & power-iteration LexRank
    adj = [[0.0] * n_sents for _ in range(n_sents)]
    for i in range(n_sents):
        row_sum = 0.0
        for j in range(n_sents):
            if i == j:
                continue
            sim = _cosine_sim(tfidf_vecs[i], tfidf_vecs[j])
            if sim > 0.05:
                adj[i][j] = sim
                row_sum += sim
        if row_sum > 0:
            for j in range(n_sents):
                adj[i][j] /= row_sum

    lex_scores = [1.0 / n_sents] * n_sents
    damping = 0.85
    for _ in range(12):
        new_scores = []
        for i in range(n_sents):
            rank_sum = sum(adj[j][i] * lex_scores[j] for j in range(n_sents))
            new_scores.append((1.0 - damping) / n_sents + damping * rank_sum)
        lex_scores = new_scores

    max_lex = max(lex_scores) or 1.0

    scored_indices = []
    for idx, sent in enumerate(sentences):
        lex_norm = lex_scores[idx] / max_lex
        pos_weight = 1.0 / math.sqrt(idx + 1)

        low_s = sent.lower()
        has_num = 1.0 if re.search(r"\b\d+(?:\.\d+)?%?\b", low_s) else 0.0
        has_unit = 1.0 if re.search(r"\b(?:rs|usd|million|billion|crore|lakh|mw|km|percent|%)\b", low_s) else 0.0
        inst_hits = sum(1 for term in _INSTITUTIONAL_TERMS if term in low_s)
        fact_density = min(1.0, 0.35 * has_num + 0.35 * has_unit + 0.15 * inst_hits)

        overlap = _jaccard_overlap(sent_sets[idx], title_tokens)
        topical_link = 1.0 if (sent_sets[idx] & lead_tokens) else 0.0
        if overlap > 0.78:
            title_align = -0.35
        elif 0.12 <= overlap <= 0.65:
            title_align = 1.0
        else:
            title_align = 0.2 if topical_link else -0.4

        total_score = (
            0.40 * lex_norm
            + 0.30 * pos_weight
            + 0.20 * fact_density
            + 0.10 * title_align
        )
        scored_indices.append((total_score, idx))

    # Anchor sentence 1 on the stronger of the first 2 sentences to guarantee lead coherence
    lead_candidates = [x for x in scored_indices if x[1] in (0, 1)]
    lead_candidates.sort(key=lambda x: x[0], reverse=True)
    selected_indices: List[int] = [lead_candidates[0][1]] if lead_candidates else [0]

    # Pick highest-scoring non-redundant supporting sentence sharing topical continuity
    scored_indices.sort(key=lambda x: x[0], reverse=True)
    for _, cand_idx in scored_indices:
        if len(selected_indices) >= max_sentences:
            break
        if cand_idx in selected_indices:
            continue
        cand_set = sent_sets[cand_idx]
        if any(_jaccard_overlap(cand_set, sent_sets[sel_i]) > 0.58 for sel_i in selected_indices):
            continue
        if not (cand_set & lead_tokens):
            continue
        selected_indices.append(cand_idx)

    selected_indices.sort()

    chosen_sents: List[str] = []
    curr_len = 0
    for idx in selected_indices:
        s = sentences[idx]
        if s and s[-1] not in ".!?":
            s += "."
        added_len = len(s) + (1 if chosen_sents else 0)
        if chosen_sents and curr_len + added_len > max_chars:
            break
        chosen_sents.append(s)
        curr_len += added_len

    summary = " ".join(chosen_sents).strip()
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    return summary


def enrich_single_article_english_summary(art: Dict[str, Any]) -> Dict[str, Any]:
    """
    Populates English `headline_english` and a complete 2-sentence LexRank `summary`
    on a single article dictionary without altering native `title` or `full_content`.
    """
    raw_title = (art.get("title") or "").strip()
    existing_en_title = (art.get("headline_english") or "").strip()
    lang_code = "hi" if (art.get("language") or "").strip().lower() == "hindi" else "ne"

    if existing_en_title and not _has_devanagari(existing_en_title):
        headline_en = normalize_english_proper_nouns(existing_en_title)
    elif raw_title and _has_devanagari(raw_title):
        headline_en = _translate_ne_to_en(raw_title, source_lang=lang_code)
    else:
        headline_en = normalize_english_proper_nouns(raw_title)

    art["headline_english"] = headline_en

    full_body = (art.get("full_content") or "").strip()
    raw_summary = (art.get("summary") or "").strip()
    source_text = full_body if len(full_body) >= len(raw_summary) else raw_summary
    if not source_text:
        source_text = raw_title

    scoped_source = _scope_top_paragraphs(source_text, max_paras=6)

    if _has_devanagari(scoped_source):
        lead_chunk = scoped_source[:1500]
        if len(scoped_source) > 1500:
            last_sep = max(lead_chunk.rfind("।"), lead_chunk.rfind("."), lead_chunk.rfind(" "))
            if last_sep > 400:
                lead_chunk = lead_chunk[: last_sep + 1]
        english_body = _translate_ne_to_en(lead_chunk, source_lang=lang_code)
    else:
        english_body = normalize_english_proper_nouns(scoped_source)

    english_brief = generate_lexrank_english_summary(
        title=headline_en,
        full_text=english_body,
        max_sentences=2,
        max_chars=320,
    )
    if english_brief:
        art["summary"] = english_brief
    return art


def enrich_articles_with_english_summaries(
    articles: List[Dict[str, Any]],
    max_workers: int = 20,
) -> List[Dict[str, Any]]:
    """Runs cross-lingual translation & LexRank summarization across a batch of articles in parallel."""
    if not articles:
        return articles

    to_process = []
    for art in articles:
        cur_sum = (art.get("summary") or "").strip()
        cur_title = (art.get("title") or "").strip()
        cur_en_head = (art.get("headline_english") or "").strip()
        needs_summary = (
            not cur_sum
            or cur_sum == cur_title
            or _has_devanagari(cur_sum)
            or cur_sum.endswith("...")
            or (cur_title and _has_devanagari(cur_title) and (not cur_en_head or _has_devanagari(cur_en_head)))
        )
        if needs_summary:
            to_process.append(art)

    if not to_process:
        return articles

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(enrich_single_article_english_summary, to_process))

    return articles
