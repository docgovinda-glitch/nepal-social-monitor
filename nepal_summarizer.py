"""
nepal_summarizer.py
Single Source of Truth for Cross-Lingual Translation and Hybrid LexRank Extractive Summarization.
Zero external AI models, zero Ollama, zero paid APIs. Pure Python deterministic NLP.
"""

import os
import re
import ssl
import html
import math
import json
import time
import atexit
import logging
import threading
import collections
import urllib.request
import urllib.parse
import concurrent.futures
from collections import Counter
from typing import List, Dict, Any, Callable, Optional, Tuple
from nepal_config import _has_devanagari

logger = logging.getLogger("nepal_summarizer")

TRANSLATION_CACHE_MAX_SIZE = int(os.getenv("TRANSLATION_CACHE_MAX_SIZE", "5000"))
TRANSLATION_CACHE_DIR = os.getenv("TRANSLATION_CACHE_DIR", "")


class TranslationLRUCache:
    """
    Persistent SQLite-backed (diskcache) and thread-safe bounded LRU translation cache.
    Falls back gracefully to an in-memory OrderedDict if the filesystem is read-only or diskcache is missing.
    """
    def __init__(self, maxsize: int = 5000, cache_dir: Optional[str] = None):
        self.maxsize = max(1, maxsize)
        self._mem_cache = collections.OrderedDict()
        self._lock = threading.Lock()
        self._disk_cache = None

        target_dir = cache_dir or TRANSLATION_CACHE_DIR
        if not target_dir:
            import tempfile
            target_dir = os.path.join(tempfile.gettempdir(), "nepal_monitor_translation_cache")

        try:
            import diskcache
            os.makedirs(target_dir, exist_ok=True)
            self._disk_cache = diskcache.Cache(target_dir, size_limit=int(1e8))  # ~100 MB limit
            logger.info(f"Initialized diskcache TranslationLRUCache at {target_dir}")
        except Exception as exc:
            logger.info(f"Diskcache unavailable or directory unwriteable ({exc}); using in-memory LRU cache.")
            self._disk_cache = None

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key not in self._mem_cache:
                if self._disk_cache is not None:
                    try:
                        val = self._disk_cache.get(key, default=None)
                        if val is not None:
                            self._mem_cache[key] = val
                            return val
                    except Exception:
                        pass
                return default
            self._mem_cache.move_to_end(key)
            return self._mem_cache[key]

    def __contains__(self, key: str) -> bool:
        with self._lock:
            if key in self._mem_cache:
                return True
            if self._disk_cache is not None:
                try:
                    return key in self._disk_cache
                except Exception:
                    pass
            return False

    def __getitem__(self, key: str) -> str:
        with self._lock:
            if key not in self._mem_cache:
                if self._disk_cache is not None:
                    try:
                        val = self._disk_cache.get(key, default=None)
                        if val is not None:
                            self._mem_cache[key] = val
                            return val
                    except Exception:
                        pass
                raise KeyError(key)
            self._mem_cache.move_to_end(key)
            return self._mem_cache[key]

    def __setitem__(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._mem_cache:
                self._mem_cache.move_to_end(key)
            self._mem_cache[key] = value
            if len(self._mem_cache) > self.maxsize:
                evicted_key, _ = self._mem_cache.popitem(last=False)
                if self._disk_cache is not None:
                    try:
                        self._disk_cache.delete(evicted_key)
                    except Exception:
                        pass
            if self._disk_cache is not None:
                try:
                    self._disk_cache.set(key, value)
                except Exception:
                    pass

    def set(self, key: str, value: str) -> None:
        self[key] = value

    def clear(self) -> None:
        with self._lock:
            if self._disk_cache is not None:
                try:
                    self._disk_cache.clear()
                except Exception:
                    pass
            self._mem_cache.clear()

    def close(self) -> None:
        """Closes the underlying SQLite diskcache cleanly and clears in-memory structures."""
        with self._lock:
            if self._disk_cache is not None:
                try:
                    self._disk_cache.close()
                except Exception:
                    pass
                self._disk_cache = None
            self._mem_cache.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def __len__(self) -> int:
        with self._lock:
            return len(self._mem_cache)


_TRANSLATION_CACHE = TranslationLRUCache(maxsize=TRANSLATION_CACHE_MAX_SIZE)
atexit.register(_TRANSLATION_CACHE.close)

# Circuit breaker & local translation fallback settings
ENABLE_LOCAL_TRANSLATION_FALLBACK = (
    os.getenv("ENABLE_LOCAL_TRANSLATION_FALLBACK", "false").lower() in ("true", "1", "yes")
)
# "google" (default): Google first, local NLLB as fallback. "local": local NLLB first, Google as backup.
TRANSLATION_PRIMARY = os.getenv("TRANSLATION_PRIMARY", "google").strip().lower()
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("TRANSLATION_CIRCUIT_BREAKER_THRESHOLD", "3"))
CIRCUIT_BREAKER_COOLDOWN_SECS = int(os.getenv("TRANSLATION_CIRCUIT_COOLDOWN_SECS", "600"))

_CB_LOCK = threading.Lock()
_CONSECUTIVE_FAILURES = 0
_CIRCUIT_OPEN_UNTIL = 0.0


def is_circuit_breaker_open() -> bool:
    """Returns True if the translation circuit breaker is currently open (cooling down)."""
    with _CB_LOCK:
        if _CIRCUIT_OPEN_UNTIL > 0:
            if time.time() < _CIRCUIT_OPEN_UNTIL:
                return True
            else:
                logger.info("Translation circuit breaker cooldown expired; attempting recovery to primary endpoint.")
                return False
        return False


def record_translation_failure(reason: str = "") -> None:
    """Records a failure on primary translation endpoints and trips the circuit breaker if threshold is reached."""
    global _CONSECUTIVE_FAILURES, _CIRCUIT_OPEN_UNTIL
    with _CB_LOCK:
        _CONSECUTIVE_FAILURES += 1
        logger.warning(
            f"Primary translation failure #{_CONSECUTIVE_FAILURES} (threshold {CIRCUIT_BREAKER_THRESHOLD}): {reason}"
        )
        if _CONSECUTIVE_FAILURES >= CIRCUIT_BREAKER_THRESHOLD:
            _CIRCUIT_OPEN_UNTIL = time.time() + CIRCUIT_BREAKER_COOLDOWN_SECS
            logger.error(
                f"Translation Circuit Breaker OPENED for {CIRCUIT_BREAKER_COOLDOWN_SECS}s. "
                f"Routing to {'local offline NLLB' if ENABLE_LOCAL_TRANSLATION_FALLBACK else 'text fallback'}."
            )


def record_translation_success() -> None:
    """Resets consecutive failures and closes the circuit breaker upon a successful primary translation."""
    global _CONSECUTIVE_FAILURES, _CIRCUIT_OPEN_UNTIL
    with _CB_LOCK:
        if _CONSECUTIVE_FAILURES > 0 or _CIRCUIT_OPEN_UNTIL > 0:
            logger.info("Primary translation service recovered; circuit breaker CLOSED.")
        _CONSECUTIVE_FAILURES = 0
        _CIRCUIT_OPEN_UNTIL = 0.0


_LOCAL_MODEL = None
_LOCAL_MODEL_LOCK = threading.Lock()


def _load_local_nllb_model():
    """
    Lazy-loads CTranslate2 INT8 model (Serkan007/CTranslate2-nllb-200-int8) on CPU on first fallback invocation.
    Provides ~4x faster inference and 60% less RAM compared to PyTorch transformers.
    """
    global _LOCAL_MODEL
    if _LOCAL_MODEL is not None:
        return _LOCAL_MODEL
    with _LOCAL_MODEL_LOCK:
        if _LOCAL_MODEL is not None:
            return _LOCAL_MODEL
        model_name = os.getenv("LOCAL_NLLB_MODEL_NAME", "Serkan007/CTranslate2-nllb-200-int8")
        logger.info(f"Lazy-loading local CTranslate2 translation model ({model_name} on CPU int8)...")
        try:
            from hf_hub_ctranslate2 import MultiLingualTranslatorCT2fromHfHub
            _LOCAL_MODEL = MultiLingualTranslatorCT2fromHfHub(
                model_name_or_path=model_name,
                device="cpu",
                compute_type="int8",
            )
            logger.info("Local CTranslate2 INT8 model successfully loaded on CPU.")
            return _LOCAL_MODEL
        except Exception as exc:
            logger.warning(f"Failed to load CTranslate2 model ({exc}); attempting PyTorch transformers fallback...")
            try:
                from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
                fallback_name = "facebook/nllb-200-distilled-600M"
                tok = AutoTokenizer.from_pretrained(fallback_name)
                mod = AutoModelForSeq2SeqLM.from_pretrained(fallback_name)
                mod.eval()
                _LOCAL_MODEL = (mod, tok)
                logger.info("Loaded PyTorch fallback NLLB model.")
                return _LOCAL_MODEL
            except Exception as e2:
                logger.error(f"All local translation model loaders failed: {e2}")
                raise


