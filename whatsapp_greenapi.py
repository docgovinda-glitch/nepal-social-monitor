"""
whatsapp_greenapi.py
Server-side Green API integration for WhatsApp group discovery and message sharing.
All credentials remain strictly server-side via environment / Streamlit secrets.
Actual group messaging remains inactive until Green API setup is confirmed and approved.
"""

import hashlib
import logging
import requests
from typing import Dict, Any, List, Optional, Set

from nepal_news_store import get_env_variable

logger = logging.getLogger("whatsapp_greenapi")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _get_green_config() -> Dict[str, str]:
    """Loads Green API configuration strictly server-side."""
    return {
        "api_url": (get_env_variable("GREEN_API_URL") or "").rstrip("/"),
        "id_instance": get_env_variable("GREEN_API_ID_INSTANCE") or "",
        "token_instance": get_env_variable("GREEN_API_TOKEN_INSTANCE") or "",
        "env_chat_id": get_env_variable("GREEN_API_CHAT_ID") or "",
        "sending_enabled_flag": get_env_variable("GREEN_API_SENDING_ENABLED", "").lower(),
    }


def is_configured() -> bool:
    """Returns True if Green API URL, instance ID, and token are present server-side."""
    cfg = _get_green_config()
    return bool(cfg["api_url"] and cfg["id_instance"] and cfg["token_instance"])


def get_env_suggested_chat_id() -> str:
    """Returns the configured GREEN_API_CHAT_ID from environment, if present, without forcing selection."""
    return _get_green_config().get("env_chat_id", "")


def is_sending_active(session_approved: bool = True) -> bool:
    """
    Returns True when Green API credentials are configured and sending is approved
    (unless explicitly disabled via GREEN_API_SENDING_ENABLED=false).
    """
    cfg = _get_green_config()
    if cfg["sending_enabled_flag"] in ("0", "false", "no"):
        return False
    return bool(session_approved and is_configured())


def get_destination_group(timeout: int = 10) -> Dict[str, Any]:
    """
    Resolves the configured destination WhatsApp group (Media Monitor) from GREEN_API_CHAT_ID
    and retrieves its live group name via Green API getChats without hardcoding group IDs.
    """
    env_cid = get_env_suggested_chat_id().strip()
    if not env_cid:
        return {"ok": False, "id": "", "name": "", "error": "GREEN_API_CHAT_ID is not configured."}
    grps = list_whatsapp_groups(timeout=timeout)
    if grps.get("ok"):
        for g in grps.get("groups", []):
            if g["id"] == env_cid:
                return {"ok": True, "id": g["id"], "name": g["name"], "error": ""}
    return {"ok": True, "id": env_cid, "name": "Media Monitor", "error": ""}


def get_instance_status(timeout: int = 8) -> Dict[str, Any]:
    """Checks Green API instance authorization state without exposing credentials."""
    cfg = _get_green_config()
    if not (cfg["api_url"] and cfg["id_instance"] and cfg["token_instance"]):
        return {
            "configured": False,
            "authorized": False,
            "state": "not_configured",
            "error": "Green API credentials are not configured in the server environment.",
        }
    endpoint = f"{cfg['api_url']}/waInstance{cfg['id_instance']}/getStateInstance/{cfg['token_instance']}"
    try:
        resp = requests.get(endpoint, timeout=timeout)
        if resp.status_code != 200:
            return {
                "configured": True,
                "authorized": False,
                "state": f"http_{resp.status_code}",
                "error": f"Green API returned HTTP {resp.status_code} while checking instance state.",
            }
        data = resp.json()
        state = str(data.get("stateInstance") or "unknown")
        return {
            "configured": True,
            "authorized": state == "authorized",
            "state": state,
            "error": "" if state == "authorized" else f"Instance state is '{state}'.",
        }
    except Exception as exc:
        logger.warning(f"Green API state check failed: {type(exc).__name__}")
        return {
            "configured": True,
            "authorized": False,
            "state": "unreachable",
            "error": "Unable to reach Green API instance. Check network or instance URL.",
        }


