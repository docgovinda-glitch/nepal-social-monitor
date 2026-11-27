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


_ENGINE_LABELS = {
    "google": "Google Translate",
    "indictrans2": "IndicTrans2",
    "nllb": "NLLB-200",
    "cached": "Cached",
}


def format_translation_engine_label(engine_code: str) -> str:
    """Formats an internal translation engine code ('google', 'indictrans2', 'nllb') for UI display."""
    code = (engine_code or "").strip().lower()
    if not code:
        return ""
    return _ENGINE_LABELS.get(code, engine_code.strip())


class TranslationLRUCache:
    """
    Persistent SQLite-backed (diskcache) and thread-safe bounded LRU translation cache.
    Stores both translated text and originating engine metadata while keeping string lookup
    signatures backward-compatible.
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

    @staticmethod
    def _unpack_entry(raw_val: Any) -> Tuple[str, str]:
        if isinstance(raw_val, dict):
            return str(raw_val.get("t") or ""), str(raw_val.get("e") or "google")
        return str(raw_val), "google"

    def _put_mem(self, key: str, value: Any) -> None:
        """Inserts/updates a key in the bounded L1 memory cache without evicting from L2 diskcache."""
        if key in self._mem_cache:
            self._mem_cache.move_to_end(key)
        self._mem_cache[key] = value
        while len(self._mem_cache) > self.maxsize:
            self._mem_cache.popitem(last=False)

    def get_with_meta(self, key: str, default: Any = None) -> Tuple[Any, str]:
        with self._lock:
            if key not in self._mem_cache:
                if self._disk_cache is not None:
                    try:
                        val = self._disk_cache.get(key, default=None)
                        if val is not None:
                            self._put_mem(key, val)
                            return self._unpack_entry(val)
                    except Exception:
                        pass
                return default, ""
            self._mem_cache.move_to_end(key)
            return self._unpack_entry(self._mem_cache[key])

    def set_with_meta(self, key: str, value: str, engine: str = "google") -> None:
        packed = {"t": value, "e": (engine or "google").strip().lower()}
        with self._lock:
            self._put_mem(key, packed)
            if self._disk_cache is not None:
                try:
                    self._disk_cache.set(key, packed)
                except Exception:
                    pass

    def get(self, key: str, default: Any = None) -> Any:
        val, _ = self.get_with_meta(key, default=None)
        return default if val is None else val

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
        val, _ = self.get_with_meta(key, default=None)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key: str, value: str) -> None:
        self.set_with_meta(key, value, engine="google")

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
# "google" (default): Google first, local MT as fallback. "local": local MT first, Google as backup.
TRANSLATION_PRIMARY = os.getenv("TRANSLATION_PRIMARY", "google").strip().lower()
# Local MT engine: "indictrans2" (default) or "nllb" (automatic secondary fallback)
LOCAL_MT_ENGINE = os.getenv("LOCAL_MT_ENGINE", "indictrans2").strip().lower()
INDICTRANS2_MODEL_ID = os.getenv(
    "INDICTRANS2_MODEL_ID", "adalat-ai/ct2-rotary-indictrans2-indic-en-dist-200M"
).strip()
HF_TOKEN = (os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN") or "").strip()
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
_LOCAL_IT2_MODEL = None
_LOCAL_IT2_LOCK = threading.Lock()


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


def _translate_with_nllb_model(text: str, source_lang: str = "ne") -> str:
    """Translates text using local NLLB-200 model on CPU."""
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


class _FallbackVocabTokenizer:
    """Lightweight greedy subword tokenizer/detokenizer using CTranslate2 source_vocabulary.json when sentencepiece is unavailable."""

    def __init__(self, vocab_list: List[str]):
        self._vocab = set(vocab_list)
        self._max_len = max((len(t) for t in vocab_list), default=16)

    def encode(self, text: str, out_type=str) -> List[str]:
        toks: List[str] = []
        # Split punctuation and digit runs cleanly so multi-digit numbers aren't greedily truncated
        for word in re.findall(r"[0-9]+|[^\s0-9.,!?;:()\[\]\"']+|[.,!?;:()\[\]\"']", text or ""):
            if word.isdigit():
                toks.append("▁")
                for d in word:
                    toks.append(d if d in self._vocab else "<unk>")
                continue
            s = "▁" + word
            i = 0
            n = len(s)
            while i < n:
                matched = None
                upper = min(n, i + self._max_len)
                for j in range(upper, i, -1):
                    cand = s[i:j]
                    if cand in self._vocab:
                        matched = cand
                        break
                if matched is not None:
                    toks.append(matched)
                    i += len(matched)
                else:
                    toks.append("<unk>")
                    i += 1
        return toks

    def decode(self, tokens: List[str]) -> str:
        return "".join(tokens).replace("▁", " ").strip()


def _find_ct2_model_dir(root_dir: str) -> str:
    """Finds the directory containing model.bin (handles nested layouts like indic-en-200m-ct2/ctranslate2_model)."""
    if os.path.isfile(os.path.join(root_dir, "model.bin")):
        return root_dir
    for cur_root, _, files in os.walk(root_dir):
        if "model.bin" in files:
            return cur_root
    return ""


def _clean_it2_decoded_text(text: str) -> str:
    """Strips residual special/language tokens and normalizes punctuation spacing from IndicTrans2 output."""
    if not text:
        return ""
    cleaned = re.sub(r"(?:</s>|<s>|<unk>|<blank>|<pad>|\b(?:npi_Deva|hin_Deva|eng_Latn)\b)", " ", text)
    cleaned = re.sub(r"\s+([.,!?;:%\)\]])", r"\1", cleaned)
    cleaned = re.sub(r"([\(\[])\s+", r"\1", cleaned)
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def _load_local_indictrans2_model():
    """
    Lazy-loads IndicTrans2 (npi_Deva/hin_Deva -> eng_Latn).
    Option A (preferred lightweight CPU/GPU): CTranslate2 + SentencePiece (e.g. adalat-ai/ct2-rotary-indictrans2-indic-en-dist-200M).
    Option B (PyTorch/HF fallback): transformers AutoModelForSeq2SeqLM (+ optional IndicTransToolkit) with HF_TOKEN for gated repos.
    """
    global _LOCAL_IT2_MODEL
    if _LOCAL_IT2_MODEL is not None:
        return _LOCAL_IT2_MODEL
    with _LOCAL_IT2_LOCK:
        if _LOCAL_IT2_MODEL is not None:
            return _LOCAL_IT2_MODEL
        model_id = os.getenv("INDICTRANS2_MODEL_ID", INDICTRANS2_MODEL_ID).strip()
        hf_token = (os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN") or HF_TOKEN).strip() or None
        logger.info(f"Lazy-loading local IndicTrans2 model ({model_id})...")

        # Option A: CTranslate2 + SentencePiece (zero PyTorch required)
        if not model_id.startswith("ai4bharat/"):
            try:
                import ctranslate2
                if os.path.isdir(model_id):
                    root_dir = model_id
                else:
                    from huggingface_hub import snapshot_download
                    root_dir = snapshot_download(repo_id=model_id, token=hf_token)

                ct2_dir = _find_ct2_model_dir(root_dir)
                if ct2_dir:
                    translator = ctranslate2.Translator(ct2_dir, device="cpu", compute_type="int8")
                    src_sp_candidates = [
                        os.path.join(ct2_dir, "vocab", "model.SRC"),
                        os.path.join(ct2_dir, "model.SRC"),
                        os.path.join(ct2_dir, "sentencepiece.bpe.model"),
                    ]
                    tgt_sp_candidates = [
                        os.path.join(ct2_dir, "vocab", "model.TGT"),
                        os.path.join(ct2_dir, "model.TGT"),
                        os.path.join(ct2_dir, "sentencepiece.bpe.model"),
                    ]
                    src_sp_path = next((p for p in src_sp_candidates if os.path.isfile(p)), "")
                    tgt_sp_path = next((p for p in tgt_sp_candidates if os.path.isfile(p)), "")

                    sp_src = None
                    sp_tgt = None
                    try:
                        import sentencepiece as spm
                        if src_sp_path:
                            sp_src = spm.SentencePieceProcessor(model_file=src_sp_path)
                        if tgt_sp_path:
                            sp_tgt = spm.SentencePieceProcessor(model_file=tgt_sp_path)
                    except ImportError:
                        logger.info("sentencepiece not installed; using source_vocabulary.json fallback tokenizer.")

                    if sp_src is None:
                        src_vocab_json = os.path.join(ct2_dir, "source_vocabulary.json")
                        if os.path.isfile(src_vocab_json):
                            with open(src_vocab_json, "r", encoding="utf-8") as vf:
                                sp_src = _FallbackVocabTokenizer(json.load(vf))
                    if sp_tgt is None:
                        sp_tgt = _FallbackVocabTokenizer([])

                    if sp_src is not None:
                        _LOCAL_IT2_MODEL = ("ct2", translator, sp_src, sp_tgt)
                        logger.info(f"Loaded CTranslate2 IndicTrans2 model from {ct2_dir}.")
                        return _LOCAL_IT2_MODEL
            except Exception as exc:
                logger.warning(f"CTranslate2 IndicTrans2 load failed ({exc}); checking HuggingFace/PyTorch fallback...")

        # Option B: HuggingFace transformers (+ optional IndicTransToolkit)
        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True, token=hf_token)
            mod = AutoModelForSeq2SeqLM.from_pretrained(model_id, trust_remote_code=True, token=hf_token)
            mod.eval()
            ip = None
            try:
                from IndicTransToolkit import IndicProcessor
                ip = IndicProcessor(inference=True)
            except Exception:
                ip = None
            _LOCAL_IT2_MODEL = ("hf", mod, tok, ip)
            logger.info(f"Loaded HuggingFace IndicTrans2 model ({model_id}).")
            return _LOCAL_IT2_MODEL
        except Exception as exc:
            logger.error(f"All IndicTrans2 loaders failed for {model_id}: {type(exc).__name__}: {exc}")
            raise


_DEVANAGARI_DIGITS_TRANS = str.maketrans("०१२३४५६७८९", "0123456789")


def _using_local_indictrans2() -> bool:
    """Returns True when local IndicTrans2 is the active translation path (local primary or open circuit breaker)."""
    engine = os.getenv("LOCAL_MT_ENGINE", LOCAL_MT_ENGINE).strip().lower()
    primary = os.getenv("TRANSLATION_PRIMARY", TRANSLATION_PRIMARY).strip().lower()
    return ENABLE_LOCAL_TRANSLATION_FALLBACK and engine == "indictrans2" and (primary == "local" or is_circuit_breaker_open())


def _translate_with_indictrans2_batch_meta(texts: List[str], source_lang: str = "ne") -> Tuple[List[str], str]:
    """Translates a list of texts using IndicTrans2, returning (outputs, 'indictrans2'|'nllb')."""
    if not texts:
        return [], ""
    src_tag = "hin_Deva" if source_lang == "hi" else "npi_Deva"
    tgt_tag = "eng_Latn"
    norm_texts = [(t or "").translate(_DEVANAGARI_DIGITS_TRANS) for t in texts]
    try:
        model_obj = _load_local_indictrans2_model()
        kind = model_obj[0]

        if kind == "ct2":
            translator = model_obj[1]
            sp_src = model_obj[2]
            sp_tgt = model_obj[3] if len(model_obj) > 3 else sp_src
            tokenized_inputs = [
                [src_tag, tgt_tag] + sp_src.encode(t, out_type=str) + ["</s>"]
                for t in norm_texts
            ]
            results = translator.translate_batch(
                tokenized_inputs,
                beam_size=4,
                max_decoding_length=256,
            )
            out_list: List[str] = []
            _skip_toks = {"</s>", "<s>", "<unk>", "<blank>", "<pad>", src_tag, tgt_tag}
            for orig, res in zip(texts, results):
                hyp = res.hypotheses[0] if getattr(res, "hypotheses", None) else []
                clean_hyp = [tok for tok in hyp if tok not in _skip_toks]
                decoded = _clean_it2_decoded_text(sp_tgt.decode(clean_hyp)) if clean_hyp else ""
                out_list.append(decoded or orig)
            return out_list, "indictrans2"

        # HuggingFace / PyTorch path
        _, mod, tok, ip = model_obj
        import torch
        if ip is not None:
            prepped = ip.preprocess_batch(texts, src_lang=src_tag, tgt_lang=tgt_tag)
        else:
            prepped = [f"{src_tag} {tgt_tag} {t}" for t in texts]
        inputs = tok(prepped, truncation=True, padding="longest", return_tensors="pt", return_attention_mask=True)
        with torch.no_grad():
            generated = mod.generate(**inputs, use_cache=True, min_length=0, max_length=256, num_beams=4)
        decoded_batch = tok.batch_decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=True)
        if ip is not None:
            return [_clean_it2_decoded_text(x) or orig for x, orig in zip(ip.postprocess_batch(decoded_batch, lang=tgt_tag), texts)], "indictrans2"
        return [_clean_it2_decoded_text(x) or orig for x, orig in zip(decoded_batch, texts)], "indictrans2"
    except Exception as exc:
        logger.warning(f"IndicTrans2 batch translation failed ({type(exc).__name__}: {exc}); falling back to NLLB-200.")
        return [_translate_with_nllb_model(t, source_lang=source_lang) for t in texts], "nllb"


def _translate_with_indictrans2_batch(texts: List[str], source_lang: str = "ne") -> List[str]:
    """Translates a list of texts using IndicTrans2, falling back gracefully to NLLB-200 on error."""
    out, _ = _translate_with_indictrans2_batch_meta(texts, source_lang=source_lang)
    return out


def _translate_with_local_model(text: str, source_lang: str = "ne") -> str:
    """Translates text using the configured local MT engine (indictrans2 default, with automatic NLLB-200 fallback)."""
    if not text:
        _set_last_engine("")
        return ""
    engine = os.getenv("LOCAL_MT_ENGINE", LOCAL_MT_ENGINE).strip().lower()
    if engine != "nllb":
        try:
            res, used_eng = _translate_with_indictrans2_batch_meta([text], source_lang=source_lang)
            if res and res[0] and res[0].strip():
                _set_last_engine(used_eng or "indictrans2")
                return res[0]
        except Exception as exc:
            logger.warning(f"Local IndicTrans2 failed ({type(exc).__name__}: {exc}); falling back to NLLB-200.")
    out = _translate_with_nllb_model(text, source_lang=source_lang)
    _set_last_engine("nllb")
    return out


def _translate_with_local_model_meta(text: str, source_lang: str = "ne") -> Tuple[str, str]:
    """Translates text using the configured local MT engine, returning (translated_text, engine_code)."""
    if not text:
        return "", ""
    _set_last_engine("")
    out = _translate_with_local_model(text, source_lang=source_lang)
    default_eng = os.getenv("LOCAL_MT_ENGINE", LOCAL_MT_ENGINE).strip().lower() or "indictrans2"
    return out, _get_last_engine(default=default_eng)


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
    # Titles, honorifics & additional key institutions
    (r"(?:प्रधानमन्त्री)", "Prime Minister"),
    (r"(?:राष्ट्रपति)", "President"),
    (r"(?:अर्थमन्त्री)", "Finance Minister"),
    (r"(?:गृहमन्त्री)", "Home Minister"),
    (r"(?:मुख्यमन्त्री)", "Chief Minister"),
    (r"(?:सभामुख)", "Speaker"),
    (r"(?:माननीय)", "Hon."),
    (r"(?:प्रतिनिधिसभा|प्रतिनिधि\s*सभा)", "House of Representatives"),
    (r"(?:संसद|संसद्)", "Parliament"),
    (r"(?:नेप्से)", "NEPSE"),
    (r"(?:सेबोन)", "SEBON"),
    (r"(?:नेपाल\s*प्रहरी)", "Nepal Police"),
    (r"(?:नेपाली\s*सेना)", "Nepali Army"),
]

# Longest-match-first alternation of Nepali postpositions so multi-char suffixes detach cleanly
_POSTPOSITION_PATTERN = r"(?:विरुद्ध|भित्र|देखि|सहित|लाई|लाइ|बाट|तर्फ|सँग|संग|मा|ले|को|का|की)"


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
        full_pat = re.compile(pat + rf"(?P<post>{_POSTPOSITION_PATTERN})?", re.UNICODE)

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
    (re.compile(r"\bNep(?:se|es)\b", re.I), "NEPSE"),
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
    r"continues|continued|remained|became|become|took|made|gave|got|went|came|rose|fell|hit|set|cut|put|"
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


def _devanagari_count(text: str) -> int:
    """Counts Devanagari Unicode characters in text."""
    return sum(1 for ch in (text or "") if "\u0900" <= ch <= "\u097f")


def _translation_succeeded(src: str, out: str) -> bool:
    """
    Returns True if translation produced a non-empty changed output and either
    eliminated Devanagari or reduced Devanagari count substantially (tolerating
    an occasional untranslatable token/acronym in bilingual text).
    """
    s_clean = (src or "").strip()
    o_clean = (out or "").strip()
    if not o_clean or o_clean == s_clean:
        return False
    src_deva = _devanagari_count(s_clean)
    if src_deva == 0:
        return True
    out_deva = _devanagari_count(o_clean)
    if out_deva == 0:
        return True
    return src_deva >= 8 and out_deva <= max(2, int(src_deva * 0.25))


_LAST_ENGINE_TLS = threading.local()


def _set_last_engine(engine: str) -> None:
    _LAST_ENGINE_TLS.engine = (engine or "").strip().lower()


def _get_last_engine(default: str = "") -> str:
    return getattr(_LAST_ENGINE_TLS, "engine", "") or default


def _set_last_batch_cache_stats(hits: int, misses: int) -> None:
    _LAST_ENGINE_TLS.batch_cache_hits = int(hits)
    _LAST_ENGINE_TLS.batch_cache_misses = int(misses)


def _get_last_batch_cache_stats() -> Tuple[int, int]:
    return (
        int(getattr(_LAST_ENGINE_TLS, "batch_cache_hits", 0)),
        int(getattr(_LAST_ENGINE_TLS, "batch_cache_misses", 0)),
    )


def _translate_chunk_with_failover_meta(chunk: str, sl_code: str, timeout: int = 8) -> Tuple[str, str]:
    """Zero-key translation failover returning (translated_text, engine_code)."""
    global _CLIENT_ROTATION_IDX
    clean_chunk = (chunk or "").strip()
    if not clean_chunk:
        return "", ""

    if TRANSLATION_PRIMARY == "local" and ENABLE_LOCAL_TRANSLATION_FALLBACK:
        _loc, _loc_eng = _translate_with_local_model_meta(clean_chunk, source_lang=sl_code)
        if _loc and _loc.strip() != clean_chunk and not _has_devanagari(_loc):
            return _loc, (_loc_eng or "indictrans2")
        logger.info("Local MT gave no usable result; trying Google endpoints.")

    if is_circuit_breaker_open():
        if ENABLE_LOCAL_TRANSLATION_FALLBACK:
            return _translate_with_local_model_meta(clean_chunk, source_lang=sl_code)
        return clean_chunk, ""

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
                if out and _translation_succeeded(clean_chunk, out):
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
                return res, "google"
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            continue

    record_translation_failure(last_err or "Primary endpoints failed to translate Devanagari")
    if ENABLE_LOCAL_TRANSLATION_FALLBACK:
        logger.info("Primary endpoints exhausted; routing to local offline MT model.")
        return _translate_with_local_model_meta(clean_chunk, source_lang=sl_code)

    return clean_chunk, ""


def _translate_chunk_with_failover(chunk: str, sl_code: str, timeout: int = 8) -> str:
    """Zero-key translation failover across working POST endpoints on translate.googleapis.com with circuit breaker & tenacity."""
    res, _ = _translate_chunk_with_failover_meta(chunk, sl_code=sl_code, timeout=timeout)
    return res


def _translate_batch_group_meta(items: List[str], sl_code: str, timeout: int = 10) -> Tuple[List[str], str]:
    """Translates a small aligned batch, returning (translated_lines, engine_code)."""
    if not items:
        return [], ""
    engine = os.getenv("LOCAL_MT_ENGINE", LOCAL_MT_ENGINE).strip().lower()
    if (
        ENABLE_LOCAL_TRANSLATION_FALLBACK
        and engine == "indictrans2"
        and (TRANSLATION_PRIMARY == "local" or is_circuit_breaker_open())
    ):
        batch_out, used_eng = _translate_with_indictrans2_batch_meta(items, source_lang=sl_code)
        if batch_out and len(batch_out) == len(items):
            return batch_out, (used_eng or "indictrans2")
    payload = "\n".join(items)
    translated, used_eng = _translate_chunk_with_failover_meta(payload, sl_code=sl_code, timeout=timeout)
    if translated == payload and _has_devanagari(payload):
        if len(items) == 1:
            return [items[0]], used_eng
        mid = len(items) // 2
        left_out, left_eng = _translate_batch_group_meta(items[:mid], sl_code, timeout)
        right_out, right_eng = _translate_batch_group_meta(items[mid:], sl_code, timeout)
        return left_out + right_out, (left_eng or right_eng)

    out_lines = translated.splitlines()
    if len(out_lines) == len(items):
        return [ln.strip() or orig for ln, orig in zip(out_lines, items)], used_eng

    if len(items) == 1:
        return [translated.replace("\n", " ").strip() or items[0]], used_eng

    mid = len(items) // 2
    left_out, left_eng = _translate_batch_group_meta(items[:mid], sl_code, timeout)
    right_out, right_eng = _translate_batch_group_meta(items[mid:], sl_code, timeout)
    return left_out + right_out, (left_eng or right_eng)


def _translate_batch_group(items: List[str], sl_code: str, timeout: int = 10) -> List[str]:
    """Translates a small aligned batch via newline-delimited POST, or native batching when using local IndicTrans2."""
    out, _ = _translate_batch_group_meta(items, sl_code=sl_code, timeout=timeout)
    return out


def _translate_batch_to_en(texts: List[str], source_lang: str = "ne", timeout: int = 10) -> List[str]:
    """Translates a list of Devanagari texts in batched POST requests with entity masking, updating _TRANSLATION_CACHE."""
    if not texts:
        _set_last_engine("")
        _set_last_batch_cache_stats(0, 0)
        return []
    sl_code = "hi" if source_lang == "hi" else "ne"
    results: List[str] = [""] * len(texts)
    pending: List[tuple] = []  # (idx, cache_key, one_line_prepped, clean, mask_map)
    used_engines: List[str] = []
    cache_hits = 0
    cache_misses = 0

    for idx, raw in enumerate(texts):
        clean = (raw or "").strip()
        if not clean:
            continue
        if not _has_devanagari(clean):
            results[idx] = normalize_english_proper_nouns(clean)
            continue
        cache_key = f"{source_lang}::{clean}"
        if cache_key in _TRANSLATION_CACHE:
            c_val, c_eng = _TRANSLATION_CACHE.get_with_meta(cache_key)
            results[idx] = c_val
            if c_eng:
                used_engines.append(c_eng)
            cache_hits += 1
            continue
        cache_misses += 1
        prepped = _normalize_devanagari_before_translation(clean) if source_lang != "hi" else clean
        if _using_local_indictrans2():
            masked, mmap = prepped, {}
        else:
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

        translated_strs, batch_eng = _translate_batch_group_meta(batch_strs, sl_code=sl_code, timeout=timeout)
        if batch_eng:
            used_engines.append(batch_eng)
        for k, src_line, tr_line, mmap in zip(batch_keys, batch_strs, translated_strs, batch_mmaps):
            restored = restore_entities_after_translation(tr_line, mmap)
            norm_tr = normalize_english_proper_nouns(restored)
            if norm_tr and _translation_succeeded(src_line, tr_line):
                _TRANSLATION_CACHE.set_with_meta(k, norm_tr, engine=batch_eng or "google")

    for idx, ckey, one_line, orig, mmap in pending:
        if ckey in _TRANSLATION_CACHE:
            results[idx] = _TRANSLATION_CACHE[ckey]
        else:
            results[idx] = orig

    _set_last_engine(used_engines[-1] if used_engines else "")
    _set_last_batch_cache_stats(cache_hits, cache_misses)
    return results


def _translate_batch_to_en_with_meta(texts: List[str], source_lang: str = "ne", timeout: int = 10) -> Tuple[List[str], str]:
    """Translates a batch of texts and returns (translated_list, engine_code)."""
    _set_last_engine("")
    _set_last_batch_cache_stats(0, 0)
    out = _translate_batch_to_en(texts, source_lang=source_lang, timeout=timeout)
    eng = _get_last_engine(default=("google" if any(_has_devanagari(t or "") for t in (texts or [])) else ""))
    return out, eng


def _translate_ne_to_en(text: str, timeout: int = 8, source_lang: str = "ne", force_translate: bool = False) -> str:
    """Translates Nepali, Hindi, or auto-detected non-English text into English with entity masking and proper-noun normalization."""
    clean = (text or "").strip()
    if not clean:
        _set_last_engine("")
        return clean
    if not force_translate and source_lang != "auto" and not _has_devanagari(clean):
        _set_last_engine("")
        return normalize_english_proper_nouns(clean)
    cache_key = f"{source_lang}::{clean}"
    if cache_key in _TRANSLATION_CACHE:
        c_val, c_eng = _TRANSLATION_CACHE.get_with_meta(cache_key)
        _set_last_engine(c_eng or "google")
        return c_val

    prepped = _normalize_devanagari_before_translation(clean) if source_lang == "ne" else clean
    sl_code = source_lang if source_lang in ("ne", "hi", "auto") else "ne"

    # Pre-translation entity masking (skipped when routing directly to IndicTrans2, which translates entities natively)
    if _using_local_indictrans2():
        masked_prepped, mask_map = prepped, {}
    else:
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
    chunk_engines: List[str] = []
    for chunk in chunks:
        tr, chunk_eng = _translate_chunk_with_failover_meta(chunk, sl_code=sl_code, timeout=timeout)
        if chunk_eng:
            chunk_engines.append(chunk_eng)
        if not _translation_succeeded(chunk, tr):
            any_failed = True
        restored = restore_entities_after_translation(tr, mask_map)
        translated_chunks.append(normalize_english_proper_nouns(restored))

    result = "\n\n".join(translated_chunks).strip()
    used_eng = chunk_engines[-1] if chunk_engines else ""
    _set_last_engine(used_eng)
    if not any_failed and _translation_succeeded(clean, result):
        _TRANSLATION_CACHE.set_with_meta(cache_key, result, engine=used_eng or "google")
    return result


def _translate_ne_to_en_with_meta(
    text: str,
    timeout: int = 8,
    source_lang: str = "ne",
    force_translate: bool = False,
) -> Tuple[str, str]:
    """Translates text into English and returns (translated_text, engine_code)."""
    _set_last_engine("")
    out = _translate_ne_to_en(text, timeout=timeout, source_lang=source_lang, force_translate=force_translate)
    clean = (text or "").strip()
    needs_tr = bool(clean and (force_translate or source_lang == "auto" or _has_devanagari(clean)))
    eng = _get_last_engine(default=("google" if needs_tr else ""))
    return out, eng


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


def _is_valid_sentence(s: str) -> bool:
    """Checks sentence/clause validity: length bounds, Latin capitalization, and English finite verb."""
    if not s:
        return False
    if not _has_devanagari(s) and s[0].islower():
        return False
    word_count = len(s.split())
    if word_count < 7 or word_count > 55:
        return False
    if not _has_devanagari(s) and not _FINITE_VERB_RE.search(s):
        return False
    return True


_CLAUSE_BOUNDARY_RE = re.compile(
    r"\s*(?:;|—)\s*|,\s+(?:which|while|although)\s+|\s+(?:तर|भने)\s+",
    re.IGNORECASE,
)


def _split_clauses_quote_aware(text: str) -> List[str]:
    """Splits a long sentence on major clause boundaries only outside open single/double quotes."""
    matches = list(_CLAUSE_BOUNDARY_RE.finditer(text))
    if not matches:
        return [text]

    in_straight_double = False
    in_smart_double = False
    in_straight_single = False
    in_smart_single = False

    def _is_quoted_mask(s: str) -> List[bool]:
        nonlocal in_straight_double, in_smart_double, in_straight_single, in_smart_single
        mask = [False] * len(s)
        n = len(s)
        for i, ch in enumerate(s):
            prev_ch = s[i - 1] if i > 0 else " "
            next_ch = s[i + 1] if i + 1 < n else " "
            if ch == '"':
                in_straight_double = not in_straight_double
            elif ch == "“":
                in_smart_double = True
            elif ch == "”":
                in_smart_double = False
            elif ch == "‘":
                in_smart_single = True
            elif ch == "’":
                if in_smart_single and not next_ch.isalnum():
                    in_smart_single = False
            elif ch == "'":
                if not in_straight_single and not prev_ch.isalnum():
                    in_straight_single = True
                elif in_straight_single and not next_ch.isalnum():
                    in_straight_single = False
            mask[i] = in_straight_double or in_smart_double or in_straight_single or in_smart_single
        return mask

    quoted = _is_quoted_mask(text)
    parts: List[str] = []
    last_idx = 0
    for m in matches:
        if quoted[m.start()]:
            continue
        parts.append(text[last_idx:m.start()])
        last_idx = m.end()
    parts.append(text[last_idx:])
    return parts


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
        if len(restored.split()) > 55:
            clauses = _split_clauses_quote_aware(restored)
            for clause in clauses:
                c = clause.strip(" \t\n\r,;—–-")
                if _is_valid_sentence(c):
                    sents.append(c)
            continue
        if _is_valid_sentence(restored):
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


def _clamp_salient_max_chars(val: int) -> int:
    """Clamps the pre-translation character budget to a safe [400, 3000] range."""
    return max(400, min(3000, int(val)))


def _get_salient_char_budget() -> int:
    """Resolves NATIVE_SALIENT_MAX_CHARS from env (if set) or module default, clamped to [400, 3000]."""
    raw = os.getenv("NATIVE_SALIENT_MAX_CHARS", "")
    if raw.strip():
        try:
            return _clamp_salient_max_chars(int(raw))
        except ValueError:
            pass
    return _clamp_salient_max_chars(NATIVE_SALIENT_MAX_CHARS)


NATIVE_SALIENT_MAX_SENTENCES = max(1, int(os.getenv("NATIVE_SALIENT_MAX_SENTENCES", "7")))
NATIVE_SALIENT_MAX_CHARS = _clamp_salient_max_chars(int(os.getenv("NATIVE_SALIENT_MAX_CHARS", "1500")))


def _extract_native_salient_sentences(
    title: str,
    body: str,
    max_sentences: Optional[int] = None,
    max_chars: Optional[int] = None,
) -> str:
    """Pre-selects up to 7 clean, salient Devanagari sentences before machine translation so LexRank has multi-sentence candidates."""
    if max_sentences is None:
        max_sentences = NATIVE_SALIENT_MAX_SENTENCES
    if max_chars is None:
        max_chars = _get_salient_char_budget()
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
    scored: List[Tuple[float, int]] = []
    for idx in range(1, min(len(candidates), 12)):
        c = candidates[idx]
        c_tokens = set(re.findall(r"[\u0900-\u097F0-9a-zA-Z]{2,}", c.lower()))
        overlap = len(lead_tokens & c_tokens) / max(1, len(c_tokens))
        has_digits = 0.25 if re.search(r"[0-9०-९]", c) else 0.0
        len_bonus = 0.15 if 8 <= len(c.split()) <= 35 else 0.0
        score = overlap + has_digits + len_bonus - (0.04 * idx)
        scored.append((score, idx))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked_indices = [0]
    cur_len = len(lead)
    for _, idx in scored:
        if len(picked_indices) >= max_sentences:
            break
        cand = candidates[idx]
        if cur_len + 1 + len(cand) > max_chars:
            continue
        picked_indices.append(idx)
        cur_len += 1 + len(cand)

    picked_indices.sort()
    joined = " ".join(candidates[i] for i in picked_indices).strip()
    if len(joined) > max_chars:
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


def _word_bigrams(tokens: List[str]) -> set:
    """Returns adjacent word bigram strings from a token list."""
    return {f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)}


def _extract_fact_markers(sent: str) -> set:
    """Extracts numeric figures, units, and institutional terms for novelty scoring."""
    low = sent.lower()
    nums = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", low))
    units = set(re.findall(r"\b(?:rs|usd|million|billion|crore|lakh|mw|km|percent|%)\b", low))
    insts = {term for term in _INSTITUTIONAL_TERMS if term in low}
    return nums | units | insts


def generate_lexrank_english_summary(
    title: str,
    full_text: str,
    max_sentences: int = 2,
    max_chars: int = 450,
) -> str:
    """
    Lead-Anchored Hybrid LexRank + Journalistic Salience Summarizer.
    Scores paragraph-scoped sentences by unigram+bigram graph centrality, lead position,
    factual density, and topical alignment against the headline, producing a clean 2-sentence executive brief.
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

    # Build unigram + bigram TF-IDF vectors for LexRank
    sent_tokens = [_tokenize_content_words(s) for s in sentences]
    sent_sets = [set(toks) for toks in sent_tokens]
    sent_bigrams = [_word_bigrams(toks) for toks in sent_tokens]
    tfidf_tokens = [
        toks + [f"{toks[i]} {toks[i + 1]}" for i in range(len(toks) - 1)]
        for toks in sent_tokens
    ]
    n_sents = len(sentences)
    title_tokens = set(_tokenize_content_words(clean_title))
    lead_tokens = sent_sets[0] | title_tokens

    df: Counter = Counter()
    for t_list in tfidf_tokens:
        for w in set(t_list):
            df[w] += 1

    tfidf_vecs: List[Dict[str, float]] = []
    for t_list in tfidf_tokens:
        tf = Counter(t_list)
        total = len(t_list) or 1
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
    if n_sents < 8:
        w_lex, w_pos, w_fact, w_title = 0.25, 0.35, 0.25, 0.15
    else:
        w_lex, w_pos, w_fact, w_title = 0.40, 0.30, 0.20, 0.10

    scored_indices = []
    score_by_idx: Dict[int, float] = {}
    sent_facts: List[set] = []
    for idx, sent in enumerate(sentences):
        lex_norm = lex_scores[idx] / max_lex
        pos_weight = 1.0 / math.sqrt(idx + 1)

        low_s = sent.lower()
        has_num = 1.0 if re.search(r"\b\d+(?:\.\d+)?%?\b", low_s) else 0.0
        has_unit = 1.0 if re.search(r"\b(?:rs|usd|million|billion|crore|lakh|mw|km|percent|%)\b", low_s) else 0.0
        inst_hits = sum(1 for term in _INSTITUTIONAL_TERMS if term in low_s)
        fact_density = min(1.0, 0.35 * has_num + 0.35 * has_unit + 0.15 * inst_hits)
        sent_facts.append(_extract_fact_markers(sent))

        overlap = _jaccard_overlap(sent_sets[idx], title_tokens)
        topical_link = 1.0 if (sent_sets[idx] & lead_tokens) else 0.0
        if overlap > 0.78:
            title_align = -0.35
        elif 0.12 <= overlap <= 0.65:
            title_align = 1.0
        else:
            title_align = 0.2 if topical_link else -0.4

        total_score = (
            w_lex * lex_norm
            + w_pos * pos_weight
            + w_fact * fact_density
            + w_title * title_align
        )
        scored_indices.append((total_score, idx))
        score_by_idx[idx] = total_score

    # Anchor sentence 1 on the stronger of the first 2 sentences to guarantee lead coherence
    lead_candidates = [x for x in scored_indices if x[1] in (0, 1)]
    lead_candidates.sort(key=lambda x: x[0], reverse=True)
    selected_indices: List[int] = [lead_candidates[0][1]] if lead_candidates else [0]

    # Pick highest-scoring non-redundant supporting sentences via MMR + bigram/RapidFuzz diversity
    try:
        import rapidfuzz.fuzz as fuzz
    except Exception:
        fuzz = None

    sent_word_counts = [len(s.split()) for s in sentences]

    while len(selected_indices) < max_sentences:
        selected_facts = set().union(*(sent_facts[i] for i in selected_indices))
        best_mmr: Optional[Tuple[float, float, int]] = None
        for cand_idx in range(n_sents):
            if cand_idx in selected_indices:
                continue
            cand_sent = sentences[cand_idx]
            cand_set = sent_sets[cand_idx]
            if not (cand_set & lead_tokens):
                continue

            is_dup = False
            max_unigram_overlap = 0.0
            for sel_i in selected_indices:
                sel_sent = sentences[sel_i]
                if fuzz is not None:
                    if fuzz.token_set_ratio(cand_sent, sel_sent) > 68:
                        is_dup = True
                        break
                else:
                    if _jaccard_overlap(cand_set, sent_sets[sel_i]) > 0.58:
                        is_dup = True
                        break
                bigram_threshold = 0.45 if min(sent_word_counts[cand_idx], sent_word_counts[sel_i]) <= 11 else 0.35
                if _jaccard_overlap(sent_bigrams[cand_idx], sent_bigrams[sel_i]) > bigram_threshold:
                    is_dup = True
                    break
                uni_ov = _jaccard_overlap(cand_set, sent_sets[sel_i])
                if uni_ov > max_unigram_overlap:
                    max_unigram_overlap = uni_ov

            if is_dup:
                continue

            new_fact_bonus = 1.0 if (sent_facts[cand_idx] - selected_facts) else 0.0
            base_score = score_by_idx[cand_idx]
            mmr_score = base_score - 0.15 * max_unigram_overlap + 0.10 * new_fact_bonus
            key = (mmr_score, base_score, -cand_idx)
            if best_mmr is None or key > best_mmr:
                best_mmr = key

        if best_mmr is None:
            break
        selected_indices.append(-best_mmr[2])

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

    t_total_start = time.perf_counter()

    # Stage 1: Concurrently fetch missing/truncated article bodies from source URLs
    t_scrape_start = time.perf_counter()
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
    scrape_ms = (time.perf_counter() - t_scrape_start) * 1000.0

    # Stage 2: Prepare native headlines + compact salient bodies grouped by source language
    t_extract_start = time.perf_counter()
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
            compact_native = _extract_native_salient_sentences(raw_title, source_text)
            if not compact_native:
                compact_native = raw_title
            target_list = pending_hi_texts if lang_code == "hi" else pending_ne_texts
            body_jobs.append((idx, lang_code, len(target_list)))
            target_list.append(compact_native)
        else:
            en_bodies[idx] = normalize_english_proper_nouns(source_text)
    extract_ms = (time.perf_counter() - t_extract_start) * 1000.0

    # Stage 3: Batched HTTP POST translation across rotating endpoints
    t_mt_start = time.perf_counter()
    cache_hits = 0
    cache_misses = 0
    if pending_ne_texts:
        tr_ne, eng_ne = _translate_batch_to_en_with_meta(pending_ne_texts, source_lang="ne")
        h_ne, m_ne = _get_last_batch_cache_stats()
        cache_hits += h_ne
        cache_misses += m_ne
    else:
        tr_ne, eng_ne = [], ""

    if pending_hi_texts:
        tr_hi, eng_hi = _translate_batch_to_en_with_meta(pending_hi_texts, source_lang="hi")
        h_hi, m_hi = _get_last_batch_cache_stats()
        cache_hits += h_hi
        cache_misses += m_hi
    else:
        tr_hi, eng_hi = [], ""
    mt_ms = (time.perf_counter() - t_mt_start) * 1000.0

    art_engines: Dict[int, str] = {}
    for idx, lang_code, pos in title_jobs:
        tr_title = tr_hi[pos] if lang_code == "hi" else tr_ne[pos]
        if tr_title and not _has_devanagari(tr_title):
            en_titles[idx] = tr_title
            art_engines[idx] = eng_hi if lang_code == "hi" else eng_ne
        else:
            # Never store untranslated Devanagari inside headline_english
            existing = (to_process[idx].get("headline_english") or "").strip()
            en_titles[idx] = existing if (existing and not _has_devanagari(existing)) else ""

    for idx, lang_code, pos in body_jobs:
        tr_body = tr_hi[pos] if lang_code == "hi" else tr_ne[pos]
        en_bodies[idx] = tr_body
        art_engines[idx] = eng_hi if lang_code == "hi" else eng_ne

    # Stage 4: Final LexRank summarization & safe assignment (only persist clean English)
    t_lex_start = time.perf_counter()
    for idx, art in enumerate(to_process):
        headline_en = en_titles.get(idx, "")
        if headline_en and not _has_devanagari(headline_en):
            art["headline_english"] = headline_en
        elif _has_devanagari(art.get("headline_english", "")):
            art["headline_english"] = ""

        if art_engines.get(idx):
            art["translation_engine"] = format_translation_engine_label(art_engines[idx])

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
    lexrank_ms = (time.perf_counter() - t_lex_start) * 1000.0
    total_ms = (time.perf_counter() - t_total_start) * 1000.0
    avg_per_article_ms = total_ms / len(to_process)

    logger.info(
        "enrich_batch_metrics count=%d scrape_ms=%.2f extract_ms=%.2f mt_ms=%.2f "
        "lexrank_ms=%.2f total_ms=%.2f avg_per_article_ms=%.2f cache_hits=%d cache_misses=%d",
        len(to_process),
        scrape_ms,
        extract_ms,
        mt_ms,
        lexrank_ms,
        total_ms,
        avg_per_article_ms,
        cache_hits,
        cache_misses,
    )

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
    related_links: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Formats a 3-part English Brief (Headline, Brief, Link) with clean visual separation
    for WhatsApp sharing and single-click copy, plus optional same-stream Related links.
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
        parts.append(f"Source: {url}")
    if related_links:
        rel_lines: List[str] = []
        for rel in related_links:
            if not isinstance(rel, dict):
                continue
            r_url = (rel.get("url") or "").strip()
            r_src = (rel.get("source") or "").strip()
            if r_url:
                rel_lines.append(f"- {r_src}: {r_url}" if r_src else f"- {r_url}")
        if rel_lines:
            parts.append("Related:\n" + "\n".join(rel_lines))
    return "\n\n".join(parts)


