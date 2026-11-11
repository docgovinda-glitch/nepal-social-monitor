"""
ai_summarizer.py
----------------
AI-powered summarization and translation module for Nepal Media & Intelligence Monitor.
Uses Google Gemini 2.5 Flash to:
1. Translate Nepali & Hindi news headlines into natural, professional English.
2. Produce a coherent, 2-sentence English executive summary from article content.
3. Condense English news stories into crisp 2-sentence summaries.
4. Translate Nepali & Hindi X (Twitter) posts into clean English.
"""

import os
import re
import time
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

logger = logging.getLogger("ai_summarizer")

def get_gemini_api_key() -> str:
    """Retrieves the Gemini API key, prioritizing project .env / secrets over ambient shell vars."""
    # Check .env file first
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass

    # Check secrets.toml
    secrets_file = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY"):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass

    # Ambient environment variable fallback
    return os.getenv("GEMINI_API_KEY", "").strip()

_CIRCUIT_BREAKER_UNTIL = 0.0
_CIRCUIT_BREAKER_REASON = ""

def _is_devanagari(text: str) -> bool:
    """Checks if text contains Devanagari script (Nepali or Hindi)."""
    return bool(re.search(r'[\u0900-\u097F]', text or ""))

def _call_gemini(prompt: str, api_key: str, max_retries: int = 2) -> Optional[Dict[str, Any]]:
    """Calls Gemini API with JSON response format and retry with backoff, with circuit breaker on quota exhaustion."""
    global _CIRCUIT_BREAKER_UNTIL, _CIRCUIT_BREAKER_REASON

    # If circuit breaker is tripped (e.g. 429 quota exhaustion), skip Gemini immediately
    now = time.time()
    if now < _CIRCUIT_BREAKER_UNTIL:
        return None

    if not api_key:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(raw_text)
        except urllib.error.HTTPError as he:
            if he.code == 429:
                # Quota / rate limit exceeded: trip circuit breaker for 15 minutes and don't retry
                _CIRCUIT_BREAKER_UNTIL = time.time() + 900
                _CIRCUIT_BREAKER_REASON = "429 Quota Exceeded"
                logger.warning("Gemini 429 Quota Exceeded: tripping circuit breaker for 15 mins, using clean text fallback.")
                return None
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
            else:
                logger.warning(f"Gemini call failed after {max_retries} retries: {he}")
                return None
        except Exception as e:
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
            else:
                logger.warning(f"Gemini call failed after {max_retries} retries: {e}")
                return None

def summarize_and_translate_news(
    title: str,
    content: str,
    source: str = ""
) -> Dict[str, str]:
    """
    Summarizes and translates a news article into English.
    Returns:
        {
            "headline": "English Headline",
            "summary": "Crisp 2-sentence English executive summary."
        }
    """
    clean_title = (title or "").strip()
    clean_content = (content or "").strip()
    api_key = get_gemini_api_key()

    if not api_key:
        return {
            "headline": clean_title,
            "summary": clean_content[:320] + ("..." if len(clean_content) > 320 else "")
        }

    is_dev = _is_devanagari(clean_title) or _is_devanagari(clean_content)

    if is_dev:
        prompt = (
            "You are a professional wire editor for a Nepal Intelligence Monitor.\n"
            "Translate this Nepali/Hindi news item into natural, journalistic English.\n"
            "Requirements:\n"
            "1. 'headline': A clear, concise, punchy English headline.\n"
            "2. 'summary': A crisp 2-sentence executive summary in English detailing what happened and key context. Do not use generic filler.\n\n"
            f"Original Title: {clean_title}\n"
            f"Original Content: {clean_content[:1500]}\n\n"
            "Respond ONLY with a JSON object in this exact format:\n"
            "{\n"
            '  "headline": "...",\n'
            '  "summary": "..."\n'
            "}"
        )
    else:
        # Already in English (e.g. Kathmandu Post, Indian Express, The Hindu)
        prompt = (
            "You are a professional wire editor for a Nepal Intelligence Monitor.\n"
            "Review this English news item and produce:\n"
            "1. 'headline': A refined, clean English headline.\n"
            "2. 'summary': A crisp 2-sentence executive summary detailing what happened and key context.\n\n"
            f"Original Title: {clean_title}\n"
            f"Original Content: {clean_content[:1500]}\n\n"
            "Respond ONLY with a JSON object in this exact format:\n"
            "{\n"
            '  "headline": "...",\n'
            '  "summary": "..."\n'
            "}"
        )

    res = _call_gemini(prompt, api_key)
    if res and isinstance(res, dict):
        headline = res.get("headline", "").strip() or clean_title
        summary = res.get("summary", "").strip()
        return {"headline": headline, "summary": summary}

    # Fallback to original content
    return {
        "headline": clean_title,
        "summary": clean_content[:320] + ("..." if len(clean_content) > 320 else "")
    }

def translate_tweet(
    author: str,
    handle: str,
    text: str
) -> Dict[str, str]:
    """
    Translates Nepali/Hindi tweets into natural English.
    Returns:
        {
            "author": "Author Name",
            "handle": "@handle",
            "text": "English translation of tweet"
        }
    """
    clean_text = (text or "").strip()
    clean_author = (author or "Author").strip()
    clean_handle = (handle or "@user").strip()

    if not _is_devanagari(clean_text) and not _is_devanagari(clean_author):
        return {"author": clean_author, "handle": clean_handle, "text": clean_text}

    api_key = get_gemini_api_key()
    if not api_key:
        return {"author": clean_author, "handle": clean_handle, "text": clean_text}

    prompt = (
        "You are a translator for a Nepal Intelligence Monitor.\n"
        "Translate this Nepali/Hindi tweet into natural, fluent English.\n"
        f"Author: {clean_author} ({clean_handle})\n"
        f"Tweet Text: {clean_text}\n\n"
        "Respond ONLY with a JSON object in this exact format:\n"
        "{\n"
        '  "author": "...",\n'
        '  "text": "..."\n'
        "}"
    )

    res = _call_gemini(prompt, api_key)
    if res and isinstance(res, dict):
        trans_author = res.get("author", "").strip() or clean_author
        trans_text = res.get("text", "").strip() or clean_text
        return {"author": trans_author, "handle": clean_handle, "text": trans_text}

    return {"author": clean_author, "handle": clean_handle, "text": clean_text}
