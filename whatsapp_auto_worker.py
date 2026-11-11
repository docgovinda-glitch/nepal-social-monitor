"""
whatsapp_auto_worker.py
-----------------------
Automated background worker for Nepal Media & Intelligence Monitor.
Periodically scans for fresh, unbroadcasted news articles and X tweets,
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
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("whatsapp_auto_worker")

# Import project modules
from nepal_fetcher import fetch_top_nepal_media, fetch_nepal_in_indian_media, NEPAL_TZ
from nepal_x_scanner import scan_popular_nepal_x_posts
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
    get_green_api_credentials,
    find_channel_newsletter_id
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

def is_within_broadcast_hours(dt: datetime) -> bool:
    """
    Checks if given time is within allowed broadcasting hours:
    From 6:00 AM (06:00) to 10:00 PM (22:00) NPT.
    Allows tolerance for runs starting at 22:00:00 up to 22:05:00.
    """
    if dt.hour < 6:
        return False
    if dt.hour > 22:
        return False
    if dt.hour == 22 and dt.minute > 5:
        return False
    return True

def get_next_run_time(dt: datetime) -> datetime:
    """
    Calculates the exact next scheduled run time.
    Operating hours: 6:00 AM to 10:00 PM NPT (hours 6 through 22).
    Scheduled for the first minute of each hour (:00:00).
    Night quiet window (10:00 PM to 6:00 AM): sleeps until 06:00:00 AM.
    """
    if dt.hour >= 22 and (dt.minute > 0 or dt.second > 0):
        # After 10:00 PM cycle finishes, sleep until 06:00 AM tomorrow
        return (dt + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
    elif dt.hour < 6:
        # Before 6:00 AM, sleep until 06:00 AM today
        return dt.replace(hour=6, minute=0, second=0, microsecond=0)
    else:
        # Between 06:00 and 21:59, next run is top of next hour (:00:00)
        return (dt + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

def run_single_broadcast_cycle(
    max_items_per_cycle: int = 10,
    dry_run: bool = False,
    force: bool = False
) -> Dict[str, Any]:
    """
    Executes a single scan-and-dispatch cycle across all feeds.
    Returns summary statistics of the run.
    """
    now_nepal = datetime.now(NEPAL_TZ)

    # Operating window check: 6:00 AM to 10:00 PM NPT
    if not is_within_broadcast_hours(now_nepal) and not force:
        logger.info(
            f"Current time ({now_nepal.strftime('%I:%M %p')} NPT) is outside broadcast window (06:00 AM - 10:00 PM). "
            "Overnight news is held and will be broadcast at 06:00 AM at once. (Use --force to override)"
        )
        return {
            "timestamp": now_nepal.isoformat(),
            "status": "held_outside_hours",
            "dispatched": 0,
            "failed": 0
        }

    webhook_url = get_env_variable("WHATSAPP_WEBHOOK_URL")
    meta_token = get_env_variable("WHATSAPP_ACCESS_TOKEN")
    _, green_id, _ = get_green_api_credentials()
    green_chat_id = get_env_variable("GREEN_API_CHAT_ID")
    if not green_chat_id and green_id:
        detected_ch = find_channel_newsletter_id()
        if detected_ch:
            green_chat_id = detected_ch

    logger.info("--- Starting Broadcast Scan Cycle ---")
    logger.info(f"Current Time: {now_nepal.strftime('%Y-%m-%d %I:%M:%S %p')} NPT")
    logger.info(f"Broadcast Channel URL: {get_env_variable('WHATSAPP_CHANNEL_URL', DEFAULT_CHANNEL_URL)}")
    logger.info(f"Direct Green-API configured: {'Yes (Chat: ' + green_chat_id + ')' if green_id and green_chat_id else 'No'}")
    logger.info(f"Webhook URL configured: {'Yes' if webhook_url else 'No'}")
    logger.info(f"Meta Cloud API configured: {'Yes' if meta_token else 'No'}")

    # 1. Fetch latest items across portals (Nepali media, Indian media & X posts only)
    logger.info("Scanning Nepali media, Indian press & X posts...")
    nepali_articles = fetch_top_nepal_media(max_workers=15)
    indian_articles = fetch_nepal_in_indian_media(max_workers=12)
    x_posts = scan_popular_nepal_x_posts(force_refresh=False)

    all_scanned: List[tuple[Dict[str, Any], str]] = []
    # 1. Send all news published by 34 Nepali media regardless of category
    for a in nepali_articles:
        all_scanned.append((a, "article"))

    # 2. Indian media publishing anything about Nepal
    for a in indian_articles:
        all_scanned.append((a, "article"))

    # 3. X posts that strictly fall under the structured categories (excluding uncategorized/generic chatter)
    CORE_X_CATEGORIES = {
        "India Section",
        "China Section",
        "Pakistan Section",
        "Bangladesh Section",
        "Nepal – Internal",
        "Nepal – External",
        "Nepal – Economy",
        "International News",
        # Backward compatibility aliases
        "India in Nepal",
        "China in Nepal",
        "Pakistan in Nepal",
        "Bangladesh in Nepal",
        "Nepal – Internal Politics",
        "Nepal – External Relations (Others)",
        "Economy"
    }
    for p in x_posts:
        cat = (p.get("structured_category") or "").strip()
        if cat in CORE_X_CATEGORIES:
            all_scanned.append((p, "x"))

    # 2. Filter for items published in the refresh window
    # Morning window (06:00 AM): 10-hour lookback sweeps all overnight stories from 10 PM to 6 AM
    if now_nepal.hour == 6 or now_nepal.hour < 7:
        lookback_seconds = 10 * 3600  # 10 hours covers from 8 PM yesterday to 6 AM today
        logger.info("🌅 6:00 AM Morning batch: Gathering and broadcasting all overnight news from 10:00 PM to 6:00 AM...")
    else:
        # Daytime hourly runs (7:00 AM to 10:00 PM): 3-hour lookback ensures no gaps
        lookback_seconds = 3 * 3600

    cutoff_time = now_nepal - timedelta(seconds=lookback_seconds)

    def _parse_item_dt(val):
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=NEPAL_TZ)
        if isinstance(val, str):
            try:
                dt = datetime.fromisoformat(val)
                return dt if dt.tzinfo else dt.replace(tzinfo=NEPAL_TZ)
            except Exception:
                return None
        return None

    unbroadcasted_in_window = []
    for item, itype in all_scanned:
        pdt = _parse_item_dt(item.get("published_dt"))
        # Keep items published within the refresh window (or items with no timestamp)
        if pdt and pdt < cutoff_time:
            continue
        if not is_item_broadcasted(item, itype):
            unbroadcasted_in_window.append((item, itype))

    # Sort chronological (oldest unbroadcasted first) so messages appear in sequential order
    def _get_dt(entry):
        dt = _parse_item_dt(entry[0].get("published_dt"))
        if not dt:
            return datetime.min.replace(tzinfo=NEPAL_TZ)
        return dt

    unbroadcasted_in_window.sort(key=_get_dt)

    logger.info(
        f"Total scanned: {len(all_scanned)} | "
        f"Unsent within lookback ({lookback_seconds // 3600}h): {len(unbroadcasted_in_window)}"
    )

    dispatched_count = 0
    failed_count = 0

    # If max_items_per_cycle is <= 0 or 0, broadcast ALL stories published in the interval window
    if max_items_per_cycle and max_items_per_cycle > 0:
        items_to_send = unbroadcasted_in_window[:max_items_per_cycle]
        logger.info(f"Broadcasting {len(items_to_send)} items (capped at {max_items_per_cycle})...")
    else:
        items_to_send = unbroadcasted_in_window
        logger.info(f"Broadcasting ALL {len(items_to_send)} fresh stories in this cycle...")

    for item, itype in items_to_send:
        title = item.get("title") or item.get("text") or "Untitled"
        if dry_run:
            logger.info(f"[DRY RUN] Would send: {title[:70]}")
            dispatched_count += 1
            continue

        success = False
        try:
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
        except Exception as ex:
            logger.error(f"Error dispatching item '{title[:50]}': {ex}")

        if success:
            mark_item_broadcasted(item, itype)
            dispatched_count += 1
            time.sleep(1)  # 1-second pacing between posts to respect rate limits
        else:
            failed_count += 1

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_scanned": len(all_scanned),
        "unbroadcasted_found": len(unbroadcasted_in_window),
        "dispatched": dispatched_count,
        "failed": failed_count,
        "remaining_unbroadcasted": max(0, len(unbroadcasted_in_window) - dispatched_count)
    }
    logger.info(f"Broadcast cycle finished: {dispatched_count} sent, {failed_count} failed.")
    return summary

def main():
    default_max = int(get_env_variable("MAX_BROADCAST_PER_CYCLE", "0"))  # 0 = send all stories published in cycle
    parser = argparse.ArgumentParser(description="Nepal Monitor WhatsApp Automated Dispatch Worker")
    parser.add_argument("--once", action="store_true", help="Run once and exit (for cron jobs)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without sending network requests")
    parser.add_argument("--max-per-cycle", type=int, default=default_max, help=f"Maximum stories to send per cycle (0 = send all stories, default: {default_max})")
    parser.add_argument("--force", action="store_true", help="Force broadcast even outside active hours (10:00 PM - 06:00 AM)")
    parser.add_argument("--run-now", action="store_true", help="Run an immediate cycle upon startup before syncing to hourly :00 schedule")

    args = parser.parse_args()

    if args.once:
        run_single_broadcast_cycle(max_items_per_cycle=args.max_per_cycle, dry_run=args.dry_run, force=args.force)
    else:
        logger.info("==================================================================")
        logger.info("Starting Nepal Monitor Continuous Daemon")
        logger.info("Schedule: 06:00 AM to 10:00 PM NPT (every hour at :00)")
        logger.info("Overnight news (10:00 PM to 06:00 AM) held and broadcast at 06:00 AM at once")
        logger.info("==================================================================")

        if args.run_now:
            try:
                run_single_broadcast_cycle(max_items_per_cycle=args.max_per_cycle, dry_run=args.dry_run, force=args.force)
            except Exception as ex:
                logger.error(f"Error during startup broadcast cycle: {ex}")

        while True:
            now_nepal = datetime.now(NEPAL_TZ)
            next_run = get_next_run_time(now_nepal)
            sleep_secs = max(5, int((next_run - now_nepal).total_seconds()))

            logger.info(
                f"Next broadcast scheduled for: {next_run.strftime('%Y-%m-%d %I:%M:%S %p')} NPT "
                f"(sleeping for {sleep_secs}s / {sleep_secs // 60}m)..."
            )
            time.sleep(sleep_secs)

            try:
                run_single_broadcast_cycle(max_items_per_cycle=args.max_per_cycle, dry_run=args.dry_run, force=args.force)
            except Exception as ex:
                logger.error(f"Error during broadcast cycle: {ex}")

if __name__ == "__main__":
    main()
