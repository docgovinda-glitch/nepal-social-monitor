"""
ai_summarizer.py
----------------
AI summarization and translation disabled per user request to maximize speed
and eliminate Gemini API latency and quota issues.
"""

from typing import Dict, Any

def get_gemini_api_key() -> str:
    return ""

def summarize_and_translate_news(
    title: str,
    content: str,
    source: str = ""
) -> Dict[str, str]:
    """Instant passthrough with zero network latency."""
    return {
        "headline": title,
        "summary": content[:300] if content else title
    }

def translate_tweet(
    author: str,
    handle: str,
    text: str
) -> Dict[str, str]:
    """Instant passthrough with zero network latency."""
    return {
        "author": author,
        "text": text
    }
