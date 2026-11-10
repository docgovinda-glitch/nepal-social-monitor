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

try:
    from ai_summarizer import summarize_and_translate_news, translate_tweet
except ImportError:
    summarize_and_translate_news = None
    translate_tweet = None

SENT_CACHE_FILE = os.path.join(os.path.dirname(__file__), "whatsapp_sent_cache.json")

def get_env_variable(key: str, default: str = "") -> str:
    """
    Fetches environment variable from os.environ, falling back to local .env
    and .streamlit/secrets.toml if available.
    """
    val = os.getenv(key, "")
    if val:
        return val.strip()

    # Fallback to local .env file
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{key}="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

    # Fallback to .streamlit/secrets.toml
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{key}") and "=" in line:
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

    return default

DEFAULT_CHANNEL_URL = get_env_variable("WHATSAPP_CHANNEL_URL", "https://whatsapp.com/channel/0029Vb92VH61iUxbhQ4HpB38")

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
    Uses Google Gemini AI to translate Nepali/Hindi to English and write
    crisp 2-sentence executive summaries.
    Produces a clean, uncluttered template: Title -> Summary -> Full Story Link.
    """
    if item_type in ("x", "twitter"):
        if translate_tweet and "ai_text" not in item:
            tr = translate_tweet(
                author=item.get("author_name", ""),
                handle=item.get("handle", ""),
                text=item.get("text", "")
            )
            item["ai_author"] = tr.get("author") or item.get("author_name", "Author")
            item["ai_text"] = tr.get("text") or item.get("text", "")

        author = (item.get("ai_author") or item.get("author_name") or "Author").replace("*", "").strip()
        handle = (item.get("handle") or "@user").strip()
        text = (item.get("ai_text") or item.get("text") or "").strip()
        link = item.get("link") or "https://x.com"

        if handle and handle in author:
            author_line = f"*{author}*"
        elif handle:
            author_line = f"*{author}* ({handle})"
        else:
            author_line = f"*{author}*"

        msg = (
            f"{author_line}\n\n"
            f"{text}\n\n"
            f"🔗 Full Story: {link}"
        )
        return msg

    elif item_type in ("fb", "facebook"):
        author = (item.get("author_name") or "Page").replace("*", "").strip()
        text = (item.get("text") or "").strip()
        link = item.get("fb_link") or item.get("link") or "https://facebook.com"

        msg = (
            f"*{author}*\n\n"
            f"{text}\n\n"
            f"🔗 Full Story: {link}"
        )
        return msg

    else:
        # News Article (Nepali, Indian Press, or English)
        if summarize_and_translate_news and "ai_headline" not in item:
            raw_content = item.get("summary") or item.get("description") or item.get("content") or item.get("title", "")
            ai_res = summarize_and_translate_news(
                title=item.get("title", ""),
                content=raw_content,
                source=item.get("source", "")
            )
            item["ai_headline"] = ai_res.get("headline") or item.get("title", "")
            item["ai_summary"] = ai_res.get("summary") or item.get("summary", "")

        title = (item.get("ai_headline") or item.get("title") or "").replace("*", "").strip()
        summary = (item.get("ai_summary") or item.get("summary") or "").strip()
        link = item.get("link") or "#"

        if summary and summary != title:
            clean_sum = summary[:500] + ("..." if len(summary) > 500 else "")
            body = f"{clean_sum}\n\n"
        else:
            body = ""

        msg = (
            f"*{title}*\n\n"
            f"{body}"
            f"🔗 Full Story: {link}"
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

def dispatch_item_to_webhook(item: Dict[str, Any], item_type: str, webhook_url: str) -> Tuple[bool, str]:
    """
    Sends an individual item payload to the configured webhook (e.g. Make.com, n8n, Zapier).
    Returns (success, message).
    """
    import urllib.request
    import urllib.error

    channel_url = get_env_variable("WHATSAPP_CHANNEL_URL", DEFAULT_CHANNEL_URL)
    channel_id = channel_url.rstrip("/").split("/")[-1] if "/channel/" in channel_url else ""
    wa_text = format_whatsapp_message(item, item_type)

    payload = {
        "event": "new_scanned_item",
        "timestamp": datetime.now().isoformat(),
        "item_type": item_type,
        "title": item.get("title") or item.get("text") or "Untitled",
        "source": item.get("source") or item.get("author_name") or item.get("handle") or "Unknown",
        "category": item.get("structured_category", "Others"),
        "link": item.get("link") or item.get("fb_link") or "",
        "channel_url": channel_url,
        "channel_id": channel_id,
        "whatsapp_text": wa_text
    }

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "NepalMonitor-Dispatcher/1.0"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = resp.getcode()
            if code in (200, 201, 202, 204):
                return True, f"HTTP {code} OK"
            return False, f"Unexpected HTTP status {code}"
    except Exception as ex:
        return False, str(ex)







def send_test_webhook_ping(webhook_url: str) -> Tuple[bool, str]:
    """
    Sends a test verification ping to the webhook endpoint.
    """
    import urllib.request

    channel_url = get_env_variable("WHATSAPP_CHANNEL_URL", DEFAULT_CHANNEL_URL)
    payload = {
        "event": "test_ping",
        "timestamp": datetime.now().isoformat(),
        "channel_url": channel_url,
        "message": "✅ Nepal Media Intelligence Monitor Webhook Connection Verified Successfully!",
        "sample_item": {
            "title": "Prime Minister holds high-level council meeting in Singha Durbar",
            "source": "Ekantipur",
            "category": "Politics & Governance",
            "whatsapp_text": "📰 *Ekantipur* · 📌 *Politics & Governance*\n*Prime Minister holds high-level council meeting in Singha Durbar*\n\n🔗 *Full Story:* https://ekantipur.com\n🌐 *Nepal Intelligence Monitor*"
        }
    }

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "NepalMonitor-TestPing/1.0"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = resp.getcode()
            if code in (200, 201, 202, 204):
                return True, f"Connection verified (HTTP {code})"
            return False, f"HTTP {code}"
    except Exception as ex:
        return False, str(ex)










def get_green_api_credentials() -> Tuple[str, str, str]:
    """Returns (api_url, id_instance, api_token_instance)."""
    api_url = get_env_variable("GREEN_API_URL", "https://7107.api.greenapi.com").rstrip("/")
    id_instance = get_env_variable("GREEN_API_ID_INSTANCE")
    token_instance = get_env_variable("GREEN_API_TOKEN_INSTANCE")
    return api_url, id_instance, token_instance

def get_green_api_status() -> Tuple[str, str]:
    """
    Checks authorization status with Green-API.
    Returns (status_text, qr_code_base64).
    """
    import urllib.request
    api_url, id_inst, token = get_green_api_credentials()
    if not id_inst or not token:
        return "notConfigured", ""

    status = "unknown"
    qr_code = ""

    try:
        st_url = f"{api_url}/waInstance{id_inst}/getStateInstance/{token}"
        with urllib.request.urlopen(st_url, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            status = data.get("stateInstance", "unknown")
    except Exception:
        status = "error"

    if status in ("notAuthorized", "unknown"):
        try:
            qr_url = f"{api_url}/waInstance{id_inst}/qr/{token}"
            with urllib.request.urlopen(qr_url, timeout=8) as resp:
                data = json.loads(resp.read().decode())
                if data.get("type") == "qrCode":
                    qr_code = data.get("message", "")
        except Exception:
            pass

    return status, qr_code

def dispatch_item_to_green_api(
    item: Dict[str, Any],
    item_type: str,
    chat_id: str
) -> Tuple[bool, str]:
    """
    Dispatches formatted WhatsApp message via Green-API.
    chat_id format:
      - Personal number: e.g. "9779812345678@c.us"
      - Group: e.g. "12036304...8@g.us"
      - Channel: e.g. "12036304...8@newsletter"
    """
    import urllib.request
    api_url, id_inst, token = get_green_api_credentials()
    if not id_inst or not token:
        return False, "Green-API credentials not configured"

    wa_text = format_whatsapp_message(item, item_type)
    url = f"{api_url}/waInstance{id_inst}/sendMessage/{token}"
    payload = {
        "chatId": chat_id,
        "message": wa_text
    }

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            resp_data = json.loads(resp.read().decode())
            if "idMessage" in resp_data:
                return True, resp_data["idMessage"]
            return False, str(resp_data)
    except Exception as ex:
        return False, str(ex)

def get_green_api_chats() -> List[Dict[str, Any]]:
    """Fetches list of active chats/groups/channels from authorized Green-API instance."""
    import urllib.request
    api_url, id_inst, token = get_green_api_credentials()
    if not id_inst or not token:
        return []
    url = f"{api_url}/waInstance{id_inst}/getChats/{token}"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

def find_channel_newsletter_id() -> Optional[str]:
    """Scans recent outgoing and incoming messages for WhatsApp channel (@newsletter) IDs."""
    import urllib.request
    api_url, id_inst, token = get_green_api_credentials()
    if not id_inst or not token:
        return None

    for endpoint in ("lastOutgoingMessages", "lastIncomingMessages"):
        url = f"{api_url}/waInstance{id_inst}/{endpoint}/{token}?minutes=1440"
        try:
            with urllib.request.urlopen(url, timeout=6) as resp:
                msgs = json.loads(resp.read().decode())
                for m in msgs:
                    cid = m.get("chatId", "")
                    if cid.endswith("@newsletter"):
                        return cid
        except Exception:
            pass
    return None


def send_test_green_api_message(chat_id: str) -> Tuple[bool, str]:
    """Sends a verification test message to the specified WhatsApp chat ID."""
    test_item = {
        "title": "🇳🇵 Nepal Media & Intelligence Monitor - Direct WhatsApp Gateway Test",
        "source": "Nepal Monitor Core",
        "structured_category": "System Alert",
        "summary": "This is a direct test confirmation from your Nepal Intelligence Monitor. Direct Green-API connection is active and ready for automated broadcasts!",
        "link": get_env_variable("WHATSAPP_CHANNEL_URL", DEFAULT_CHANNEL_URL),
        "exact_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return dispatch_item_to_green_api(test_item, "article", chat_id)

