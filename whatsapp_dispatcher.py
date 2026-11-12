"""
whatsapp_dispatcher.py
----------------------
Deduplication, formatting, and broadcasting engine for WhatsApp Channel and
subscriber distribution across Nepal Media, Indian Media, and X (Twitter).
"""

import os
import json
import hashlib
import urllib.parse
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Comprehensive regex to ensure Indian media coverage is substantially related to Nepal
NEPAL_SUBSTANTIVE_KEYWORDS = re.compile(
    r'\b('
    r'nepal|nepali|nepalese|kathmandu|pokhara|birgunj|biratnagar|everest|sagarmatha|'
    r'kp oli|k\.p\. oli|oli|prachanda|pushpa kamal dahal|deuba|sher bahadur|'
    r'balen|balen shah|rabi lamichhane|kulman|singha durbar|'
    r'indo-nepal|nepal-india|india-nepal|'
    r'kalapani|lipulekh|limpiyadhura|susta|pancheshwar|mahakali|koshi|gandak|'
    r'gorkha|gurkha|madhesh|terai|janakpur|lumbini|buddha was born in nepal|'
    r'1950 treaty|open border|ssb border|cross-border transmission|gorakhpur-butwal|'
    r'arun iii|nepal electricity|power trade agreement|pta|'
    r'नेपाल|काठमांडू|काठमाडौँ|ओली|प्रचण्ड|देउवा|बालेन|मधेस|लिपुलेक|कालापानी|महाकाली|गोरखा'
    r')\b',
    re.IGNORECASE
)

def is_substantially_related_to_nepal(item: Dict[str, Any], threshold: Optional[float] = None) -> bool:
    """
    Evaluates whether an article is substantially related to Nepal,
    including its politics, diplomacy, economy, security, and bilateral relations,
    using contextual AI/semantic relevance classification rather than simple keyword matching.
    """
    effective_threshold = threshold if threshold is not None else float(os.getenv("INDIA_MEDIA_RELEVANCE_THRESHOLD", "0.65"))
    if "nepal_relevance_score" in item and item.get("nepal_relevance_score") is not None:
        return float(item["nepal_relevance_score"]) >= effective_threshold

    try:
        from nepal_fetcher import evaluate_indian_article_nepal_relevance
        res = evaluate_indian_article_nepal_relevance(
            title=str(item.get("title") or ""),
            summary=str(item.get("summary") or ""),
            full_content=str(item.get("full_content") or ""),
            link=str(item.get("link") or ""),
            source=str(item.get("source") or ""),
            threshold=effective_threshold,
        )
        item["nepal_relevance_score"] = res["nepal_relevance_score"]
        item["relevance_status"] = res["relevance_status"]
        item["relevance_reason"] = res["relevance_reason"]
        item["nepal_dimensions"] = res["nepal_dimensions"]
        return bool(res["is_substantive"])
    except Exception:
        title = str(item.get("title") or "")
        summary = str(item.get("summary") or "")
        full_content = str(item.get("full_content") or "")
        link = str(item.get("link") or "").lower()
        text_corpus = f"{title} {summary} {full_content[:1500]} {link}"
        return bool(NEPAL_SUBSTANTIVE_KEYWORDS.search(text_corpus))

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

_MEM_SENT_CACHE: Optional[Dict[str, Any]] = None
_MEM_SENT_MTIME: float = -1.0