def list_whatsapp_groups(timeout: int = 10) -> Dict[str, Any]:
    """Retrieves available WhatsApp groups (@g.us) from the connected Green API instance."""
    cfg = _get_green_config()
    if not (cfg["api_url"] and cfg["id_instance"] and cfg["token_instance"]):
        return {"ok": False, "groups": [], "error": "Green API credentials are not configured."}

    endpoint = f"{cfg['api_url']}/waInstance{cfg['id_instance']}/getChats/{cfg['token_instance']}"
    try:
        resp = requests.get(endpoint, timeout=timeout)
        if resp.status_code != 200:
            return {
                "ok": False,
                "groups": [],
                "error": f"Green API getChats returned HTTP {resp.status_code}.",
            }
        raw_chats = resp.json()
        if not isinstance(raw_chats, list):
            return {"ok": False, "groups": [], "error": "Unexpected response format from Green API getChats."}

        seen: Set[str] = set()
        groups: List[Dict[str, str]] = []
        for ch in raw_chats:
            cid = str(ch.get("id") or "").strip()
            if not cid.endswith("@g.us") or cid in seen:
                continue
            seen.add(cid)
            name = str(ch.get("name") or "").strip() or cid
            groups.append({"id": cid, "name": name})

        groups.sort(key=lambda g: g["name"].lower())
        return {"ok": True, "groups": groups, "error": ""}
    except Exception as exc:
        logger.warning(f"Green API getChats failed: {type(exc).__name__}")
        return {"ok": False, "groups": [], "error": "Failed to retrieve WhatsApp groups from Green API."}


def build_send_dedup_key(chat_id: str, message: str) -> str:
    """Creates a deterministic key to prevent duplicate sends of the same content to the same group."""
    digest = hashlib.sha256(f"{chat_id}||{message}".encode("utf-8")).hexdigest()[:20]
    return digest


def send_group_message(
    chat_id: str,
    message: str,
    session_approved: bool = False,
    sent_registry: Optional[Set[str]] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """
    Sends a single text message to a selected WhatsApp group via Green API.
    Remains strictly inactive unless is_sending_active(session_approved) is True.
    Distinguishes Green API queue acceptance (idMessage) from confirmed delivery.
    """
    if not is_sending_active(session_approved=session_approved):
        return {
            "ok": False,
            "accepted": False,
            "status": "inactive",
            "id_message": "",
            "error": "WhatsApp group messaging is currently inactive pending Green API setup & approval.",
        }

    target_chat = (chat_id or "").strip()
    body = (message or "").strip()
    if not target_chat or not target_chat.endswith("@g.us"):
        return {
            "ok": False,
            "accepted": False,
            "status": "invalid_group",
            "id_message": "",
            "error": "Please select a valid destination WhatsApp group first.",
        }
    if not body:
        return {
            "ok": False,
            "accepted": False,
            "status": "empty_message",
            "id_message": "",
            "error": "Message content is empty.",
        }

    dedup_key = build_send_dedup_key(target_chat, body)
    if sent_registry is not None and dedup_key in sent_registry:
        return {
            "ok": False,
            "accepted": False,
            "status": "duplicate_prevented",
            "id_message": "",
            "error": "This exact content was already sent to the selected group.",
        }

    cfg = _get_green_config()
    endpoint = f"{cfg['api_url']}/waInstance{cfg['id_instance']}/sendMessage/{cfg['token_instance']}"
    payload = {
        "chatId": target_chat,
        "message": body,
        "linkPreview": True,
    }
    try:
        resp = requests.post(endpoint, json=payload, timeout=timeout)
        if resp.status_code != 200:
            return {
                "ok": False,
                "accepted": False,
                "status": "api_error",
                "id_message": "",
                "error": f"Green API rejected message with HTTP {resp.status_code}.",
            }
        data = resp.json()
        id_msg = str(data.get("idMessage") or "").strip()
        if not id_msg:
            return {
                "ok": False,
                "accepted": False,
                "status": "no_message_id",
                "id_message": "",
                "error": "Green API did not return an acceptance idMessage.",
            }
        if sent_registry is not None:
            sent_registry.add(dedup_key)
        return {
            "ok": True,
            "accepted": True,
            "status": "accepted_by_api",
            "id_message": id_msg,
            "error": "",
        }
    except Exception as exc:
        logger.warning(f"Green API sendMessage failed: {type(exc).__name__}")
        return {
            "ok": False,
            "accepted": False,
            "status": "network_error",
            "id_message": "",
            "error": "Network error while sending to Green API.",
        }