def _translate_with_local_model(text: str, source_lang: str = "ne") -> str:
    """Translates text using local NLLB model on CPU when circuit breaker is active or endpoints fail."""
    if not text:
        return ""
    try:
        model_obj = _load_local_nllb_model()
        src_lang = "hin_Deva" if source_lang == "hi" else "npi_Deva"
        tgt_lang = "eng_Latn"

        chunks = [text] if len(text) <= 500 else [p.strip() for p in text.split("\n\n") if p.strip()]
        out_chunks = []

        # Check if model_obj is MultiLingualTranslatorCT2fromHfHub or PyTorch tuple
        if hasattr(model_obj, "generate"):
            # CTranslate2 path
            for ch in chunks:
                tr = model_obj.generate(
                    text=ch,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                    beam_size=4,
                    max_decoding_length=512,
                )
                if isinstance(tr, list):
                    out_chunks.append(tr[0] if tr else ch)
                else:
                    out_chunks.append(str(tr))
        else:
            # PyTorch fallback path
            mod, tok = model_obj
            import torch
            tok.src_lang = src_lang
            for ch in chunks:
                inputs = tok(ch, return_tensors="pt", truncation=True, max_length=512)
                forced_bos_token_id = tok.convert_tokens_to_ids(tgt_lang)
                with torch.no_grad():
                    outputs = mod.generate(**inputs, forced_bos_token_id=forced_bos_token_id, max_length=512)
                out_chunks.append(tok.batch_decode(outputs, skip_special_tokens=True)[0])

        return "\n\n".join(out_chunks).strip()
    except Exception as exc:
        logger.error(f"Local NLLB translation failed: {type(exc).__name__}: {exc}")
        return text


# High-priority entity mapping for pre-translation preservation
_HIGH_PRIORITY_ENTITY_RULES = [
    # Compound / High-specificity organizations & locations first
    (r"(?:अख्तियार\s*दुरुपयोग\s*अनुसन्धान\s*आयोग|अख्तियार)", "CIAA"),
    (r"(?:नेपाल\s*राष्ट्र\s*बैंक|राष्ट्र\s*बैंक)", "Nepal Rastra Bank"),
    (r"(?:सर्वोच्च\s*अदालत)", "Supreme Court"),
    (r"(?:निर्वाचन\s*आयोग)", "Election Commission"),
    (r"(?:सिंहदरबार|सिंह\s*दरबार|सिंहदरवार|सिंह\s*दरवार)", "Singha Durbar"),
    (r"(?:शीतल\s*निवास|शितल\s*निवास|शीतलनिवास|शितलनिवास)", "Sheetal Niwas"),
    (r"(?:बालुवाटार|वालुवाटार)", "Baluwatar"),
    (r"(?:नेकपा\s*\(एमाले\)|नेकपा\s*एमाले|एमाले)", "CPN-UML"),
    (r"(?:राष्ट्रिय\s*स्वतन्त्र\s*पार्टी|रास्वपा)", "RSP"),
    (r"(?:नेकपा\s*\(माओवादी\s*केन्द्र\)|नेकपा\s*माओवादी\s*केन्द्र|माओवादी\s*केन्द्र)", "Maoist Centre"),
    (r"(?:नेपाली\s*का[ङ्गं]ग्रेस|का[ङ्गं]ग्रेस)", "Nepali Congress"),
    (r"(?:बालेन्द्र\s*शाह|बालेन\s*शाह)", "Balendra Shah"),
    (r"बालेन", "Balen"),
    (r"(?:केपी\s*शर्मा\s*ओली|केपी\s*ओली)", "KP Sharma Oli"),
    (r"(?:पुष्पकमल\s*दाहाल\s*['\"]?प्रचण्ड['\"]?|पुष्पकमल\s*दाहाल|प्रचण्ड)", "Pushpa Kamal Dahal (Prachanda)"),
    (r"(?:शेरबहादुर\s*देउ[वाबा]|देउ[वाबा])", "Sher Bahadur Deuba"),
    (r"(?:रवि\s*लामिछाने)", "Rabi Lamichhane"),
    (r"(?:गगन\s*थापा|गगनकुमार\s*थापा)", "Gagan Thapa"),
    (r"(?:कुलमान\s*घिसिङ)", "Kulman Ghising"),
    (r"(?:नेपाल\s*विद्युत\s*प्राधिकरण|विद्युत\s*प्राधिकरण)", "Nepal Electricity Authority"),
]

_POSTPOSITION_CHARS = "मालेलाईकोकाकीबाटदेखिसँगसंगभित्रतर्फविरुद्धसहित"


