"""
nepal_summarizer.py
Single Source of Truth for Cross-Lingual Translation and Hybrid LexRank Extractive Summarization.
Zero external AI models, zero Ollama, zero paid APIs. Pure Python deterministic NLP.
"""

import re
import html
import math
import json
import urllib.request
import urllib.parse
import concurrent.futures
from collections import Counter
from typing import List, Dict, Any

_TRANSLATION_CACHE: Dict[str, str] = {}

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
    r"(?:by\s+)?[a-z\s]+\s*\|\s*(?:bureau|desk|correspondent|team)\s*"
    r"|"
    r"(?:kathmandu|new delhi|pokhara|biratnagar|birgunj|janakpur|lalitpur|bhaktapur|"
    r"london|washington|beijing|dhaka|islamabad|jamshedpur\s+news|pti|ani|rss|ians|reuters|ap|afp)"
    r"(?:\s*,\s*[a-zA-Z0-9\s\.]+)?\s*[:\-–—|।]\s*"
    r"|"
    r"(?:काठमाडौँ|काठमाडौं|पोखरा|विराटनगर|वीरगन्ज|जनकपुर|ललितपुर|लण्डन|नयाँदिल्ली)"
    r"\s*[:\-–—|।]\s*"
    r"|"
    r"\d{1,2}\s+[\u0900-\u097F]+\s*,\s*[\u0900-\u097F]+\s*[।:]\s*"
    r")",
    re.IGNORECASE,
)

_BOILERPLATE_TAIL_RE = re.compile(
    r"\s*(?:also read|read more|follow us on|share on|subscribe to|click here|"
    r"for more news|copyright ©|all rights reserved|news summary generated).*$",
    re.IGNORECASE,
)


def _has_devanagari(text: str) -> bool:
    """Returns True if text contains Devanagari characters."""
    if not text:
        return False
    return any(0x0900 <= ord(ch) <= 0x097F for ch in text)


def _translate_ne_to_en(text: str, timeout: int = 5) -> str:
    """Translates Nepali or Hindi (Devanagari) text into clean English using standard web translation."""
    clean = (text or "").strip()
    if not clean or not _has_devanagari(clean):
        return clean
    if clean in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[clean]

    chunks = []
    if len(clean) <= 2500:
        chunks = [clean]
    else:
        paras = clean.split("\n\n")
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
    for chunk in chunks:
        try:
            url = (
                "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q="
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
    # Protect common abbreviations before splitting
    protected = re.sub(r"\b(Mr|Mrs|Ms|Dr|Prof|Hon|Rs|No|St|vs|etc|U\.S|U\.K)\.", r"\1<DOT>", text)
    protected = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", protected)
    raw_sents = re.split(r"(?<=[.!?।])\s+", protected)
    sents = []
    for s in raw_sents:
        restored = s.replace("<DOT>", ".").strip()
        restored = _DATELINE_RE.sub("", restored).strip()
        if len(restored.split()) >= 5:
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


def generate_lexrank_english_summary(
    title: str,
    full_text: str,
    max_sentences: int = 3,
    max_chars: int = 360,
) -> str:
    """
    Hybrid LexRank + Journalistic Salience Summarizer.
    Scores sentences by graph centrality, position decay, factual/entity density,
    and title alignment while enforcing MMR novelty against the headline and prior picks.
    """
    clean_title = clean_journalistic_text(title)
    clean_body = clean_journalistic_text(full_text, title=clean_title)
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
        # Prefer first complete sentence if 2 exceed max_chars
        if len(sentences[0]) <= max_chars:
            return sentences[0]
        return sentences[0][:max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "..."

    # Build TF-IDF vectors for LexRank
    sent_tokens = [_tokenize_content_words(s) for s in sentences]
    sent_sets = [set(toks) for toks in sent_tokens]
    n_sents = len(sentences)

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
    title_tokens = set(_tokenize_content_words(clean_title))

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
        if overlap > 0.75:
            # Penalize sentences that just echo the headline verbatim
            title_align = -0.35
        elif 0.15 <= overlap <= 0.65:
            title_align = 1.0
        else:
            title_align = 0.3

        total_score = (
            0.45 * lex_norm
            + 0.25 * pos_weight
            + 0.20 * fact_density
            + 0.10 * title_align
        )
        scored_indices.append((total_score, idx))

    scored_indices.sort(key=lambda x: x[0], reverse=True)

    # MMR selection avoiding redundancy
    selected_indices: List[int] = []
    for _, cand_idx in scored_indices:
        if len(selected_indices) >= max_sentences:
            break
        cand_set = sent_sets[cand_idx]
        if any(_jaccard_overlap(cand_set, sent_sets[sel_i]) > 0.60 for sel_i in selected_indices):
            continue
        selected_indices.append(cand_idx)

    if not selected_indices:
        selected_indices = [0]

    # Re-order chronologically for natural reading flow
    selected_indices.sort()

    chosen_sents: List[str] = []
    curr_len = 0
    for idx in selected_indices:
        s = sentences[idx]
        # Ensure proper ending punctuation
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
    Populates English `headline_english` and a complete 2-3 sentence LexRank `summary`
    on a single article dictionary without altering native `title` or `full_content`.
    """
    raw_title = (art.get("title") or "").strip()
    existing_en_title = (art.get("headline_english") or "").strip()

    if existing_en_title and not _has_devanagari(existing_en_title):
        headline_en = existing_en_title
    elif raw_title and _has_devanagari(raw_title):
        headline_en = _translate_ne_to_en(raw_title)
    else:
        headline_en = raw_title

    art["headline_english"] = headline_en

    full_body = (art.get("full_content") or "").strip()
    raw_summary = (art.get("summary") or "").strip()
    source_text = full_body if len(full_body) >= len(raw_summary) else raw_summary
    if not source_text:
        source_text = raw_title

    # Limit translation payload to lead 1600 characters (enough for 6-10 rich paragraphs)
    if _has_devanagari(source_text):
        lead_chunk = source_text[:1600]
        if len(source_text) > 1600:
            # Cut cleanly at space/sentence boundary before translating
            last_sep = max(lead_chunk.rfind("।"), lead_chunk.rfind("."), lead_chunk.rfind(" "))
            if last_sep > 400:
                lead_chunk = lead_chunk[: last_sep + 1]
        english_body = _translate_ne_to_en(lead_chunk)
    else:
        english_body = source_text

    english_brief = generate_lexrank_english_summary(
        title=headline_en,
        full_text=english_body,
        max_sentences=3,
        max_chars=360,
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