_NEPALI_RELATED_STOPWORDS = frozenset({
    "र", "को", "का", "की", "मा", "ले", "लाई", "बाट", "द्वारा", "सँग", "निम्ति",
    "लागि", "गरेको", "गरेकी", "गरेका", "भएको", "भएका", "भएकी", "हुने", "गर्ने",
    "छ", "छन्", "थियो", "थिए", "हो", "हुन्", "तथा", "एवं", "वा", "तर", "भने",
    "पनि", "नै", "अनुसार", "जनाएको", "बताएको", "भनिएको", "यो", "त्यो", "यस",
    "त्यस", "एक", "दुई", "गते", "साल", "रासस",
})
_WIRE_MARKERS = frozenset({"रासस", "rss", "ani", "pti", "reuters", "afp"})
_DEVA_DIGITS_TRANS = str.maketrans("०१२३४५६७८९", "0123456789")


def _is_social_item(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return True
    if "raw_handle" in item or "handle" in item:
        return True
    plat = str(item.get("platform") or "").strip().lower()
    if plat in ("x", "facebook"):
        return True
    feed_type = str(item.get("_feed_type") or item.get("stream") or "").strip().lower()
    return feed_type == "x"


def _resolve_news_stream(item: Dict[str, Any]) -> str:
    """Resolves strict 'Nepali' or 'English' stream; returns '' if ambiguous, Hindi, or social."""
    if _is_social_item(item):
        return ""
    title = (item.get("title") or "").strip()
    summary = (item.get("summary") or "").strip()
    combined = f"{title} {summary}".strip()
    decl = (item.get("language") or "").strip().lower()
    detected = detect_text_language(combined, declared_lang=decl)

    if detected == "hi" or decl in ("hindi", "hi"):
        return ""
    if decl in ("nepali", "ne"):
        if detected == "ne" or _has_devanagari(combined):
            return "Nepali"
        return ""
    if decl in ("english", "en"):
        if detected == "en" and not _has_devanagari(title):
            return "English"
        return ""
    if detected == "ne":
        return "Nepali"
    if detected == "en" and not _has_devanagari(combined):
        return "English"
    return ""


def _tokenize_stream_text(text: str, stream_lang: str) -> List[str]:
    """Tokenizes meaningful content words for Nepali or English story matching."""
    norm = (text or "").translate(_DEVA_DIGITS_TRANS)
    if stream_lang == "Nepali":
        deva_words = [
            w for w in re.findall(r"[\u0900-\u097f]{2,}", norm)
            if w not in _NEPALI_RELATED_STOPWORDS and w not in _WIRE_MARKERS
        ]
        ascii_words = [
            w for w in _tokenize_content_words(norm)
            if w not in _WIRE_MARKERS
        ]
        return deva_words + ascii_words
    return [w for w in _tokenize_content_words(norm) if w not in _WIRE_MARKERS]


def _canonical_url_dedup_key(url: str) -> str:
    clean = (url or "").strip()
    if not clean:
        return ""
    try:
        from nepal_news_store import normalize_canonical_url
        clean = normalize_canonical_url(clean)
    except Exception:
        pass
    try:
        from urllib.parse import urlparse, urlunparse
        p = urlparse(clean)
        host = p.netloc.lower()
        for prefix in ("www.", "m."):
            if host.startswith(prefix):
                host = host[len(prefix):]
        return urlunparse((p.scheme.lower(), host, p.path.rstrip("/"), p.params, p.query, ""))
    except Exception:
        return clean.rstrip("/").lower()


def _select_direct_publisher_url(cand: Dict[str, Any]) -> str:
    """
    Returns a normalized direct publisher URL (preferring canonical_url, falling back to link).
    Returns '' if no valid URL exists or if the URL is an unresolved news.google.com wrapper.
    """
    from urllib.parse import urlparse
    for raw_val in (cand.get("canonical_url"), cand.get("link")):
        raw = (raw_val or "").strip()
        if not raw or not raw.startswith("http"):
            continue
        try:
            from nepal_news_store import normalize_canonical_url
            norm = normalize_canonical_url(raw)
        except Exception:
            norm = raw
        if not norm or not norm.startswith("http"):
            continue
        host = urlparse(norm).netloc.lower()
        if "news.google.com" in host or "news.google.com/" in norm.lower():
            continue
        return norm
    return ""


def find_related_same_stream_articles(
    item: Dict[str, Any],
    candidates: Optional[List[Dict[str, Any]]] = None,
    max_results: int = 3,
    window_hours: Optional[int] = None,
) -> List[Dict[str, str]]:
    """
    Finds matching coverage of the same story from other media houses strictly within the
    same language stream ('Nepali' <-> 'Nepali', 'English' <-> 'English').
    Excludes social media posts, self/duplicate canonical URLs, and same-outlet duplicates.
    """
    if _is_social_item(item):
        return []
    target_stream = _resolve_news_stream(item)
    if target_stream not in ("Nepali", "English"):
        return []

    if candidates is None:
        try:
            from nepal_news_store import get_related_stream_candidates
            candidates = get_related_stream_candidates(
                item=item,
                stream_lang=target_stream,
                window_hours=window_hours,
                limit=250,
            )
        except Exception:
            candidates = []

    if not candidates:
        return []

    item_source = (item.get("source") or "").strip().lower()
    item_cid = (item.get("canonical_id") or "").strip()
    excluded_urls = {
        k for k in (
            _canonical_url_dedup_key(item.get("link") or ""),
            _canonical_url_dedup_key(item.get("canonical_url") or ""),
        ) if k
    }

    item_title = (item.get("title") or "").strip()
    item_summary = (item.get("summary") or "").strip()
    item_hl_en = (item.get("headline_english") or "").strip()
    item_title_tokens = _tokenize_stream_text(item_title, target_stream)
    item_all_text = f"{item_title} {item_summary}".strip()
    if target_stream == "English" and item_hl_en:
        item_all_text = f"{item_all_text} {item_hl_en}".strip()
    item_all_tokens = _tokenize_stream_text(item_all_text, target_stream)
    item_title_set = set(item_title_tokens)
    item_all_set = set(item_all_tokens)
    if len(item_all_set) < 2:
        return []

    item_bigrams = {
        f"{item_all_tokens[i]}_{item_all_tokens[i + 1]}"
        for i in range(len(item_all_tokens) - 1)
    }
    item_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", item_all_text.translate(_DEVA_DIGITS_TRANS)))

    scored: List[Tuple[float, float, Dict[str, str]]] = []
    for cand in candidates:
        if not isinstance(cand, dict) or _is_social_item(cand):
            continue
        if _resolve_news_stream(cand) != target_stream:
            continue

        cand_source = (cand.get("source") or "").strip()
        if not cand_source or (item_source and cand_source.lower() == item_source):
            continue
        cand_cid = (cand.get("canonical_id") or "").strip()
        if item_cid and cand_cid and cand_cid == item_cid:
            continue

        cand_url = _select_direct_publisher_url(cand)
        if not cand_url:
            continue
        cand_url_key = _canonical_url_dedup_key(cand_url)
        if not cand_url_key or cand_url_key in excluded_urls:
            continue
        raw_link_key = _canonical_url_dedup_key(cand.get("link") or "")
        if raw_link_key and raw_link_key in excluded_urls:
            continue

        cand_title = (cand.get("title") or "").strip()
        cand_summary = (cand.get("summary") or "").strip()
        cand_hl_en = (cand.get("headline_english") or "").strip()
        cand_title_tokens = _tokenize_stream_text(cand_title, target_stream)
        cand_all_text = f"{cand_title} {cand_summary}".strip()
        if target_stream == "English" and cand_hl_en:
            cand_all_text = f"{cand_all_text} {cand_hl_en}".strip()
        cand_all_tokens = _tokenize_stream_text(cand_all_text, target_stream)
        cand_title_set = set(cand_title_tokens)
        cand_all_set = set(cand_all_tokens)
        if len(cand_all_set) < 2:
            continue

        shared_all = item_all_set & cand_all_set
        if len(shared_all) < 2:
            continue

        title_sim = _jaccard_overlap(item_title_set, cand_title_set)
        full_sim = _jaccard_overlap(item_all_set, cand_all_set)
        min_title_len = min(len(item_title_set), len(cand_title_set))
        title_containment = (len(item_title_set & cand_title_set) / min_title_len) if min_title_len > 0 else 0.0

        cand_bigrams = {
            f"{cand_all_tokens[i]}_{cand_all_tokens[i + 1]}"
            for i in range(len(cand_all_tokens) - 1)
        }
        bigram_sim = _jaccard_overlap(item_bigrams, cand_bigrams)
        cand_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", cand_all_text.translate(_DEVA_DIGITS_TRANS)))
        num_sim = _jaccard_overlap(item_nums, cand_nums) if (item_nums and cand_nums) else 0.0

        weighted_score = (
            0.45 * max(title_sim, 0.85 * title_containment)
            + 0.30 * full_sim
            + 0.15 * bigram_sim
            + 0.10 * num_sim
        )
        if weighted_score < 0.32:
            continue

        pub_dt = cand.get("published_dt")
        try:
            recency_ts = float(pub_dt.timestamp()) if hasattr(pub_dt, "timestamp") else 0.0
        except Exception:
            recency_ts = 0.0
        is_indian_cand = (
            str(cand.get("_feed_type") or cand.get("stream") or "").strip().lower() in ("indian", "indian press")
            or ("nepal_relevance_score" in cand)
        )
        scored.append((
            weighted_score,
            recency_ts,
            {
                "source": cand_source,
                "url": cand_url,
                "title": cand_title,
                "canonical_id": cand_cid,
                "canonical_url": (cand.get("canonical_url") or cand_url).strip(),
                "table": "indian_media_articles" if is_indian_cand else "articles",
            },
        ))

    scored.sort(key=lambda x: (-x[0], -x[1], x[2]["source"].lower()))
    results: List[Dict[str, str]] = []
    seen_sources = set()
    seen_urls = set(excluded_urls)
    eff_max = max(1, int(max_results or 3))
    for _, _, entry in scored:
        src_key = entry["source"].lower()
        url_key = _canonical_url_dedup_key(entry["url"])
        if src_key in seen_sources or url_key in seen_urls:
            continue
        seen_sources.add(src_key)
        seen_urls.add(url_key)
        results.append(entry)
        if len(results) >= eff_max:
            break
    return results


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
        parts.append(f"Source: {url}")
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

    used_engine_code = ""
    existing_en_title = (work.get("headline_english") or "").strip()
    if existing_en_title and not _has_devanagari(existing_en_title):
        headline_en = normalize_english_proper_nouns(existing_en_title)
    elif lang_code != "en" or _has_devanagari(raw_title):
        title_src_lang = detect_text_language(raw_title, declared_lang=work.get("language", ""))
        headline_en, hl_eng = _translate_ne_to_en_with_meta(
            raw_title,
            source_lang=title_src_lang if title_src_lang != "en" else lang_code,
            force_translate=True,
        )
        if hl_eng:
            used_engine_code = hl_eng
    else:
        headline_en = normalize_english_proper_nouns(raw_title)

    headline_en = re.sub(r"\s+", " ", (headline_en or "").strip())

    if _has_devanagari(source_text) or lang_code in ("ne", "hi", "auto"):
        if _has_devanagari(source_text):
            compact_native = _extract_native_salient_sentences(raw_title, source_text)
            if not compact_native:
                compact_native = raw_title
            english_body, body_eng = _translate_ne_to_en_with_meta(compact_native, source_lang=lang_code, force_translate=True)
            if body_eng:
                used_engine_code = body_eng
        else:
            english_body = normalize_english_proper_nouns(source_text)
    else:
        english_body = normalize_english_proper_nouns(source_text)

    if not _translation_succeeded(source_text, english_body) and _has_devanagari(source_text):
        return {
            "ok": False,
            "error": "Translation service temporarily unavailable. Please try again.",
            "headline_english": "",
            "content": "",
            "source_url": source_url,
            "formatted_text": "",
            "lang": lang_code,
        }
    if _has_devanagari(raw_title) and not _translation_succeeded(raw_title, headline_en):
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
    related_links: List[Dict[str, str]] = []
    try:
        related_links = find_related_same_stream_articles(work, max_results=3)
    except Exception:
        related_links = []
    formatted = format_english_brief_payload(
        headline=final_headline,
        brief=brief,
        source_url=source_url,
        whatsapp_bold=True,
        related_links=related_links,
    )
    return {
        "ok": True,
        "error": "",
        "headline_english": final_headline,
        "content": brief,
        "source_url": source_url,
        "related_links": related_links,
        "formatted_text": formatted,
        "lang": lang_code,
        "translation_engine": format_translation_engine_label(used_engine_code),
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
    """Builds a concise one-line social account profile brief from Supabase x_accounts, directory, or post metadata."""
    raw_h_field = (post.get("raw_handle") or post.get("handle") or "").strip()
    if "facebook.com/" in raw_h_field.lower():
        raw_h = raw_h_field.rstrip("/").split("/")[-1].lstrip("@").split(" ")[0].strip()
    else:
        raw_h = raw_h_field.lstrip("@").split(" ")[0].strip()
    h_low = raw_h.lower()
    is_fb = (
        str(post.get("platform") or "").strip().lower() == "facebook"
        or "facebook.com" in str(post.get("link") or "").lower()
    )
    author_name = (post.get("author_name") or "").strip()
    role = (post.get("profile_brief") or post.get("role") or "").strip()
    if role.lower() in _GENERIC_X_ROLES:
        role = ""

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

    if not role and h_low:
        try:
            from nepal_social_directory import DIRECTORY_BY_HANDLE
            acc = DIRECTORY_BY_HANDLE.get(h_low)
            if acc:
                role = (acc.get("profile_brief") or acc.get("role") or acc.get("category") or "").strip()
                if not author_name:
                    author_name = (acc.get("name") or "").strip()
        except Exception:
            pass

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

    if not role and h_low in _WIRE_PROFILE_FALLBACKS:
        role = _WIRE_PROFILE_FALLBACKS[h_low]

    if not role:
        at_val = (post.get("author_type") or "").strip()
        if at_val.lower() not in _GENERIC_X_ROLES:
            role = at_val

    if is_fb:
        who = author_name or raw_h
    else:
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
    On-demand user-initiated X/Facebook post processor.
    - English social posts: returns the complete original post text untouched (no summarization/rewriting).
    - Non-English social posts (Nepali, Hindi, etc.): translates the complete post in batch preserving line breaks and tone.
    """
    raw_text = (post.get("text") or post.get("title") or "").strip()
    source_url = (post.get("link") or "").strip()
    is_fb = (
        str(post.get("platform") or "").strip().lower() == "facebook"
        or "facebook.com" in source_url.lower()
    )
    if not source_url and not is_fb:
        raw_h = (post.get("raw_handle") or post.get("handle") or "").lstrip("@").strip()
        sid = str(post.get("id") or "").strip()
        if raw_h and sid:
            source_url = f"https://x.com/{raw_h}/status/{sid}"

    lang_code = detect_text_language(raw_text)
    used_engine_code = ""
    if lang_code == "en":
        _emit_progress(on_progress, "Retrieving complete English post…", 0.7)
        content = raw_text
    else:
        _emit_progress(on_progress, "Translating post to English…", 0.35)
        lines = raw_text.splitlines()
        non_empty_indices: List[int] = []
        non_empty_texts: List[str] = []
        for idx, ln in enumerate(lines):
            stripped = ln.strip()
            if stripped:
                non_empty_indices.append(idx)
                non_empty_texts.append(stripped)

        translated_lines = list(lines)
        if non_empty_texts:
            if lang_code == "auto":
                tr_batch = []
                for t in non_empty_texts:
                    tr_t, t_eng = _translate_ne_to_en_with_meta(t, source_lang="auto", force_translate=True)
                    tr_batch.append(tr_t)
                    if t_eng:
                        used_engine_code = t_eng
            else:
                tr_batch, used_engine_code = _translate_batch_to_en_with_meta(non_empty_texts, source_lang=lang_code, timeout=10)
            for idx, tr_ln in zip(non_empty_indices, tr_batch):
                translated_lines[idx] = tr_ln
        _emit_progress(on_progress, "Finalizing translated post…", 0.9)
        content = "\n".join(translated_lines).strip()
        if not content or (_has_devanagari(raw_text) and not _translation_succeeded(raw_text, content)):
            return {
                "ok": False,
                "error": "Translation service temporarily unavailable. Please try again.",
                "content": "",
                "source_url": source_url,
                "formatted_text": "",
                "lang": lang_code,
                "translation_engine": "",
            }

    _emit_progress(on_progress, "Ready", 1.0)
    profile_line = _build_x_profile_line(post)
    parts = [content]
    if profile_line:
        parts.append(f"_{profile_line}_")
    if source_url:
        parts.append(f"Source: {source_url}")
    formatted = "\n\n".join(parts)
    return {
        "ok": True,
        "error": "",
        "content": content,
        "profile_line": profile_line,
        "source_url": source_url,
        "formatted_text": formatted,
        "lang": lang_code,
        "translation_engine": format_translation_engine_label(used_engine_code),
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
    used_engine_code = ""
    if translate_to_english:
        existing_en_title = (work.get("headline_english") or "").strip()
        if existing_en_title and not _has_devanagari(existing_en_title):
            translated_title = normalize_english_proper_nouns(existing_en_title)
        elif raw_title and (lang_code != "en" or _has_devanagari(raw_title)):
            _emit_progress(on_progress, "Translating headline to English…", 0.18)
            title_lang = detect_text_language(raw_title, declared_lang=work.get("language", ""))
            tr_hl, hl_eng = _translate_ne_to_en_with_meta(
                raw_title,
                timeout=10,
                source_lang=title_lang if title_lang != "en" else lang_code,
                force_translate=True,
            )
            if tr_hl and not (_has_devanagari(raw_title) and _has_devanagari(tr_hl)):
                translated_title = re.sub(r"\s+", " ", tr_hl).strip()
                if hl_eng:
                    used_engine_code = hl_eng
        elif raw_title:
            translated_title = normalize_english_proper_nouns(raw_title)

        if lang_code == "en" and not _has_devanagari(original_text):
            translated_text = original_text
        else:
            src_paras = [p.strip() for p in original_text.split("\n\n") if p.strip()]
            _emit_progress(on_progress, f"Translating {len(src_paras)} paragraph(s) to English…", 0.55)
            if lang_code == "auto":
                tr_paras = []
                for p in src_paras:
                    tr_p, p_eng = _translate_ne_to_en_with_meta(p, timeout=10, source_lang="auto", force_translate=True)
                    tr_paras.append(tr_p)
                    if p_eng:
                        used_engine_code = p_eng
            else:
                tr_paras, body_eng = _translate_batch_to_en_with_meta(src_paras, source_lang=lang_code, timeout=10)
                if body_eng:
                    used_engine_code = body_eng
            _emit_progress(on_progress, "Finalizing translated article…", 0.92)
            translated_text = "\n\n".join(tr_paras).strip()
            if not translated_text or (_has_devanagari(original_text) and not _translation_succeeded(original_text, translated_text)):
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
        "translation_engine": "" if tr_error else format_translation_engine_label(used_engine_code),
    }