def mask_entities_for_translation(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Masks high-priority entities, acronyms and proper nouns with deterministic tokens
    (__ENT001__, __ENT002__, etc.) before sending text to machine translation.
    Detaches attached Devanagari postpositions so prepositions translate naturally.
    """
    if not text:
        return text, {}
    mask_map: Dict[str, str] = {}
    entity_to_tok: Dict[str, str] = {}
    out = text
    idx = 1

    for pat, en_name in _HIGH_PRIORITY_ENTITY_RULES:
        full_pat = re.compile(pat + rf"(?P<post>[{_POSTPOSITION_CHARS}])?", re.UNICODE)

        def _repl(m: re.Match) -> str:
            nonlocal idx
            if en_name in entity_to_tok:
                token = entity_to_tok[en_name]
            else:
                token = f"__ENT{idx:03d}__"
                entity_to_tok[en_name] = token
                mask_map[token] = en_name
                idx += 1
            post = m.group("post")
            if post:
                return f"{token} {post}"
            return token

        out = full_pat.sub(_repl, out)

    return out, mask_map


def restore_entities_after_translation(text: str, mask_map: Dict[str, str]) -> str:
    """
    Restores deterministic entity tokens (__ENT001__) to their exact proper English forms.
    Tolerates machine-translation variations in whitespace, casing, and underscores (e.g. _ ent 001 _).
    """
    if not text or not mask_map:
        return text or ""

    def _repl(m: re.Match) -> str:
        tok_num = m.group(1)
        full_tok = f"__ENT{int(tok_num):03d}__"
        return mask_map.get(full_tok, m.group(0))

    # Regex matches: r'_{1,2}\s*ent\s*(\d{1,3})\s*_{1,2}' case-insensitively
    restored = re.sub(r"_{1,2}\s*ent\s*(\d{1,3})\s*_{1,2}", _repl, text, flags=re.IGNORECASE)
    return re.sub(r"[ \t]+", " ", restored).strip()

_SSL_CTX = ssl._create_unverified_context()
_TRANSLATE_SEM = threading.Semaphore(2)
_ROTATION_LOCK = threading.Lock()
_CLIENT_ROTATION_IDX = 0
_TRANSLATE_BUCKETS = [
    ("translate_a/t", "dict-chrome-ex"),
    ("translate_a/single", "at"),
    ("translate_a/single", "tw-ob"),
    ("translate_a/single", "it"),
    ("translate_a/single", "gtx"),
]

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
    r"(?:Author|Written\s+by|Reported\s+by)\s+[^|\n।]{2,55}(?:\s*\|\s*(?:Edited\s+by|Updated|Desk)[^|\n।]{2,55})?\s*"
    r"|"
    r"Edited\s+by\s+[^|\n।]{2,55}\s*"
    r"|"
    r"(?:By\s+[A-Z][a-zA-Z\.\-\s\(\)]{2,60}\s+)?"
    r"(?:Published|Updated|Last\s+Updated)\s*:\s*(?:\d{1,2}:\d{2}\s*(?:am|pm)?\s*)?(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}(?:\s*,?\s*\d{1,2}:\d{1,2}(?::\d{1,2})?\s*(?:am|pm|IST|NPT)?)?(?:\s*[\(\[][A-Z]{2,5}[\)\]])?\s*"
    r"|"
    r"By\s+[A-Za-z\.\-\s\(\)\|]{2,60}(?=\s+(?:Published|The|A|In|Nepal|India|[A-Z][a-z]+|[\u0900-\u097F]))"
    r"|"
    r"[^\n]{0,60}©\s*\d{4}[^\n]{0,120}?(?=(?:Kathmandu|Pokhara|New\s+Delhi|[A-Z][a-z]+\s+[A-Z][a-z]+))"
    r"|"
    r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}(?:\s+\d{1,2}:\d{1,2}(?::\d{1,2})?)?\s*"
    r"|"
    r"(?:by\s+)?[a-z]+\s*\|\s*(?:bureau|desk|correspondent|team)\s*"
    r"|"
    r"[A-Za-z][A-Za-z\s\.,/\-]{1,35}(?:\[[^\]]{2,30}\])?(?:,?\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?)?\s*\([A-Z0-9/\-]{2,15}\)\s*[:\-–—]\s*"
    r"|"
    r"[A-Z][A-Z\s\.\-]{1,22}\s*[:/]\s*"
    r"|"
    r"(?:kathmandu|new\s+york|washington(?:\s+d\.?c\.?)?|mumbai|new\s+delhi|beijing|london|tokyo|geneva|antalya|"
    r"pokhara|chitwan|morang|biratnagar|birgunj|janakpur|lalitpur|bhaktapur|bardia|bardiya|tansen|sindhuli|"
    r"dhangadhi|butwal|hetauda|nepalgunj|surkhet|dhaka|islamabad|jamshedpur\s+news|bhagalpur\s+news|pti|ani|rss|ians|reuters|ap|afp)"
    r"(?:\s*\[[^\]]{2,30}\])?(?:\s*,\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?|\s*,\s*[a-zA-Z0-9\s\.]+)?\s*[\.:\-–—|।/]\s*"
    r"|"
    r"(?:प्रभात\s+खबर\s+को\s+Google\s+पर\s+पसंदीदा\s+सोर्स\s+बनाएं\s*[→\-]*\s*|Make\s+Prabhat\s+Khabar\s+your\s+favorite\s+source\s+on\s+Google\s*[→\-]*\s*|Add\s+as\s+a\s+preferred\s+source\s+on\s+Google\s*)"
    r"|"
    r"(?:काठमाडौँ|काठमाडौं|पोखरा|विराटनगर|वीरगन्ज|जनकपुर(?:\s+धाम)?(?:/मुजफ्फरपुर)?|ललितपुर|लण्डन|नयाँदिल्ली|तानसेन|सिन्धुली|मधुबनी|रक्सौल|भागलपुर|अर्घाखाँची|घोराही)(?:\s+सड़क\s+मार्ग)?(?:,\s*[\u0900-\u097F\s०-९0-9]+)?\s*[:\-–—|।]\s*"
    r"|"
    r"(?:[\u0900-\u097F]+,\s*)?(?:वैशाख|जेठ|असार|साउन|भदौ|असोज|कात्तिक|मंसिर|मङ्सिर|पुस|पौष|माघ|फागुन|चैत)\s+[०-९0-9]{1,2}(?:\s*गते)?\s*[:\-–—|।]\s*"
    r"|"
    r"\d{1,2}\s+[\u0900-\u097F]+\s*,\s*[\u0900-\u097F]+\s*[।:]\s*"
    r")+",
    re.IGNORECASE,
)

_STANDALONE_META_PARA_RE = re.compile(
    r"^\s*(?:"
    r"(?:author|written\s+by|edited\s+by|reported\s+by|by)\s+.{2,90}"
    r"|(?:published|updated|last\s+updated)\s*:\s*.*"
    r"|[^\n]{0,60}©\s*\d{4}[^\n]{0,100}"
    r"|[a-z\s]+,\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?"
    r"|[a-z0-9\s/]+/photo[a-z0-9\s]*"
    r"|प्रतीकात्मक\s+(?:AI\s+)?तस्वीर.*"
    r"|.*(?:तस्बिर|तस्विर)\s*[:ः].*"
    r"|प्रभात\s+खबर\s+को\s+Google\s+पर.*"
    r"|.*Prabhat\s+Khabar\s+Network.*"
    r")\s*$",
    re.IGNORECASE,
)

_BOILERPLATE_TAIL_RE = re.compile(
    r"\s*(?:The\s+post\s+.+?\s+appeared\s+first\s+on\s+.*$|also read.*$|read more.*$|"
    r"follow us on.*$|share on.*$|subscribe to.*$|click here.*$|"
    r"for more news.*$|copyright ©.*$|all rights reserved.*$|news summary generated.*$)",
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
    return re.sub(r"[ \t]+", " ", out).strip()


_NEPALI_DISTINCTIVE_MARKERS = re.compile(
    r"(?:^|\s)(?:गर्ने|गरेको|गरिएको|भएको|छन्|गरेका|भने|गर्दै|रहेका|रहेको|गरे|भनेर|गर्न|भनेका|गरेकी|हुने|हुनेछ|गरेपछि|लागि|बाट|सँग|लाई|बारे|तर्फ|अनुसार)(?:\s|[।,.!?]|$)"
)
_HINDI_DISTINCTIVE_MARKERS = re.compile(
    r"(?:^|\s)(?:है|हैं|था|थी|थे|में|से|की|के|को|पर|और|नहीं|कहा|किया|होगा|होगी|होंगे|होने|गया|गई|गए)(?:\s|[।,.!?]|$)"
)


def detect_text_language(text: str, declared_lang: str = "") -> str:
    """
    Detects whether text is English ('en'), Nepali ('ne'), Hindi ('hi'), or another non-English language ('auto').
    Distinguishes Hindi vs. Nepali Devanagari using distinctive morphological postpositions and verb auxiliaries.
    """
    raw = (text or "").strip()
    decl = (declared_lang or "").strip().lower()
    if _has_devanagari(raw):
        if decl in ("nepali", "ne"):
            return "ne"
        if decl in ("hindi", "hi"):
            return "hi"

        ne_hits = len(_NEPALI_DISTINCTIVE_MARKERS.findall(raw))
        hi_hits = len(_HINDI_DISTINCTIVE_MARKERS.findall(raw))

        if hi_hits > ne_hits:
            return "hi"
        if ne_hits > hi_hits:
            return "ne"

        # Default Devanagari within nepal-social-monitor domain is Nepali
        return "ne"

    # Strip URLs, @mentions, #hashtags, emojis/punctuation before checking non-Latin scripts
    stripped = re.sub(r"https?://\S+|@[A-Za-z0-9_]+|#[A-Za-z0-9_]+", "", raw)
    non_ascii_letters = [ch for ch in stripped if ord(ch) > 127 and ch.isalpha()]
    if len(non_ascii_letters) >= 4:
        return "auto"
    return "en"


def _translate_chunk_with_failover(chunk: str, sl_code: str, timeout: int = 8) -> str:
    """Zero-key translation failover across working POST endpoints on translate.googleapis.com with circuit breaker & tenacity."""
    global _CLIENT_ROTATION_IDX
    clean_chunk = (chunk or "").strip()
    if not clean_chunk:
        return ""

    if TRANSLATION_PRIMARY == "local" and ENABLE_LOCAL_TRANSLATION_FALLBACK:
        _loc = _translate_with_local_model(clean_chunk, source_lang=sl_code)
        if _loc and _loc.strip() != clean_chunk and not _has_devanagari(_loc):
            return _loc
        logger.info("Local NLLB gave no usable result; trying Google endpoints.")

    if is_circuit_breaker_open():
        if ENABLE_LOCAL_TRANSLATION_FALLBACK:
            return _translate_with_local_model(clean_chunk, source_lang=sl_code)
        return clean_chunk

    with _ROTATION_LOCK:
        start_idx = _CLIENT_ROTATION_IDX % 4
        _CLIENT_ROTATION_IDX += 1

    ordered = _TRANSLATE_BUCKETS[start_idx:4] + _TRANSLATE_BUCKETS[:start_idx] + _TRANSLATE_BUCKETS[4:]
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    }
    encoded_body = urllib.parse.urlencode({"q": clean_chunk}).encode("utf-8")

    def _execute_single_request(url: str, path: str) -> Optional[str]:
        req = urllib.request.Request(url, data=encoded_body, headers=headers, method="POST")
        with _TRANSLATE_SEM:
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                out = ""
                if path == "translate_a/t":
                    if isinstance(data, list) and data:
                        out = data[0] if isinstance(data[0], str) else str(data[0][0])
                else:
                    if isinstance(data, list) and data and isinstance(data[0], list):
                        out = "".join(seg[0] for seg in data[0] if seg and seg[0])
                if out and out.strip() and out.strip() != clean_chunk and not _has_devanagari(out):
                    return out.strip()
        return None

    # Tenacity-wrapped request executor (absorbs transient network blips without blocking circuit breaker)
    try:
        from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
        @retry(
            stop=stop_after_attempt(2),
            wait=wait_exponential_jitter(multiplier=0.5, max=3.0),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        def _retryable_call(url: str, path: str) -> Optional[str]:
            return _execute_single_request(url, path)
    except Exception:
        def _retryable_call(url: str, path: str) -> Optional[str]:
            return _execute_single_request(url, path)

    last_err = ""
    for path, client in ordered:
        url = f"https://translate.googleapis.com/{path}?client={client}&sl={sl_code}&tl=en"
        if path == "translate_a/single":
            url += "&dt=t"
        try:
            res = _retryable_call(url, path)
            if res:
                record_translation_success()
                return res
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            continue

    record_translation_failure(last_err or "Primary endpoints failed to translate Devanagari")
    if ENABLE_LOCAL_TRANSLATION_FALLBACK:
        logger.info("Primary endpoints exhausted; routing to local offline NLLB model.")
        return _translate_with_local_model(clean_chunk, source_lang=sl_code)

    return clean_chunk


def _translate_batch_group(items: List[str], sl_code: str, timeout: int = 10) -> List[str]:
    """Translates a small aligned batch via newline-delimited POST, recursively halving if line counts drift."""
    if not items:
        return []
    payload = "\n".join(items)
    translated = _translate_chunk_with_failover(payload, sl_code=sl_code, timeout=timeout)
    if translated == payload and _has_devanagari(payload):
        if len(items) == 1:
            return [items[0]]
        mid = len(items) // 2
        return _translate_batch_group(items[:mid], sl_code, timeout) + _translate_batch_group(items[mid:], sl_code, timeout)

    out_lines = translated.splitlines()
    if len(out_lines) == len(items):
        return [ln.strip() or orig for ln, orig in zip(out_lines, items)]

    if len(items) == 1:
        return [translated.replace("\n", " ").strip() or items[0]]

    mid = len(items) // 2
    return _translate_batch_group(items[:mid], sl_code, timeout) + _translate_batch_group(items[mid:], sl_code, timeout)


def _translate_batch_to_en(texts: List[str], source_lang: str = "ne", timeout: int = 10) -> List[str]:
    """Translates a list of Devanagari texts in batched POST requests with entity masking, updating _TRANSLATION_CACHE."""
    if not texts:
        return []
    sl_code = "hi" if source_lang == "hi" else "ne"
    results: List[str] = [""] * len(texts)
    pending: List[tuple] = []  # (idx, cache_key, one_line_prepped, clean, mask_map)

    for idx, raw in enumerate(texts):
        clean = (raw or "").strip()
        if not clean:
            continue
        if not _has_devanagari(clean):
            results[idx] = normalize_english_proper_nouns(clean)
            continue
        cache_key = f"{source_lang}::{clean}"
        if cache_key in _TRANSLATION_CACHE:
            results[idx] = _TRANSLATION_CACHE[cache_key]
            continue
        prepped = _normalize_devanagari_before_translation(clean) if source_lang != "hi" else clean
        masked, mmap = mask_entities_for_translation(prepped)
        one_line = re.sub(r"[\r\n\t]+", " ", masked)
        one_line = re.sub(r"\s+", " ", one_line).strip()
        pending.append((idx, cache_key, one_line, clean, mmap))

    # Deduplicate identical pending strings
    unique_map: Dict[str, tuple] = {}
    for idx, ckey, one_line, orig, mmap in pending:
        unique_map.setdefault(ckey, (one_line, orig, mmap))

    unique_keys = list(unique_map.keys())
    pos = 0
    while pos < len(unique_keys):
        batch_keys: List[str] = []
        batch_strs: List[str] = []
        batch_mmaps: List[Dict[str, str]] = []
        char_budget = 0
        while pos < len(unique_keys) and len(batch_keys) < 16:
            k = unique_keys[pos]
            s = unique_map[k][0]
            mmap = unique_map[k][2]
            if batch_keys and (char_budget + len(s) + 1 > 3400):
                break
            batch_keys.append(k)
            batch_strs.append(s)
            batch_mmaps.append(mmap)
            char_budget += len(s) + 1
            pos += 1

        translated_strs = _translate_batch_group(batch_strs, sl_code=sl_code, timeout=timeout)
        for k, src_line, tr_line, mmap in zip(batch_keys, batch_strs, translated_strs, batch_mmaps):
            restored = restore_entities_after_translation(tr_line, mmap)
            norm_tr = normalize_english_proper_nouns(restored)
            if norm_tr and not _has_devanagari(norm_tr) and tr_line != src_line:
                _TRANSLATION_CACHE[k] = norm_tr

    for idx, ckey, one_line, orig, mmap in pending:
        if ckey in _TRANSLATION_CACHE:
            results[idx] = _TRANSLATION_CACHE[ckey]
        else:
            results[idx] = orig

    return results


def _translate_ne_to_en(text: str, timeout: int = 8, source_lang: str = "ne", force_translate: bool = False) -> str:
    """Translates Nepali, Hindi, or auto-detected non-English text into English with entity masking and proper-noun normalization."""
    clean = (text or "").strip()
    if not clean:
        return clean
    if not force_translate and source_lang != "auto" and not _has_devanagari(clean):
        return normalize_english_proper_nouns(clean)
    cache_key = f"{source_lang}::{clean}"
    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]

    prepped = _normalize_devanagari_before_translation(clean) if source_lang == "ne" else clean
    sl_code = source_lang if source_lang in ("ne", "hi", "auto") else "ne"

    # Pre-translation entity masking
    masked_prepped, mask_map = mask_entities_for_translation(prepped)

    chunks = []
    if len(masked_prepped) <= 2500:
        chunks = [masked_prepped]
    else:
        paras = masked_prepped.split("\n\n")
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
        restored = restore_entities_after_translation(tr, mask_map)
        translated_chunks.append(normalize_english_proper_nouns(restored))

    result = "\n\n".join(translated_chunks).strip()
    if not any_failed and not _has_devanagari(result):
        _TRANSLATION_CACHE[cache_key] = result
    return result


_READ_TIME_RE = re.compile(r"\b\d+\s*min(?:utes?)?\s+read\b[:|\s-]*", re.IGNORECASE)
_LAST_UPDATED_RE = re.compile(
    r"\b(?:Last\s+Updated|Updated\s+on|Updated|Published\s+on|Published)\s*:\s*"
    r"[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}(?:\s*\|\s*\d{1,2}:\d{2}\s*(?:AM|PM)?\s*(?:IST|NPT|UTC|GMT)?)?\s*",
    re.IGNORECASE,
)


def clean_journalistic_text(text: str, title: str = "") -> str:
    """Strips HTML, wire datelines, read-time/updated prefixes, and editorial boilerplate while preserving sentence structure and fixing Unicode."""
    if not text:
        return ""
    try:
        import ftfy
        s = ftfy.fix_text(str(text))
    except Exception:
        s = str(text)
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("\xa0", " ")
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for _ in range(3):
        prev = s
        s = _READ_TIME_RE.sub("", s).strip()
        s = _LAST_UPDATED_RE.sub("", s).strip()
        s = _DATELINE_RE.sub("", s).strip()
        if s == prev:
            break
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
    """Splits cleaned text into well-formed sentences without slicing inside numbers, English abbreviations, or Devanagari abbreviations."""
    # Protect common English and Devanagari abbreviations
    protected = re.sub(r"\b(Mr|Mrs|Ms|Dr|Prof|Hon|Rs|No|St|vs|etc|U\.S|U\.K)\.", r"\1<DOT>", text)
    protected = re.sub(r"(वि\.सं|डा|प्रा|रु|नं|प्र\.जि\.अ|कि\.मी|मे\.वा|मु\.अ|अ\.नि)\.", r"\1<DOT>", protected)
    protected = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", protected)
    protected = re.sub(r"(?:^|(?<=[.!?।])\s+)\d{1,2}\.\s+", r" ", protected)
    raw_sents = re.split(r"(?<=[.!?।])\s+", protected)
    sents = []
    for s in raw_sents:
        restored = s.replace("<DOT>", ".").strip()
        restored = _DATELINE_RE.sub("", restored).strip()
        restored = _DANGLING_LEAD_PREFIX_RE.sub("", restored).strip()
        if not restored:
            continue
        # Ensure first char is capitalized for English Latin text; allow Devanagari Unicode
        if not _has_devanagari(restored) and restored[0].islower():
            continue
        word_count = len(restored.split())
        if word_count < 7 or word_count > 55:
            continue
        # Filter bare image captions / noun phrases lacking a finite verb in English text
        if not _has_devanagari(restored) and not _FINITE_VERB_RE.search(restored):
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


def _scope_top_paragraphs(text: str, max_paras: int = 8, title: str = "") -> str:
    """Restricts body text to clean opening paragraphs, dropping bylines, photo credits, and duplicate titles."""
    if not text:
        return ""
    norm_title = re.sub(r"\s+", " ", (title or "")).strip().lower()
    paras = []
    for raw_p in re.split(r"\n\s*\n", text):
        p = re.sub(r"\s+", " ", raw_p.replace("\xa0", " ")).strip()
        if len(p) <= 22:
            continue
        if norm_title and p.lower().rstrip("।.") == norm_title.rstrip("।."):
            continue
        if _STANDALONE_META_PARA_RE.match(p):
            continue
        if ("photo:" in p.lower() or "तस्बिर" in p or "तस्विर" in p) and len(p) < 160:
            continue
        paras.append(p)
        if len(paras) >= max_paras:
            break
    if paras:
        return "\n\n".join(paras)
    return text


def _trim_clean_sentence(text: str, limit: int = 460) -> str:
    """Trims overly long prose cleanly at a clause or word boundary without mid-sentence ellipsis."""
    s = re.sub(r"\s+", " ", (text or "")).strip()
    if not s:
        return ""
    if s.endswith("..."):
        s = s[:-3].rstrip(" ,;:-–—")
    if len(s) <= limit:
        if s[-1] not in ".!?":
            s += "."
        return s

    min_cut = max(120, limit // 2)
    window = s[:limit]
    best_cut = -1
    for sep in ("; ", " — ", ", which ", ", where ", ", while ", ", including ", ", after ", ", as "):
        idx = window.rfind(sep)
        if idx >= min_cut:
            best_cut = max(best_cut, idx)
    if best_cut >= min_cut:
        trimmed = window[:best_cut].rstrip(" ,;:-–—")
    else:
        trimmed = window.rsplit(" ", 1)[0].rstrip(" ,;:-–—")
    if trimmed and trimmed[-1] not in ".!?":
        trimmed += "."
    return trimmed


def _extract_native_salient_sentences(title: str, body: str, max_sentences: int = 2) -> str:
    """Pre-selects 2 clean, salient Devanagari sentences before machine translation to minimize API load."""
    scoped = _scope_top_paragraphs(body, max_paras=8, title=title)
    cleaned = clean_journalistic_text(scoped, title=title)
    if not cleaned:
        return ""

    # Strip leading title again in case HTML didn't separate paragraphs
    clean_t = re.sub(r"\s+", " ", (title or "")).strip()
    if clean_t and cleaned.startswith(clean_t):
        cleaned = cleaned[len(clean_t):].lstrip(" .:-–—|।")
        cleaned = _DATELINE_RE.sub("", cleaned).strip()

    raw_sents = re.split(r"(?<=[।.!?])\s+", cleaned)
    candidates: List[str] = []
    for raw_s in raw_sents:
        s = _DATELINE_RE.sub("", raw_s).strip()
        if not s:
            continue
        low_s = s.lower()
        if any(k in low_s for k in ("author ", "edited by", "google पर", "prabhat khabar network", "तस्बिर", "तस्विर", "copyright ©")):
            continue
        if len(s.split()) < 5:
            continue
        candidates.append(s)

    if not candidates:
        return cleaned[:420].strip()

    if len(candidates) == 1 or max_sentences <= 1:
        return candidates[0][:480].strip()

    lead = candidates[0]
    lead_tokens = set(re.findall(r"[\u0900-\u097F0-9a-zA-Z]{2,}", (clean_t + " " + lead).lower()))
    best_idx = 1
    best_score = -1.0
    for idx in range(1, min(len(candidates), 6)):
        c = candidates[idx]
        c_tokens = set(re.findall(r"[\u0900-\u097F0-9a-zA-Z]{2,}", c.lower()))
        overlap = len(lead_tokens & c_tokens) / max(1, len(c_tokens))
        has_digits = 0.25 if re.search(r"[0-9०-९]", c) else 0.0
        len_bonus = 0.15 if 8 <= len(c.split()) <= 35 else 0.0
        score = overlap + has_digits + len_bonus - (0.04 * idx)
        if score > best_score:
            best_score = score
            best_idx = idx

    picked = [lead, candidates[best_idx]]
    joined = " ".join(picked).strip()
    if len(joined) > 520:
        return lead[:480].strip()
    return joined


def _needs_body_scrape(art: Dict[str, Any]) -> bool:
    raw_title = (art.get("title") or "").strip()
    full_body = (art.get("full_content") or "").strip()
    raw_summary = (art.get("summary") or "").strip()
    source_text = full_body if len(full_body) >= len(raw_summary) else raw_summary
    link = (art.get("link") or "").strip()
    if not link.startswith("http"):
        return False
    return (
        not source_text
        or len(source_text) < 750
        or (full_body == raw_summary and len(source_text) < 1200)
        or "..." in source_text
        or "…" in source_text
        or "appeared first on" in source_text.lower()
        or source_text == raw_title
    )


def generate_lexrank_english_summary(
    title: str,
    full_text: str,
    max_sentences: int = 2,
    max_chars: int = 450,
) -> str:
    """
    Lead-Anchored Hybrid LexRank + Journalistic Salience Summarizer.
    Scores paragraph-scoped sentences by graph centrality, lead position, factual density,
    and topical alignment against the headline, producing a clean 2-sentence executive brief.
    """
    clean_title = normalize_english_proper_nouns(clean_journalistic_text(title))
    scoped_body = _scope_top_paragraphs(full_text, max_paras=8, title=clean_title)
    clean_body = normalize_english_proper_nouns(clean_journalistic_text(scoped_body, title=clean_title))
    if not clean_body:
        return clean_title

    sentences = [s for s in _split_sentences(clean_body) if "..." not in s and "…" not in s]
    if not sentences:
        # Clean dangling ellipsis fragment to last complete clause or word
        no_ellip = re.sub(r"\s*[.…]{2,}\s*$", "", clean_body).strip()
        return _trim_clean_sentence(no_ellip or clean_body, limit=max_chars)

    # Sentence-count guard to ensure graph centrality runs in <10ms even on unpunctuated text
    if len(sentences) > 25:
        sentences = sentences[:25]

    if len(sentences) <= 2:
        joined = " ".join(s if s[-1] in ".!?" else f"{s}." for s in sentences)
        if len(joined) <= max_chars:
            return joined
        return _trim_clean_sentence(sentences[0], limit=max(max_chars, 500))

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
    # Uses RapidFuzz token_set_ratio to penalize paraphrased/duplicate sentences cleanly
    scored_indices.sort(key=lambda x: x[0], reverse=True)
    for _, cand_idx in scored_indices:
        if len(selected_indices) >= max_sentences:
            break
        if cand_idx in selected_indices:
            continue
        cand_sent = sentences[cand_idx]
        cand_set = sent_sets[cand_idx]

        is_dup = False
        for sel_i in selected_indices:
            sel_sent = sentences[sel_i]
            # RapidFuzz similarity check
            try:
                import rapidfuzz.fuzz as fuzz
                sim_ratio = fuzz.token_set_ratio(cand_sent, sel_sent)
                if sim_ratio > 68:
                    is_dup = True
                    break
            except Exception:
                if _jaccard_overlap(cand_set, sent_sets[sel_i]) > 0.58:
                    is_dup = True
                    break

        if is_dup:
            continue
        if not (cand_set & lead_tokens):
            continue
        selected_indices.append(cand_idx)

    # Always re-sort selected sentences back into original chronological order
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
    if len(summary) > max(max_chars, 500):
        summary = _trim_clean_sentence(summary, limit=max(max_chars, 500))
    return summary


def enrich_single_article_english_summary(art: Dict[str, Any]) -> Dict[str, Any]:
    """
    Populates English `headline_english` and a complete 2-sentence LexRank `summary`
    on a single article dictionary without altering native `title` or `full_content`.
    """
    return enrich_articles_with_english_summaries([art], max_workers=1)[0]


def _summary_needs_enrichment(art: Dict[str, Any]) -> bool:
    cur_sum = (art.get("summary") or "").strip()
    cur_title = (art.get("title") or "").strip()
    cur_en_head = (art.get("headline_english") or "").strip()
    if (
        not cur_sum
        or cur_sum == cur_title
        or (cur_en_head and cur_sum == cur_en_head)
        or _has_devanagari(cur_sum)
        or "..." in cur_sum
        or "appeared first on" in cur_sum.lower()
        or (cur_title and _has_devanagari(cur_title) and (not cur_en_head or _has_devanagari(cur_en_head)))
    ):
        return True
    if (
        _DATELINE_RE.match(cur_sum)
        or cur_sum.startswith(("By ", "Author ", "Edited by ", "Published:", "Updated:"))
        or "favorite source on google" in cur_sum.lower()
        or "preferred source on google" in cur_sum.lower()
    ):
        return True
    if re.match(r"^[A-Z]{4,}:\s", cur_sum):
        return True
    return False


def enrich_articles_with_english_summaries(
    articles: List[Dict[str, Any]],
    max_workers: int = 12,
) -> List[Dict[str, Any]]:
    """
    Runs full-body scraping, pre-translation salient sentence selection, batched POST translation,
    and Lead-Anchored LexRank summarization across a batch of articles.
    """
    if not articles:
        return articles

    to_process = [art for art in articles if _summary_needs_enrichment(art)]
    if not to_process:
        return articles

    # Stage 1: Concurrently fetch missing/truncated article bodies from source URLs
    scrape_targets = [art for art in to_process if _needs_body_scrape(art)]
    if scrape_targets:
        def _scrape_one(art: Dict[str, Any]):
            link = (art.get("link") or "").strip()
            existing = (art.get("full_content") or art.get("summary") or "").strip()
            try:
                from nepal_fetcher import extract_article_full_text
                fetched = extract_article_full_text(link, timeout=5)
                if fetched and (len(fetched) > len(existing) or ("appeared first on" in existing.lower() and "appeared first on" not in fetched.lower())):
                    art["full_content"] = fetched
            except Exception:
                pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, 12)) as ex:
            list(ex.map(_scrape_one, scrape_targets))

    # Stage 2: Prepare native headlines + compact 2-sentence bodies grouped by source language
    pending_ne_texts: List[str] = []
    pending_hi_texts: List[str] = []
    title_jobs: List[tuple] = []  # (art_idx, lang_code, list_idx)
    body_jobs: List[tuple] = []   # (art_idx, lang_code, list_idx)
    en_bodies: Dict[int, str] = {}
    en_titles: Dict[int, str] = {}

    for idx, art in enumerate(to_process):
        raw_title = (art.get("title") or "").strip()
        existing_en_title = (art.get("headline_english") or "").strip()
        raw_lang = (art.get("language") or "").strip().lower()
        stream_tag = (art.get("stream") or art.get("portal_category") or "").lower()
        is_hindi = (
            raw_lang == "hindi"
            or "indian" in stream_tag
            or "nepal_relevance_score" in art
            or bool(re.search(r"(?:^|\s)(?:है|हैं|में|से|की|के|को|पर)(?:\s|[।,.]|$)", raw_title))
        )
        lang_code = "hi" if is_hindi else "ne"

        if existing_en_title and not _has_devanagari(existing_en_title):
            en_titles[idx] = normalize_english_proper_nouns(existing_en_title)
        elif raw_title and _has_devanagari(raw_title):
            target_list = pending_hi_texts if lang_code == "hi" else pending_ne_texts
            title_jobs.append((idx, lang_code, len(target_list)))
            target_list.append(raw_title)
        else:
            en_titles[idx] = normalize_english_proper_nouns(raw_title)

        full_body = (art.get("full_content") or "").strip()
        raw_summary = (art.get("summary") or "").strip()
        source_text = full_body if len(full_body) >= len(raw_summary) else raw_summary
        if not source_text:
            source_text = raw_title

        if _has_devanagari(source_text):
            compact_native = _extract_native_salient_sentences(raw_title, source_text, max_sentences=2)
            if not compact_native:
                compact_native = raw_title
            target_list = pending_hi_texts if lang_code == "hi" else pending_ne_texts
            body_jobs.append((idx, lang_code, len(target_list)))
            target_list.append(compact_native)
        else:
            en_bodies[idx] = normalize_english_proper_nouns(source_text)

    # Stage 3: Batched HTTP POST translation across 4 rotating endpoints
    tr_ne = _translate_batch_to_en(pending_ne_texts, source_lang="ne") if pending_ne_texts else []
    tr_hi = _translate_batch_to_en(pending_hi_texts, source_lang="hi") if pending_hi_texts else []

    for idx, lang_code, pos in title_jobs:
        tr_title = tr_hi[pos] if lang_code == "hi" else tr_ne[pos]
        if tr_title and not _has_devanagari(tr_title):
            en_titles[idx] = tr_title
        else:
            # Never store untranslated Devanagari inside headline_english
            existing = (to_process[idx].get("headline_english") or "").strip()
            en_titles[idx] = existing if (existing and not _has_devanagari(existing)) else ""

    for idx, lang_code, pos in body_jobs:
        tr_body = tr_hi[pos] if lang_code == "hi" else tr_ne[pos]
        en_bodies[idx] = tr_body

    # Stage 4: Final LexRank summarization & safe assignment (only persist clean English)
    for idx, art in enumerate(to_process):
        headline_en = en_titles.get(idx, "")
        if headline_en and not _has_devanagari(headline_en):
            art["headline_english"] = headline_en
        elif _has_devanagari(art.get("headline_english", "")):
            art["headline_english"] = ""

        body_for_lex = en_bodies.get(idx, "")
        if not body_for_lex or _has_devanagari(body_for_lex):
            continue

        english_brief = generate_lexrank_english_summary(
            title=headline_en or art.get("title", ""),
            full_text=body_for_lex,
            max_sentences=2,
            max_chars=450,
        )
        if english_brief and not _has_devanagari(english_brief) and not english_brief.endswith("..."):
            art["summary"] = english_brief

    return articles


def _emit_progress(on_progress: Optional[Callable[[str, float], None]], msg: str, pct: float) -> None:
    if on_progress is not None:
        try:
            on_progress(msg, max(0.0, min(1.0, float(pct))))
        except Exception:
            pass


def format_english_brief_payload(
    headline: str,
    brief: str,
    source_url: str = "",
    whatsapp_bold: bool = True,
) -> str:
    """
    Formats a 3-part English Brief (Headline, Brief, Link) with clean visual separation
    for WhatsApp sharing and single-click copy.
    Ensures Google News redirect URLs are resolved to their canonical publisher source.
    """
    hl = re.sub(r"\s+", " ", (headline or "").strip()).strip("*").strip()
    body = (brief or "").strip()
    url = (source_url or "").strip()
    if url and "news.google.com" in url.lower():
        try:
            from nepal_fetcher import resolve_google_news_url
            res_u = resolve_google_news_url(url)
            if res_u and "news.google.com" not in res_u.lower():
                url = res_u
        except Exception:
            pass

    parts: List[str] = []
    if hl:
        parts.append(f"*{hl}*" if whatsapp_bold else hl)
    if body and body.strip().lower() != hl.lower():
        parts.append(body)
    elif body and not hl:
        parts.append(body)
    if url:
        parts.append(f"Read Original Source: {url}")
    return "\n\n".join(parts)


def format_reader_copy_payload(
    headline: str,
    full_body: str,
    source_url: str = "",
    whatsapp_bold: bool = False,
) -> str:
    """
    Formats the complete 3-part In-App Reader payload:
    1. Headline (optionally bold for WhatsApp)
    2. Full Body
    3. Direct Article Link
    Ensures Google News redirect URLs are resolved to their canonical publisher source.
    """
    hl = re.sub(r"\s+", " ", (headline or "").strip()).strip("*").strip()
    body = (full_body or "").strip()
    url = (source_url or "").strip()
    if url and "news.google.com" in url.lower():
        try:
            from nepal_fetcher import resolve_google_news_url
            res_u = resolve_google_news_url(url)
            if res_u and "news.google.com" not in res_u.lower():
                url = res_u
        except Exception:
            pass

    parts: List[str] = []
    if hl:
        parts.append(f"*{hl}*" if whatsapp_bold else hl)
    if body:
        parts.append(body)
    if url:
        parts.append(f"Read Original Source: {url}")
    return "\n\n".join(parts)


def generate_on_demand_news_brief(
    item: Dict[str, Any],
    on_progress: Optional[Callable[[str, float], None]] = None,
) -> Dict[str, Any]:
    """
    On-demand user-initiated English Brief generator for Nepali, Hindi, and English news articles.
    Hydrates full content from DB/URL if needed, translates if non-English, summarizes concisely,
    resolves Google News aggregator URLs to canonical publisher links, and returns unified 3-part output.
    """
    work = dict(item)
    source_url = (work.get("link") or "").strip()
    if source_url and "news.google.com" in source_url.lower():
        try:
            from nepal_fetcher import resolve_google_news_url
            res_u = resolve_google_news_url(source_url)
            if res_u and "news.google.com" not in res_u.lower():
                source_url = res_u
                work["link"] = res_u
                try:
                    from nepal_news_store import update_article_link
                    update_article_link(
                        old_link=item.get("link", ""),
                        new_link=res_u,
                        canonical_id=work.get("canonical_id", ""),
                    )
                except Exception:
                    pass
        except Exception:
            pass

    raw_title = (work.get("title") or "").strip()
    lang_code = detect_text_language(
        raw_title + " " + (work.get("summary") or ""),
        declared_lang=work.get("language", ""),
    )

    _emit_progress(on_progress, "Checking stored article text…", 0.15)
    try:
        from nepal_news_store import hydrate_article_full_content
        hydrate_article_full_content(work)
    except Exception:
        pass

    if _needs_body_scrape(work) and source_url.startswith("http"):
        _emit_progress(on_progress, "Fetching full article from publisher…", 0.35)
        try:
            from nepal_fetcher import extract_article_full_text
            fetched = extract_article_full_text(source_url, timeout=6)
            if fetched and len(fetched) > len((work.get("full_content") or "").strip()):
                work["full_content"] = fetched
        except Exception:
            pass

    full_body = (work.get("full_content") or "").strip()
    raw_summary = (work.get("summary") or "").strip()
    source_text = full_body if len(full_body) >= len(raw_summary) else raw_summary
    if not source_text:
        source_text = raw_title

    if lang_code != "en":
        _emit_progress(on_progress, "Translating key facts to English…", 0.6)
    else:
        _emit_progress(on_progress, "Extracting key facts…", 0.6)

    existing_en_title = (work.get("headline_english") or "").strip()
    if existing_en_title and not _has_devanagari(existing_en_title):
        headline_en = normalize_english_proper_nouns(existing_en_title)
    elif lang_code != "en" or _has_devanagari(raw_title):
        title_src_lang = detect_text_language(raw_title, declared_lang=work.get("language", ""))
        headline_en = _translate_ne_to_en(
            raw_title,
            source_lang=title_src_lang if title_src_lang != "en" else lang_code,
            force_translate=True,
        )
    else:
        headline_en = normalize_english_proper_nouns(raw_title)

    headline_en = re.sub(r"\s+", " ", (headline_en or "").strip())

    if _has_devanagari(source_text) or lang_code in ("ne", "hi", "auto"):
        if _has_devanagari(source_text):
            compact_native = _extract_native_salient_sentences(raw_title, source_text, max_sentences=2)
            if not compact_native:
                compact_native = raw_title
            english_body = _translate_ne_to_en(compact_native, source_lang=lang_code, force_translate=True)
        else:
            english_body = normalize_english_proper_nouns(source_text)
    else:
        english_body = normalize_english_proper_nouns(source_text)

    if _has_devanagari(english_body) or (_has_devanagari(raw_title) and _has_devanagari(headline_en)):
        return {
            "ok": False,
            "error": "Translation service temporarily unavailable. Please try again.",
            "headline_english": "",
            "content": "",
            "source_url": source_url,
            "formatted_text": "",
            "lang": lang_code,
        }

    _emit_progress(on_progress, "Formatting concise English Brief…", 0.88)
    brief = generate_lexrank_english_summary(
        title=headline_en or raw_title,
        full_text=english_body,
        max_sentences=2,
        max_chars=450,
    )
    if not brief:
        brief = headline_en or raw_title

    _emit_progress(on_progress, "Ready", 1.0)
    final_headline = headline_en or normalize_english_proper_nouns(raw_title)
    formatted = format_english_brief_payload(
        headline=final_headline,
        brief=brief,
        source_url=source_url,
        whatsapp_bold=True,
    )
    return {
        "ok": True,
        "error": "",
        "headline_english": final_headline,
        "content": brief,
        "source_url": source_url,
        "formatted_text": formatted,
        "lang": lang_code,
    }


_GENERIC_X_ROLES = {"public figure", "account", "nepal live voice", "public x voice", "verified account", "x account"}
_WIRE_PROFILE_FALLBACKS = {
    "ani": "Indian News Agency (Asian News International)",
    "ani_digital": "Indian News Agency Digital Desk (ANI)",
    "pti_news": "Press Trust of India News Agency",
    "alarabiya_eng": "International News Network (Al Arabiya English)",
    "wionews": "International News Network (WION)",
    "reuters": "International News Agency (Reuters)",
    "bbcworld": "International Broadcaster (BBC World News)",
    "afp": "International News Agency (AFP)",
}


def _build_x_profile_line(post: Dict[str, Any]) -> str:
    """Builds a concise one-line X account profile brief from Supabase x_accounts, directory, or post metadata."""
    raw_h = (post.get("raw_handle") or post.get("handle") or "").lstrip("@").split(" ")[0].strip()
    h_low = raw_h.lower()
    author_name = (post.get("author_name") or "").strip()
    role = (post.get("profile_brief") or post.get("role") or "").strip()
    if role.lower() in _GENERIC_X_ROLES:
        role = ""

    if not role and h_low:
        try:
            from nepal_verified_x_directory import DIRECTORY_BY_HANDLE
            acc = DIRECTORY_BY_HANDLE.get(h_low)
            if acc:
                role = (acc.get("role") or acc.get("category") or "").strip()
                if not author_name:
                    author_name = (acc.get("name") or "").strip()
        except Exception:
            pass

    if not role and h_low:
        try:
            from nepal_news_store import get_x_profile_brief_map
            db_acc = get_x_profile_brief_map().get(h_low)
            if db_acc:
                role = (db_acc.get("profile_brief") or "").strip()
                if not author_name:
                    author_name = (db_acc.get("name") or "").strip()
        except Exception:
            pass

    if not role and h_low in _WIRE_PROFILE_FALLBACKS:
        role = _WIRE_PROFILE_FALLBACKS[h_low]

    if not role:
        at_val = (post.get("author_type") or "").strip()
        if at_val.lower() not in _GENERIC_X_ROLES:
            role = at_val

    who = f"{author_name} (@{raw_h})" if (author_name and raw_h) else (author_name or (f"@{raw_h}" if raw_h else ""))
    if who and role:
        return f"Profile: {who} — {role}"
    if who:
        return f"Profile: {who}"
    return ""


def generate_on_demand_x_content(
    post: Dict[str, Any],
    on_progress: Optional[Callable[[str, float], None]] = None,
) -> Dict[str, Any]:
    """
    On-demand user-initiated X post processor.
    - English X posts: returns the complete original post text untouched (no summarization/rewriting).
    - Non-English X posts (Nepali, Hindi, etc.): translates the complete post preserving line breaks and tone.
    """
    raw_text = (post.get("text") or post.get("title") or "").strip()
    source_url = (post.get("link") or "").strip()
    if not source_url:
        raw_h = (post.get("raw_handle") or post.get("handle") or "").lstrip("@").strip()
        sid = str(post.get("id") or "").strip()
        if raw_h and sid:
            source_url = f"https://x.com/{raw_h}/status/{sid}"

    lang_code = detect_text_language(raw_text)
    if lang_code == "en":
        _emit_progress(on_progress, "Retrieving complete English X post…", 0.7)
        content = raw_text
    else:
        _emit_progress(on_progress, "Translating X post to English…", 0.35)
        # Translate line-by-line preserving original paragraph & line-break structure
        lines = raw_text.splitlines()
        translated_lines: List[str] = []
        total_lines = max(1, len(lines))
        for idx, ln in enumerate(lines, start=1):
            stripped = ln.strip()
            if not stripped:
                translated_lines.append("")
                continue
            tr_ln = _translate_ne_to_en(stripped, source_lang=lang_code, force_translate=True)
            translated_lines.append(tr_ln)
            _emit_progress(on_progress, f"Translating line {idx} of {total_lines}…", 0.35 + 0.55 * (idx / total_lines))
        content = "\n".join(translated_lines).strip()
        if not content or (_has_devanagari(raw_text) and _has_devanagari(content)):
            return {
                "ok": False,
                "error": "Translation service temporarily unavailable. Please try again.",
                "content": "",
                "source_url": source_url,
                "formatted_text": "",
                "lang": lang_code,
            }

    _emit_progress(on_progress, "Ready", 1.0)
    profile_line = _build_x_profile_line(post)
    parts = [content]
    if profile_line:
        parts.append(f"_{profile_line}_")
    if source_url:
        parts.append(f"Read Original Source: {source_url}")
    formatted = "\n\n".join(parts)
    return {
        "ok": True,
        "error": "",
        "content": content,
        "profile_line": profile_line,
        "source_url": source_url,
        "formatted_text": formatted,
        "lang": lang_code,
    }


def extract_on_demand_full_article(
    item: Dict[str, Any],
    translate_to_english: bool = False,
    on_progress: Optional[Callable[[str, float], None]] = None,
) -> Dict[str, Any]:
    """
    On-demand full article text extractor with optional complete English translation.
    Hydrates from Supabase first, scrapes the source URL if missing/truncated, and
    preserves clean paragraph structure without altering the original feed record.
    """
    work = dict(item)
    source_url = (work.get("link") or "").strip()
    if source_url and "news.google.com" in source_url.lower():
        try:
            from nepal_fetcher import resolve_google_news_url
            res_u = resolve_google_news_url(source_url)
            if res_u and "news.google.com" not in res_u.lower():
                source_url = res_u
                work["link"] = res_u
                try:
                    from nepal_news_store import update_article_link
                    update_article_link(
                        old_link=item.get("link", ""),
                        new_link=res_u,
                        canonical_id=work.get("canonical_id", ""),
                    )
                except Exception:
                    pass
        except Exception:
            pass

    raw_title = (work.get("title") or "").strip()

    _emit_progress(on_progress, "Checking stored article content…", 0.15)
    try:
        from nepal_news_store import hydrate_article_full_content
        hydrate_article_full_content(work)
    except Exception:
        pass

    scraped_ok = False
    if _needs_body_scrape(work) and source_url.startswith("http"):
        _emit_progress(on_progress, "Fetching full article from publisher…", 0.4)
        try:
            from nepal_fetcher import extract_article_full_text
            fetched = extract_article_full_text(source_url, timeout=7)
            if fetched and len(fetched) > len((work.get("full_content") or "").strip()):
                work["full_content"] = fetched
                scraped_ok = True
        except Exception:
            pass

    _emit_progress(on_progress, "Formatting paragraphs & detecting language…", 0.6)
    full_body = (work.get("full_content") or "").strip()
    excerpt_body = (work.get("summary") or "").strip()
    raw_body = (full_body or excerpt_body or raw_title or "").strip()
    # Clean paragraph breaks and strip trailing RSS boilerplate without collapsing paragraphs
    paras = []
    for p in re.split(r"\n\s*\n", raw_body.replace("\xa0", " ")):
        cp = re.sub(r"[ \t]+", " ", p).strip()
        cp = _BOILERPLATE_TAIL_RE.sub("", cp).strip()
        if cp and not _STANDALONE_META_PARA_RE.match(cp):
            paras.append(cp)
    original_text = "\n\n".join(paras).strip() or raw_body
    lang_code = detect_text_language(original_text, declared_lang=work.get("language", ""))

    # Distinguish full article extraction from incomplete/fallback excerpt extraction
    if not original_text or original_text == raw_title:
        extraction_status = "failed"
        is_complete = False
    elif scraped_ok or (len(full_body) > len(excerpt_body) + 80 and len(original_text) >= 260):
        extraction_status = "full"
        is_complete = True
    else:
        extraction_status = "partial"
        is_complete = False

    translated_text = ""
    translated_title = ""
    tr_error = ""
    if translate_to_english:
        existing_en_title = (work.get("headline_english") or "").strip()
        if existing_en_title and not _has_devanagari(existing_en_title):
            translated_title = normalize_english_proper_nouns(existing_en_title)
        elif raw_title and (lang_code != "en" or _has_devanagari(raw_title)):
            _emit_progress(on_progress, "Translating headline to English…", 0.18)
            title_lang = detect_text_language(raw_title, declared_lang=work.get("language", ""))
            tr_hl = _translate_ne_to_en(
                raw_title,
                timeout=10,
                source_lang=title_lang if title_lang != "en" else lang_code,
                force_translate=True,
            )
            if tr_hl and not (_has_devanagari(raw_title) and _has_devanagari(tr_hl)):
                translated_title = re.sub(r"\s+", " ", tr_hl).strip()
        elif raw_title:
            translated_title = normalize_english_proper_nouns(raw_title)

        if lang_code == "en" and not _has_devanagari(original_text):
            translated_text = original_text
        else:
            src_paras = [p for p in original_text.split("\n\n") if p.strip()]
            total_p = max(1, len(src_paras))
            tr_paras: List[str] = []
            for idx, p in enumerate(src_paras, start=1):
                _emit_progress(on_progress, f"Translating paragraph {idx} of {total_p}…", 0.22 + 0.73 * (idx / total_p))
                tr_p = _translate_ne_to_en(p, timeout=10, source_lang=lang_code, force_translate=True)
                tr_paras.append(tr_p)
            translated_text = "\n\n".join(tr_paras).strip()
            if not translated_text or (_has_devanagari(original_text) and _has_devanagari(translated_text)):
                translated_text = ""
                tr_error = "Translation service temporarily unavailable. Please try again."

    _emit_progress(on_progress, "Ready", 1.0)
    return {
        "ok": bool(original_text) and extraction_status != "failed",
        "is_complete": is_complete,
        "extraction_status": extraction_status,
        "original_title": raw_title,
        "translated_title": translated_title,
        "original_text": original_text,
        "translated_text": translated_text,
        "lang": lang_code,
        "source_url": source_url,
        "error": tr_error,
    }
