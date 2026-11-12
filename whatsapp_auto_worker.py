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
import random
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
# Explicitly exclude X from WhatsApp distribution
import nepal_news_store
from nepal_news_store import (
    enqueue_whatsapp_items,
    get_pending_whatsapp_queue,
    mark_whatsapp_queue_processing,
    mark_whatsapp_queue_sent,
    mark_whatsapp_queue_failed,
    get_whatsapp_queue_stats,
    get_all_source_health
)
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
    find_channel_newsletter_id,
    is_substantially_related_to_nepal
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
    Checks if given time is within allowed WhatsApp broadcasting hours:
    From 6:00 AM (06:00) to 10:00 PM (22:00) NPT.
    Strictly:
      6:00 AM <= dt < 10:00 PM (hour 6 through 21, or 22:00:00 - 22:05:00 window).
    Between 10:00 PM and 6:00 AM: WhatsApp sending is paused.
    """
    # Force evaluation in Asia/Kathmandu
    dt_npt = dt.astimezone(NEPAL_TZ) if dt.tzinfo else dt.replace(tzinfo=NEPAL_TZ)
    if dt_npt.hour < 6:
        return False
    if dt_npt.hour > 22:
        return False
    if dt_npt.hour == 22 and (dt_npt.minute > 5 or (dt_npt.minute == 5 and dt_npt.second > 0)):
        return False
    return True

def get_next_run_time(dt: datetime) -> datetime:
    """
    Calculates the exact next scheduled run time.
    Operational Requirement:
    - Runs at minute 01 of every hour (e.g., 6:01 AM, 7:01 AM, ...).
    - If current time is past minute 1 of hour H, next run is (H+1):01:00.
    - If after 10:01 PM NPT, next broadcast window opens at 06:01 AM tomorrow.
    - If before 6:01 AM NPT, next broadcast run is 06:01 AM today.
    """
    dt_npt = dt.astimezone(NEPAL_TZ) if dt.tzinfo else dt.replace(tzinfo=NEPAL_TZ)

    # If past 22:01 NPT, sleep until 06:01 AM tomorrow
    if dt_npt.hour > 22 or (dt_npt.hour == 22 and dt_npt.minute >= 1):
        return (dt_npt + timedelta(days=1)).replace(hour=6, minute=1, second=0, microsecond=0)
    # If before 06:01 AM NPT, sleep until 06:01 AM today
    elif dt_npt.hour < 6 or (dt_npt.hour == 6 and dt_npt.minute < 1):
        return dt_npt.replace(hour=6, minute=1, second=0, microsecond=0)
    else:
        # Daytime: next run is top of next hour at minute 01 (:01:00)
        if dt_npt.minute >= 1:
            next_h = dt_npt + timedelta(hours=1)
            # If next hour exceeds 22, it rolls to tomorrow 06:01
            if next_h.hour > 22:
                return (dt_npt + timedelta(days=1)).replace(hour=6, minute=1, second=0, microsecond=0)
            return next_h.replace(minute=1, second=0, microsecond=0)
        else:
            # We are in the current hour between :00:00 and :00:59, next run is :01:00 this hour
            return dt_npt.replace(minute=1, second=0, microsecond=0)

def collect_and_enqueue_news_items() -> Dict[str, int]:
    """
    Ingests fresh items from the TWO allowed streams:
      1. Nepali Media (all enabled portals, irrespective of category)
      2. Indian Press (all items substantially related to Nepal)
    Strictly excludes X (Twitter) handles and posts.
    Stores and enqueues items into persistent Supabase `whatsapp_queue`.
    Runs 24/7 (including during overnight pause) so overnight backlog is preserved.
    """
    logger.info("Collecting news items from Nepali Media & Indian Press...")
    nepali_articles = fetch_top_nepal_media(max_workers=15, force_refresh=True)
    indian_articles = fetch_nepal_in_indian_media(max_workers=12, force_refresh=True)

    try:
        enabled_portals = {h["name"] for h in get_all_source_health() if h.get("enabled", 1)}
    except Exception:
        enabled_portals = set()

    items_to_enqueue = []

    # 1. Nepali Media
    nepali_count = 0
    for a in nepali_articles:
        src = a.get("source", "")
        if enabled_portals and src and src not in enabled_portals:
            continue
        item_k = a.get("canonical_id") or get_item_key(a, "article")
        items_to_enqueue.append({
            "item_key": item_k,
            "canonical_id": a.get("canonical_id") or item_k,
            "source_name": src,
            "stream_type": "Nepali Media",
            "title": a.get("title", ""),
            "headline_english": a.get("headline_english", ""),
            "link": a.get("link", ""),
            "summary": a.get("summary", ""),
            "published_dt": a.get("published_dt"),
            "raw_item": a
        })
        nepali_count += 1

    # 2. Indian Press (substantially related to Nepal)
    indian_count = 0
    for a in indian_articles:
        if is_substantially_related_to_nepal(a):
            item_k = a.get("canonical_id") or get_item_key(a, "article")
            items_to_enqueue.append({
                "item_key": item_k,
                "canonical_id": a.get("canonical_id") or item_k,
                "source_name": a.get("source", "Indian Media"),
                "stream_type": "Indian Press",
                "title": a.get("title", ""),
                "headline_english": a.get("headline_english", ""),
                "link": a.get("link", ""),
                "summary": a.get("summary", ""),
                "published_dt": a.get("published_dt"),
                "raw_item": a
            })
            indian_count += 1

    enqueued_count = enqueue_whatsapp_items(items_to_enqueue)
    logger.info(
        f"Ingestion summary: {nepali_count} Nepali Media, {indian_count} Indian Press. "
        f"Enqueued {enqueued_count} items into persistent Supabase queue."
    )
    return {
        "nepali": nepali_count,
        "indian": indian_count,
        "enqueued": enqueued_count
    }

def run_single_broadcast_cycle(
    max_items_per_cycle: int = 0,
    dry_run: bool = False,
    force: bool = False
) -> Dict[str, Any]:
    """
    Executes a complete collection and dispatch cycle:
    1. Collects and persists all eligible Nepali Media & Indian Press items into `whatsapp_queue`.
       (Always runs, even overnight, so news is never missed).
    2. Checks strict operating window (6:00 AM to 10:00 PM NPT).
       Between 10:00 PM and 6:00 AM: Pauses sending, retains items in queue.
       At 6:00 AM: Resumes sending and processes accumulated overnight backlog.
    3. Fetches queued items sequentially and dispatches them until queue is cleared.
    """
    now_nepal = datetime.now(NEPAL_TZ)

    # STEP 1: Continuous Ingestion into persistent queue & 7-Day Purge
    try:
        # Automated 7-Day news article retention purge
        purge_res = nepal_news_store.query_supabase("SELECT purge_expired_news_articles();")
        if purge_res:
            logger.info(f"Executed automated 7-day data retention cleanup: {purge_res}")
    except Exception as purge_err:
        logger.warning(f"7-day retention purge warning (non-fatal): {purge_err}")

    try:
        collect_and_enqueue_news_items()
    except Exception as ex:
        logger.error(f"Error during news collection/enqueue step: {ex}")

    queue_stats_before = get_whatsapp_queue_stats()
    logger.info(f"Persistent Queue Status: {queue_stats_before}")

    # STEP 2: Operating Window Check (6:00 AM to 10:00 PM NPT)
    within_hours = is_within_broadcast_hours(now_nepal)
    if not within_hours and not force:
        logger.info(
            f"Current time ({now_nepal.strftime('%I:%M %p')} NPT) is in overnight pause window (10:00 PM - 06:00 AM NPT). "
            f"WhatsApp distribution paused. {queue_stats_before['pending_count']} items held in queue for 06:01 AM NPT dispatch."
        )
        return {
            "timestamp": now_nepal.isoformat(),
            "status": "held_outside_hours",
            "pending_in_queue": queue_stats_before["pending_count"],
            "dispatched": 0,
            "failed": 0
        }

    # STEP 3: Setup credentials
    webhook_url = get_env_variable("WHATSAPP_WEBHOOK_URL")
    meta_token = get_env_variable("WHATSAPP_ACCESS_TOKEN")
    _, green_id, _ = get_green_api_credentials()
    green_chat_id = get_env_variable("GREEN_API_CHAT_ID")
    if not green_chat_id and green_id:
        detected_ch = find_channel_newsletter_id()
        if detected_ch:
            green_chat_id = detected_ch

    logger.info("--- Starting WhatsApp Distribution Cycle ---")
    logger.info(f"Current Time: {now_nepal.strftime('%Y-%m-%d %I:%M:%S %p')} NPT")
    logger.info(f"Target WhatsApp Chat: {green_chat_id or 'Webhook/Meta API'}")

    # STEP 4: Fetch all pending items from Supabase queue (sequential, oldest first)
    pending_items = get_pending_whatsapp_queue(limit=500)
    logger.info(f"Retrieved {len(pending_items)} pending items from persistent queue.")

    if not pending_items:
        logger.info("Queue is empty. No unsent items pending distribution.")
        return {
            "timestamp": now_nepal.isoformat(),
            "status": "queue_empty",
            "dispatched": 0,
            "failed": 0
        }

    dispatched_count = 0
    failed_count = 0

    # Limit to max_items_per_cycle if explicitly requested (> 0); otherwise process ALL
    if max_items_per_cycle and max_items_per_cycle > 0:
        items_to_send = pending_items[:max_items_per_cycle]
        logger.info(f"Broadcasting {len(items_to_send)} items (capped at {max_items_per_cycle})...")
    else:
        items_to_send = pending_items
        logger.info(f"Broadcasting ALL {len(items_to_send)} pending stories in queue until clear...")

    # Mark all items being processed in database to prevent concurrent collisions
    mark_whatsapp_queue_processing([it["item_key"] for it in items_to_send])

    for it in items_to_send:
        # Stop sending if we suddenly cross past 10:00 PM (hour 22) during long dispatch
        curr_time = datetime.now(NEPAL_TZ)
        if not is_within_broadcast_hours(curr_time) and not force:
            logger.info(f"Cutoff reached ({curr_time.strftime('%I:%M %p')} NPT). Halting send loop; remaining items preserved.")
            break

        item_key = it["item_key"]
        title = it.get("title") or "Untitled"
        link = it.get("link") or ""
        source = it.get("source_name") or "Unknown"
        stream_type = it.get("stream_type") or "Nepali Media"

        # Check deduplication
        if is_item_broadcasted(it, "article"):
            logger.info(f"Item already broadcasted previously ({item_key}). Marking as sent: {title[:50]}")
            mark_whatsapp_queue_sent(item_key, message_id="already_broadcasted")
            continue

        if dry_run:
            logger.info(f"[DRY RUN] Would dispatch: [{stream_type}] {source} - {title[:60]}")
            dispatched_count += 1
            mark_whatsapp_queue_sent(item_key, message_id="dry_run")
            continue

        # Format item dictionary for dispatcher
        dispatch_dict = {
            "title": title,
            "headline_english": it.get("headline_english") or "",
            "link": link,
            "source": source,
            "summary": it.get("summary") or "",
            "published_dt": it.get("published_dt"),
            "structured_category": "Others",
            "stream": stream_type
        }

        # Sequential delivery with retries
        success = False
        msg_id = ""
        error_info = ""

        for attempt in range(1, 4):
            try:
                if green_id and green_chat_id:
                    ok, msg = dispatch_item_to_green_api(dispatch_dict, "article", green_chat_id)
                    if ok:
                        success = True
                        msg_id = msg
                        break
                    else:
                        error_info = msg
                        logger.warning(f"Attempt {attempt} failed ({msg}): {title[:50]}")
                elif webhook_url:
                    ok, msg = dispatch_item_to_webhook(dispatch_dict, "article", webhook_url)
                    if ok:
                        success = True
                        msg_id = msg
                        break
                    else:
                        error_info = msg
                elif meta_token:
                    ok = dispatch_to_meta_cloud_api(dispatch_dict, "article")
                    if ok:
                        success = True
                        break
                else:
                    error_info = "No WhatsApp channel credentials configured"
                    break
            except Exception as ex:
                error_info = str(ex)
                logger.error(f"Attempt {attempt} exception for '{title[:40]}': {ex}")

            if attempt < 3:
                time.sleep(2 * attempt)  # Backoff: 2s, 4s

        if success:
            logger.info(f"✓ Delivered: [{stream_type}] {source} · {title[:60]}")
            # Mark persistent cache & database
            mark_whatsapp_queue_sent(item_key, message_id=msg_id)
            mark_item_broadcasted(
                dispatch_dict,
                item_type="article",
                channel_name=green_chat_id or "WhatsApp Group",
                message_id=msg_id,
                status="delivered"
            )
            dispatched_count += 1

            # Human-like pacing delay (1.5s - 2.8s) to prevent spam heuristics & rate limits
            pacing_delay = random.uniform(1.5, 2.8)
            time.sleep(pacing_delay)
        else:
            logger.error(f"✗ Delivery failed for: {title[:60]} ({error_info})")
            mark_whatsapp_queue_failed(item_key, error_msg=error_info)
            failed_count += 1

    summary = {
        "timestamp": datetime.now(NEPAL_TZ).isoformat(),
        "dispatched": dispatched_count,
        "failed": failed_count,
        "remaining_pending": get_whatsapp_queue_stats().get("pending_count", 0)
    }
    logger.info(f"Broadcast cycle complete: {dispatched_count} sent, {failed_count} failed, {summary['remaining_pending']} pending.")
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
