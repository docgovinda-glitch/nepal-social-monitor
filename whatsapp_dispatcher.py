"""
whatsapp_dispatcher.py
----------------------
Deduplication, formatting, and broadcasting engine for WhatsApp Channel and
subscriber distribution across Nepal Media, Indian Media, X (Twitter), and Facebook.
"""

import os
import json
import hashlib
import urllib.parse
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

SENT_CACHE_FILE = os.path.join(os.path.dirname(__file__), "whatsapp_sent_cache.json")
DEFAULT_CHANNEL_URL = "https://whatsapp.com/channel/"  # Replaced dynamically by user's actual channel URL

def load_sent_cache() -> Dict[str, Any]:
    """Loads the persistent set of already-broadcasted items."""
    if os.path.exists(SENT_CACHE_FILE):
        try:
            with open(SENT_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"sent_keys": {}, "history": []}

def save_sent_cache(cache: Dict[str, Any]) -> None:
    """Saves the persistent deduplication cache to disk."""
    try:
        with open(SENT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def get_item_key(item: Dict[str, Any], item_type: str = "article") -> str:
    """Generates a stable, unique hash key for deduplication."""
    if item_type in ("article", "nepali_media", "indian_media"):
        raw = item.get("link") or (item.get("source", "") + "_" + item.get("title", ""))
    elif item_type in ("x", "twitter"):
        raw = item.get("link") or item.get("id") or (item.get("handle", "") + "_" + item.get("text", "")[:80])
    elif item_type in ("fb", "facebook"):
        raw = item.get("fb_link") or item.get("link") or (item.get("author_name", "") + "_" + item.get("text", "")[:80])
    else:
        raw = str(item.get("link", "")) or str(item.get("title", "")) or str(item)

    return hashlib.sha256(raw.strip().encode("utf-8", errors="ignore")).hexdigest()[:24]

def is_item_broadcasted(item: Dict[str, Any], item_type: str = "article") -> bool:
    """Checks if an item was already sent to avoid duplicate broadcasting."""
    cache = load_sent_cache()
    key = get_item_key(item, item_type)
    return key in cache.get("sent_keys", {})

def mark_item_broadcasted(
    item: Dict[str, Any],
    item_type: str = "article",
    channel_name: str = "Official WhatsApp Channel"
) -> bool:
    """Marks an item as sent in the persistent deduplication cache."""
    cache = load_sent_cache()
    if "sent_keys" not in cache:
        cache["sent_keys"] = {}
    if "history" not in cache:
        cache["history"] = []

    key = get_item_key(item, item_type)
    if key in cache["sent_keys"]:
        return False

    title = item.get("title") or item.get("text") or "Untitled"
    source = item.get("source") or item.get("author_name") or item.get("handle") or "Unknown"

    entry = {
        "key": key,
        "type": item_type,
        "title": title[:140],
        "source": source,
        "link": item.get("link") or item.get("fb_link") or "",
        "sent_at": datetime.now().isoformat(),
        "channel": channel_name
    }

    cache["sent_keys"][key] = entry
    cache["history"].insert(0, entry)
    # Keep history bounded to latest 500 records
    cache["history"] = cache["history"][:500]

    save_sent_cache(cache)
    return True

def unmark_item_broadcasted(item: Dict[str, Any], item_type: str = "article") -> bool:
    """Removes an item from the sent cache (allows re-broadcasting)."""
    cache = load_sent_cache()
    key = get_item_key(item, item_type)
    if key in cache.get("sent_keys", {}):
        del cache["sent_keys"][key]
        cache["history"] = [h for h in cache.get("history", []) if h.get("key") != key]
        save_sent_cache(cache)
        return True
    return False

def get_broadcasted_stats() -> Dict[str, Any]:
    """Returns statistics of the broadcast engine."""
    cache = load_sent_cache()
    sent_keys = cache.get("sent_keys", {})
    history = cache.get("history", [])

    by_type = {"article": 0, "x": 0, "fb": 0}
    for item in sent_keys.values():
        t = item.get("type", "article")
        if "indian" in t or "nepali" in t or t == "article":
            by_type["article"] += 1
        elif "x" in t or "twitter" in t:
            by_type["x"] += 1
        elif "fb" in t or "facebook" in t:
            by_type["fb"] += 1

    last_sent = history[0]["sent_at"] if history else None

    return {
        "total_broadcasted": len(sent_keys),
        "by_type": by_type,
        "last_broadcast_at": last_sent,
        "recent_history": history[:15]
    }

def format_whatsapp_message(item: Dict[str, Any], item_type: str = "article") -> str:
    """
    Formats an individual news article, X post, or Facebook post for WhatsApp.
    Uses bold (*text*), clean emoji tagging, and direct links.
    """
    cat = item.get("structured_category", "Others")
    exact_time = item.get("exact_time") or item.get("relative_time") or "Recent"

    if item_type in ("x", "twitter"):
        author = item.get("author_name", "Author")
        handle = item.get("handle", "@user")
        text = (item.get("text") or "").strip()
        link = item.get("link") or "https://x.com"

        msg = (
            f"🐦 *X (Twitter) Alert* · {cat}\n"
            f"👤 *{author}* ({handle})\n"
            f"🕒 _{exact_time}_\n\n"
            f"{text}\n\n"
            f"🔗 *View Post on X:* {link}\n"
            f"🌐 *Nepal Intelligence Monitor*"
        )
        return msg

    elif item_type in ("fb", "facebook"):
        author = item.get("author_name", "Page / Figure")
        feed_type = item.get("feed_type", "Facebook Update")
        text = (item.get("text") or "").strip()
        link = item.get("fb_link") or item.get("link") or "https://facebook.com"

        msg = (
            f"📘 *Facebook Intelligence* · {cat}\n"
            f"👤 *{author}* ({feed_type})\n"
            f"🕒 _{exact_time}_\n\n"
            f"{text}\n\n"
            f"🔗 *View on Facebook:* {link}\n"
            f"🌐 *Nepal Intelligence Monitor*"
        )
        return msg

    else:
        # News Article (Nepali or Indian Press)
        source = item.get("source", "News Source")
        title = (item.get("title") or "").strip()
        summary = (item.get("summary") or "").strip()
        link = item.get("link") or "#"
        is_indian = bool(item.get("language") and item.get("source") in [
            "The Indian Express", "The Hindu", "India Today", "The Tribune", "Business Standard",
            "Financial Express", "Livemint", "Moneycontrol", "ABP Live", "Outlook India",
            "The Quint", "Swarajya", "OneIndia", "NDTV", "Amar Ujala", "Live Hindustan",
            "Jansatta", "Prabhat Khabar"
        ])
        portal_tag = "🇮🇳 *Indian Press on Nepal*" if is_indian else f"📰 *{source}*"

        # Truncate summary if too long for a single WhatsApp snippet
        if summary and summary != title:
            clean_sum = summary[:320] + ("..." if len(summary) > 320 else "")
            body = f"{clean_sum}\n\n"
        else:
            body = ""

        msg = (
            f"{portal_tag} · 📌 *{cat}*\n"
            f"*{title}*\n"
            f"🕒 _{exact_time}_\n\n"
            f"{body}"
            f"🔗 *Full Story:* {link}\n"
            f"🌐 *Nepal Intelligence Monitor*"
        )
        return msg

def generate_whatsapp_share_url(item: Dict[str, Any], item_type: str = "article") -> str:
    """
    Returns a direct universal `https://api.whatsapp.com/send?text=...` URL
    so visitors can 1-click share any individual post to WhatsApp.
    """
    text = format_whatsapp_message(item, item_type)
    encoded = urllib.parse.quote(text)
    return f"https://api.whatsapp.com/send?text={encoded}"
