"""
whatsapp_auto_worker.py
-----------------------
Automated background worker for Nepal Media & Intelligence Monitor.
Periodically scans for fresh, unbroadcasted news articles, X tweets, and Facebook posts,
deduplicates them, and dispatches them to your WhatsApp Channel via Webhook or Cloud API.
"""

import os
import sys
import time
import json
import logging
import argparse
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Any, List, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("whatsapp_auto_worker")

# Import project modules
from nepal_fetcher import fetch_top_nepal_media, fetch_nepal_in_indian_media
from nepal_x_scanner import scan_popular_nepal_x_posts
from nepal_fb_real_scanner import scan_real_nepal_fb_intelligence
from whatsapp_dispatcher import (
    load_sent_cache,
    is_item_broadcasted,
    mark_item_broadcasted,
    format_whatsapp_message,
    get_item_key,
    DEFAULT_CHANNEL_URL,
    get_env_variable,
    dispatch_item_to_webhook,
    get_green_api_status,
    dispatch_item_to_green_api,
    get_green_api_credentials
)

def dispatch_to_webhook(item: Dict[str, Any], item_type: str, webhook_url: str) -> bool:
    """Sends an item to webhook and logs outcome."""
    ok, msg = dispatch_item_to_webhook(item, item_type, webhook_url)
    title = item.get("title") or item.get("text") or "Untitled"
    if ok:
        logger.info(f"Successfully dispatched to webhook ({msg}): {title[:60]}")
    else:
        logger.warning(f"Failed to dispatch to webhook ({msg}): {title[:60]}")
    return ok

def dispatch_to_meta_cloud_api(item: Dict[str, Any], item_type: str) -> bool:
    """
    Sends message directly via Meta's WhatsApp Business Cloud API if credentials exist.
    """
    access_token = get_env_variable("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = get_env_variable("WHATSAPP_PHONE_NUMBER_ID")
    channel_id = get_env_variable("WHATSAPP_CHANNEL_ID")

    if not access_token or not channel_id:
        return False

    wa_text = format_whatsapp_message(item, item_type)
    url = f"https://graph.facebook.com/v20.0/{channel_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "channel",
        "type": "text",
        "text": {"body": wa_text}
    }

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=utf-8"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.getcode() in (200, 201)
    except Exception as ex:
        logger.error(f"Error posting to Meta WhatsApp Cloud API: {ex}")
        return False

def run_single_broadcast_cycle(
    max_items_per_cycle: int = 10,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Executes a single scan-and-dispatch cycle across all feeds.
    Returns summary statistics of the run.
    """
    webhook_url = get_env_variable("WHATSAPP_WEBHOOK_URL")
    meta_token = get_env_variable("WHATSAPP_ACCESS_TOKEN")
    _, green_id, _ = get_green_api_credentials()
    green_chat_id = get_env_variable("GREEN_API_CHAT_ID")

    logger.info("--- Starting Broadcast Scan Cycle ---")
    logger.info(f"Direct Green-API configured: {'Yes (Chat: ' + green_chat_id + ')' if green_id and green_chat_id else 'No'}")
    logger.info(f"Webhook URL configured: {'Yes' if webhook_url else 'No'}")
    logger.info(f"Meta Cloud API configured: {'Yes' if meta_token else 'No'}")

    # 1. Fetch latest items across all portals
    logger.info("Scanning Nepali media, Indian press, X posts & Facebook feeds...")
    nepali_articles = fetch_top_nepal_media(max_workers=15)
    indian_articles = fetch_nepal_in_indian_media(max_workers=12)
    x_posts = scan_popular_nepal_x_posts(force_refresh=False)
    fb_posts = scan_real_nepal_fb_intelligence(nepali_articles)

    all_scanned: List[tuple[Dict[str, Any], str]] = []
    for a in nepali_articles:
        all_scanned.append((a, "article"))
    for a in indian_articles:
        all_scanned.append((a, "article"))
    for p in x_posts:
        all_scanned.append((p, "x"))
    for p in fb_posts:
        all_scanned.append((p, "fb"))

    # 2. Filter for unbroadcasted items using deduplication engine
    unbroadcasted = []
    for item, itype in all_scanned:
        if not is_item_broadcasted(item, itype):
            unbroadcasted.append((item, itype))

    logger.info(f"Total scanned items: {len(all_scanned)} | Unsent new items: {len(unbroadcasted)}")

    dispatched_count = 0
    failed_count = 0
    items_to_send = unbroadcasted[:max_items_per_cycle]

    for item, itype in items_to_send:
        title = item.get("title") or item.get("text") or "Untitled"
        if dry_run:
            logger.info(f"[DRY RUN] Would send: {title[:70]}")
            dispatched_count += 1
            continue

        success = False
        if green_id and green_chat_id:
            ok, msg = dispatch_item_to_green_api(item, itype, green_chat_id)
            if ok:
                logger.info(f"Successfully dispatched to Green-API: {title[:60]}")
                success = True
            else:
                logger.warning(f"Green-API dispatch failed ({msg}): {title[:60]}")
        elif webhook_url:
            success = dispatch_to_webhook(item, itype, webhook_url)
        elif meta_token:
            success = dispatch_to_meta_cloud_api(item, itype)
        else:
            logger.info(f"[NO DISPATCH CHANNEL CONFIGURED] Item queued: {title[:70]}")
            # Without Green-API, webhook, or meta API, don't mark as sent so it stays in queue
            break

        if success:
            mark_item_broadcasted(item, itype)
            dispatched_count += 1
            time.sleep(1)  # 1-second pacing between posts to respect rate limits
        else:
            failed_count += 1

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_scanned": len(all_scanned),
        "unbroadcasted_found": len(unbroadcasted),
        "dispatched": dispatched_count,
        "failed": failed_count,
        "remaining_unbroadcasted": max(0, len(unbroadcasted) - dispatched_count)
    }
    logger.info(f"Broadcast cycle finished: {dispatched_count} sent, {failed_count} failed.")
    return summary

def main():
    parser = argparse.ArgumentParser(description="Nepal Monitor WhatsApp Automated Dispatch Worker")
    parser.add_argument("--interval", type=int, default=1800, help="Scan interval in seconds (default: 1800s / 30 mins)")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for cron jobs)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without sending network requests")
    parser.add_argument("--max-per-cycle", type=int, default=10, help="Maximum stories to send per cycle")

    args = parser.parse_args()

    if args.once:
        run_single_broadcast_cycle(max_items_per_cycle=args.max_per_cycle, dry_run=args.dry_run)
    else:
        logger.info(f"Starting continuous daemon (interval: {args.interval} seconds / {args.interval // 60} mins)...")
        while True:
            try:
                run_single_broadcast_cycle(max_items_per_cycle=args.max_per_cycle, dry_run=args.dry_run)
            except Exception as ex:
                logger.error(f"Error during broadcast cycle: {ex}")
            logger.info(f"Sleeping for {args.interval} seconds until next scan...")
            time.sleep(args.interval)

if __name__ == "__main__":
    main()