def load_sent_cache() -> Dict[str, Any]:
    """Loads the persistent set of already-broadcasted items, with in-memory mtime caching."""
    global _MEM_SENT_CACHE, _MEM_SENT_MTIME
    if os.path.exists(SENT_CACHE_FILE):
        try:
            mtime = os.path.getmtime(SENT_CACHE_FILE)
            if _MEM_SENT_CACHE is not None and mtime == _MEM_SENT_MTIME:
                return _MEM_SENT_CACHE
            with open(SENT_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _MEM_SENT_CACHE = data
                    _MEM_SENT_MTIME = mtime
                    return data
        except Exception:
            pass
    if _MEM_SENT_CACHE is not None:
        return _MEM_SENT_CACHE
    return {"sent_keys": {}, "history": []}

def save_sent_cache(cache: Dict[str, Any]) -> None:
    """Saves the persistent deduplication cache to disk and updates memory cache."""
    global _MEM_SENT_CACHE, _MEM_SENT_MTIME
    try:
        with open(SENT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        _MEM_SENT_CACHE = cache
        if os.path.exists(SENT_CACHE_FILE):
            _MEM_SENT_MTIME = os.path.getmtime(SENT_CACHE_FILE)
    except Exception:
        pass

def get_item_key(item: Dict[str, Any], item_type: str = "article") -> str:
    """Generates a stable, unique hash key for deduplication."""
    if item_type in ("article", "nepali_media", "indian_media"):
        raw = item.get("link") or (item.get("source", "") + "_" + item.get("title", ""))
    elif item_type in ("x", "twitter"):
        raw = item.get("link") or item.get("id") or (item.get("handle", "") + "_" + item.get("text", "")[:80])
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
    channel_name: str = "Official WhatsApp Channel",
    message_id: str = "",
    status: str = "delivered"
) -> bool:
    """
    Marks an item as sent in the persistent deduplication cache,
    tracks per-source delivery distribution metrics, and logs to SQLite audit store.
    """
    cache = load_sent_cache()
    if "sent_keys" not in cache:
        cache["sent_keys"] = {}
    if "history" not in cache:
        cache["history"] = []
    if "source_stats" not in cache:
        cache["source_stats"] = {}

    key = get_item_key(item, item_type)
    if key in cache["sent_keys"]:
        return False

    title = item.get("title") or item.get("text") or "Untitled"
    source = item.get("source") or item.get("author_name") or item.get("handle") or "Unknown"

    # Identify clean stream classification
    if item_type in ("x", "twitter"):
        stream_name = "X (Twitter)"
    elif item.get("portal_category") == "Indian Press" or "Indian" in str(item.get("source_type", "")):
        stream_name = "Indian Media"
    else:
        stream_name = "Nepali Media"

    entry = {
        "key": key,
        "type": item_type,
        "stream": stream_name,
        "title": title[:140],
        "source": source,
        "link": item.get("link") or "",
        "sent_at": datetime.now().isoformat(),
        "channel": channel_name,
        "message_id": message_id,
        "status": status
    }

    cache["sent_keys"][key] = entry
    cache["history"].insert(0, entry)
    # Keep history bounded to latest 500 records
    cache["history"] = cache["history"][:500]

    # Update Source-Wise Distribution Aggregates
    src_stat = cache["source_stats"].get(source, {
        "source": source,
        "stream": stream_name,
        "total_sent": 0,
        "delivered": 0,
        "failed": 0,
        "last_sent_at": None,
        "last_title": ""
    })
    src_stat["total_sent"] = src_stat.get("total_sent", 0) + 1
    if status == "delivered":
        src_stat["delivered"] = src_stat.get("delivered", 0) + 1
    else:
        src_stat["failed"] = src_stat.get("failed", 0) + 1
    src_stat["last_sent_at"] = entry["sent_at"]
    src_stat["last_title"] = title[:100]
    cache["source_stats"][source] = src_stat

    save_sent_cache(cache)

    # Durable audit logging in SQLite store
    try:
        from nepal_news_store import log_broadcast_delivery
        log_broadcast_delivery(
            item_key=key,
            source_name=source,
            stream_type=stream_name,
            title=title,
            link=item.get("link") or "",
            status=status,
            message_id=message_id,
            attempts=1,
            channel_id=channel_name
        )
    except Exception:
        pass

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
    """Returns comprehensive statistics and source-wise delivery metrics."""
    cache = load_sent_cache()
    sent_keys = cache.get("sent_keys", {})
    history = cache.get("history", [])
    source_stats = cache.get("source_stats", {})

    by_type = {"article": 0, "x": 0}
    by_stream = {"nepali_media": 0, "indian_media": 0, "x": 0}

    for item in sent_keys.values():
        t = item.get("type", "article")
        stream = item.get("stream", "")
        if "indian" in t or stream == "Indian Media":
            by_stream["indian_media"] += 1
            by_type["article"] += 1
        elif "x" in t or "twitter" in t or stream == "X (Twitter)":
            by_stream["x"] += 1
            by_type["x"] += 1
        else:
            by_stream["nepali_media"] += 1
            by_type["article"] += 1

    last_sent = history[0]["sent_at"] if history else None

    return {
        "total_broadcasted": len(sent_keys),
        "by_type": by_type,
        "by_stream": by_stream,
        "source_stats": source_stats,
        "last_broadcast_at": last_sent,
        "recent_history": history[:25]
    }

def fetch_article_full_text(url: str, timeout: int = 5) -> str:
    """
    Fetches the unabridged, full article content directly from the publisher's webpage.
    Extracts substantive story paragraphs while filtering out navigation, ads,
    and boilerplate elements.
    """
    if not url or not url.startswith("http"):
        return ""
    try:
        import urllib.request
        import ssl
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button", "figure", "figcaption"]):
            tag.decompose()

        paras = []
        for p in soup.find_all("p"):
            txt = p.get_text(strip=True)
            if len(txt) > 35 and not any(skip in txt.lower() for skip in [
                "cookie", "privacy policy", "all rights reserved", "सर्वाधिकार", "प्रतिलिपि अधिकार", "terms of use",
                "facebook", "twitter", "whatsapp", "viber", "copy link", "download app"
            ]):
                paras.append(txt)

        if paras:
            return "\n\n".join(paras)
    except Exception:
        pass
    return ""

def _is_devanagari(text: str) -> bool:
    import re
    return bool(re.search(r'[\u0900-\u097F]', text or ""))

def format_whatsapp_message(item: Dict[str, Any], item_type: str = "article") -> str:
    """
    Formats an individual news article or X post for WhatsApp.
    Preserves original headlines, post content, source attribution, timestamps, and URLs.
    Fast, direct formatting without AI translation overhead.
    """
    time_str = str(item.get("exact_time") or item.get("relative_time") or "").strip()
    if not time_str and item.get("published_dt"):
        pdt = item["published_dt"]
        if isinstance(pdt, datetime):
            time_str = pdt.strftime("%b %d, %Y · %I:%M %p NPT")
        elif isinstance(pdt, str):
            time_str = pdt

    if item_type in ("x", "twitter"):
        link = item.get("link") or "https://x.com"
        handle = (item.get("handle") or "@user").strip()
        author = (item.get("author_name") or "Author").replace("*", "").strip()
        full_text = (item.get("text") or "").strip()

        if handle and handle in author:
            author_line = f"*{author}*"
        elif handle:
            author_line = f"*{author}* ({handle})"
        else:
            author_line = f"*{author}*"

        meta_parts = ["🐦 X (Twitter)"]
        if time_str:
            meta_parts.append(f"🕒 {time_str}")
        meta_line = " · ".join(meta_parts)

        content_section = full_text
        if len(content_section) > 3400:
            content_section = content_section[:3400] + "\n\n[... Full post continued on X]"

        msg = (
            f"{author_line}\n"
            f"{meta_line}\n\n"
            f"{content_section}\n\n"
            f"🔗 Full Post: {link}"
        )
        return msg

    else:
        # News Article (Nepali Media or Indian Media)
        link = item.get("link") or "#"
        source = item.get("source") or "Nepal News"
        category = str(item.get("structured_category") or item.get("primary_section") or "").strip()

        full_content = (item.get("full_content") or "").strip()
        if len(full_content) < 300 and link and link.startswith("http"):
            fetched_body = fetch_article_full_text(link)
            if fetched_body and len(fetched_body) > len(full_content):
                full_content = fetched_body
                item["full_content"] = full_content

        headline = (item.get("title") or "").replace("*", "").strip()
        title_block = f"*{headline}*"

        meta_parts = [f"📰 {source}"]
        if category and category not in ("Others", "Nepal – Others"):
            meta_parts.append(f"📌 {category}")
        if time_str:
            meta_parts.append(f"🕒 {time_str}")
        meta_line = " · ".join(meta_parts)

        story_body = full_content or item.get("summary") or ""
        story_body = story_body.strip()

        max_body_chars = 3300
        if len(story_body) > max_body_chars:
            cut_idx = story_body[:max_body_chars].rfind("\n\n")
            if cut_idx < 1500:
                cut_idx = story_body[:max_body_chars].rfind(". ")
            if cut_idx < 1500:
                cut_idx = max_body_chars
            story_body = story_body[:cut_idx].strip() + "\n\n[... Full article continued on link]"

        body_section = f"{story_body}\n\n" if story_body else ""

        msg = (
            f"{title_block}\n"
            f"{meta_line}\n\n"
            f"{body_section}"
            f"🔗 Full Story: {link}"
        )
        return msg

def generate_whatsapp_share_url(item: Dict[str, Any], item_type: str = "article") -> str:
    """
    Returns an instantaneous direct universal WhatsApp share link without network calls.
    """
    title = (item.get("title") or item.get("text") or "").strip()
    link = item.get("link") or item.get("fb_link") or ""
    source = item.get("source") or item.get("author_name") or "Nepal Media"
    
    parts = []
    if title:
        parts.append(f"*{title}*")
    if source:
        parts.append(f"📰 {source}")
    if link:
        parts.append(f"🔗 {link}")
    
    encoded = urllib.parse.quote("\n\n".join(parts))
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
    chat_id: str,
    max_retries: int = 3
) -> Tuple[bool, str]:
    """
    Dispatches formatted WhatsApp message via Green-API with automatic retries and delivery tracking.
    chat_id format:
      - Personal number: e.g. "9779812345678@c.us"
      - Group: e.g. "12036304...8@g.us"
      - Channel: e.g. "12036304...8@newsletter"
    """
    import urllib.request
    import urllib.error
    import time

    api_url, id_inst, token = get_green_api_credentials()
    if not id_inst or not token:
        return False, "Green-API credentials not configured"

    wa_text = format_whatsapp_message(item, item_type)
    # WhatsApp text messages support up to 4096 characters; guard against oversized summaries
    if len(wa_text) > 4000:
        wa_text = wa_text[:3990] + "...\n(Read full story via link above)"

    url = f"{api_url}/waInstance{id_inst}/sendMessage/{token}"
    payload = {
        "chatId": chat_id,
        "message": wa_text
    }

    last_error = ""
    for attempt in range(1, max_retries + 1):
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode())
                if "idMessage" in resp_data:
                    return True, resp_data["idMessage"]
                last_error = f"Response missing idMessage: {resp_data}"
        except urllib.error.HTTPError as he:
            last_error = f"HTTP {he.code}: {he.reason}"
            # On 429 (Rate Limit) or 502/503/504 (Gateway temporary errors), use exponential backoff
            if he.code in (429, 500, 502, 503, 504):
                sleep_time = attempt * 3
                time.sleep(sleep_time)
            elif attempt < max_retries:
                time.sleep(attempt * 1.5)
        except Exception as ex:
            last_error = str(ex)
            if attempt < max_retries:
                time.sleep(attempt * 2)

    return False, last_error

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

