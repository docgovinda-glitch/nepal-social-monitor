"""
nepal_news_scheduler.py
Source-aware continuous news monitoring and discovery scheduler for Nepal Social Monitor.
Implements tiered polling intervals, overlapping discovery windows, error retries,
and historical backfill to ensure comprehensive news capture 24/7.
"""

import time
import logging
import threading
import datetime
import zoneinfo
from typing import List, Dict, Any, Optional

from nepal_news_store import (
    batch_upsert_articles,
    record_source_error,
    get_all_source_health,
    set_source_enabled,
    set_source_interval,
    register_portal_sources,
    query_supabase,
)
from nepal_summarizer import _has_devanagari

logger = logging.getLogger("nepal_news_scheduler")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

NEPAL_TZ = zoneinfo.ZoneInfo("Asia/Kathmandu")

def run_single_source_discovery(source_config: Dict[str, Any], max_articles: int = 50) -> Dict[str, Any]:
    """
    Executes deep discovery for a single portal using RSS, category feeds, or HTML scraping.
    Captures discovery latency, newly published items, and updates the SQLite store.
    """
    from nepal_fetcher import fetch_single_portal
    source_name = source_config["name"]
    t0 = time.time()
    now_npt = datetime.datetime.now(NEPAL_TZ)

    try:
        articles = fetch_single_portal(source_config, now_npt, max_entries=max_articles)
        latency = round(time.time() - t0, 3)

        if articles:
            stats = batch_upsert_articles(articles, source_name, latency_secs=latency)
            stats["status"] = "OK"
            stats["latency_secs"] = latency
            stats["sample_title"] = articles[0]["title"][:60]
            logger.info(f"[{source_name}] Discovered {stats['discovered']} | Ingested {stats['ingested']} | Duplicates {stats['duplicates']} | {latency}s")
            return stats
        else:
            # Check if source returned 0 items
            stats = {
                "discovered": 0,
                "ingested": 0,
                "duplicates": 0,
                "updated": 0,
                "status": "EMPTY",
                "latency_secs": latency,
                "sample_title": "No articles parsed"
            }
            logger.warning(f"[{source_name}] Zero articles parsed in {latency}s")
            return stats
    except Exception as e:
        latency = round(time.time() - t0, 3)
        err_msg = str(e)[:300]
        record_source_error(source_name, err_msg, latency_secs=latency)
        logger.error(f"[{source_name}] Discovery failed after {latency}s: {err_msg}")
        return {
            "discovered": 0,
            "ingested": 0,
            "duplicates": 0,
            "updated": 0,
            "status": "ERROR",
            "error": err_msg,
            "latency_secs": latency
        }

def run_all_sources_discovery(parallel_workers: int = 15, force_all: bool = False) -> Dict[str, Any]:
    """
    Runs an ingestion cycle across all enabled Nepali media outlets.
    If force_all=False, only polls sources whose check_interval_mins have elapsed.
    """
    import concurrent.futures
    from nepal_fetcher import TOP_NEPAL_NEWS_PORTALS

    portal_map = {p["name"]: p for p in TOP_NEPAL_NEWS_PORTALS}
    health_rows = get_all_source_health()
    now = datetime.datetime.now()

    portals_to_run = []
    for h in health_rows:
        if not h.get("enabled", 1):
            continue
        name = h["name"]
        portal_cfg = portal_map.get(name)
        if not portal_cfg:
            continue

        if force_all:
            portals_to_run.append(portal_cfg)
            continue

        # Check interval
        interval_mins = h.get("check_interval_mins", 15)
        last_disc = h.get("last_discovery_time")
        if not last_disc:
            portals_to_run.append(portal_cfg)
            continue

        try:
            if isinstance(last_disc, str):
                last_dt = datetime.datetime.strptime(last_disc[:19], "%Y-%m-%d %H:%M:%S")
            else:
                last_dt = last_disc
            elapsed = (now - last_dt).total_seconds() / 60.0
            if elapsed >= interval_mins:
                portals_to_run.append(portal_cfg)
        except Exception:
            portals_to_run.append(portal_cfg)

    if not portals_to_run:
        logger.info("All sources are currently up-to-date within their configured intervals.")
        return {"total_checked": 0, "total_ingested": 0, "results": {}}

    logger.info(f"Starting scheduled discovery for {len(portals_to_run)} of {len(TOP_NEPAL_NEWS_PORTALS)} portals...")
    results = {}
    total_ingested = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        future_map = {executor.submit(run_single_source_discovery, p): p["name"] for p in portals_to_run}
        for future in concurrent.futures.as_completed(future_map):
            src_name = future_map[future]
            try:
                res = future.result()
                results[src_name] = res
                total_ingested += res.get("ingested", 0)
            except Exception as e:
                results[src_name] = {"status": "ERROR", "error": str(e)}

    return {
        "total_checked": len(portals_to_run),
        "total_ingested": total_ingested,
        "results": results
    }

def run_historical_backfill(
    source_names: Optional[List[str]] = None,
    days_back: int = 3,
    parallel_workers: int = 8
) -> Dict[str, Any]:
    """
    Initiates deep historical recovery / backfill for specified portals (or all portals).
    Fetches deep archives, pagination feeds, and news sitemaps where supported.
    """
    from nepal_fetcher import TOP_NEPAL_NEWS_PORTALS
    portal_map = {p["name"]: p for p in TOP_NEPAL_NEWS_PORTALS}
    target_names = source_names if source_names else list(portal_map.keys())

    logger.info(f"Initiating historical backfill for {len(target_names)} portals (past {days_back} days)...")
    results = {}
    total_ingested = 0

    for name in target_names:
        p_cfg = portal_map.get(name)
        if not p_cfg:
            continue
        # Request maximum entries (up to 120) for backfill
        res = run_single_source_discovery(p_cfg, max_articles=120)
        results[name] = res
        total_ingested += res.get("ingested", 0)

    logger.info(f"Historical backfill completed. Ingested {total_ingested} historical articles.")
    return {
        "days_back": days_back,
        "sources_backfilled": len(target_names),
        "total_ingested": total_ingested,
        "details": results
    }

def run_summary_enrichment_backfill(batch_size: int = 80) -> int:
    """
    Finds recent Nepali Media and Indian Press articles lacking clean English summaries
    or English headlines, extracts full body text, and generates LexRank English briefs.
    """
    from nepal_fetcher import batch_fetch_full_content
    from nepal_summarizer import _summary_needs_enrichment

    needs_sql = (
        "(summary IS NULL OR summary = '' OR summary = title OR summary LIKE '%...%' "
        "OR summary ~ '[\u0900-\u097F]' OR summary LIKE 'Author %' OR summary LIKE 'By %' "
        "OR summary LIKE 'Edited by %' OR summary LIKE 'Published:%' OR summary LIKE 'Updated:%' "
        "OR summary LIKE 'Kathmandu [%' OR summary LIKE 'New Delhi [%' "
        "OR summary LIKE 'Kathmandu/%' OR summary LIKE 'KATHMANDU/%' OR summary LIKE 'Nepalgunj - %' "
        "OR summary LIKE '%Prabhat Khabar your favorite source%' OR summary LIKE '%preferred source on Google%' "
        "OR summary LIKE '%appeared first on%' "
        "OR headline_english IS NULL OR headline_english = '' OR headline_english ~ '[\u0900-\u097F]')"
    )

    np_rows = query_supabase(
        "SELECT canonical_id, source, title, headline_english, link, summary, full_content, language "
        f"FROM articles WHERE {needs_sql} ORDER BY published_dt DESC LIMIT {int(batch_size)};"
    )
    in_rows = query_supabase(
        "SELECT canonical_id, source, title, headline_english, link, summary, full_content, language "
        "FROM indian_media_articles WHERE relevance_status IN ('substantive', 'relevant') "
        f"AND {needs_sql} ORDER BY published_dt DESC LIMIT {int(batch_size)};"
    )

    candidates: List[Dict[str, Any]] = []
    for r in in_rows:
        r["stream"] = "Indian Press"
        if _summary_needs_enrichment(r):
            candidates.append(r)
    for r in np_rows:
        r["stream"] = "Nepali Media"
        if _summary_needs_enrichment(r):
            candidates.append(r)

    target_batch = candidates[:batch_size]
    if not target_batch:
        return 0

    batch_fetch_full_content(target_batch, max_workers=12, summarize_english=True)
    logger.info(f"Summary enrichment backfill completed for {len(target_batch)} articles.")
    return len(target_batch)


# Background Monitoring Worker Thread
_MONITOR_THREAD = None
_STOP_EVENT = threading.Event()
_LAST_X_SCAN_TIME = 0.0
_LAST_INDIAN_SCAN_TIME = 0.0
X_SCAN_INTERVAL_SECS = 15 * 60  # Automatically scan X every 15 minutes
INDIAN_SCAN_INTERVAL_SECS = 15 * 60  # Automatically poll 18 Indian outlets every 15 minutes

def _monitoring_daemon_loop():
    """Background continuous loop that checks and ingests Nepali portals, Indian press, and X posts."""
    global _LAST_X_SCAN_TIME, _LAST_INDIAN_SCAN_TIME
    logger.info("Continuous News Monitoring Daemon started in background.")
    while not _STOP_EVENT.is_set():
        try:
            run_all_sources_discovery(parallel_workers=12, force_all=False)
        except Exception as e:
            logger.error(f"Error in monitoring loop cycle: {e}")

        # Automated continuous Indian Press polling (18 outlets)
        now_sec = time.time()
        if now_sec - _LAST_INDIAN_SCAN_TIME >= INDIAN_SCAN_INTERVAL_SECS:
            try:
                from nepal_fetcher import fetch_nepal_in_indian_media
                logger.info("Triggering periodic background Indian Press scan across 18 outlets...")
                fetch_nepal_in_indian_media(max_workers=15, force_refresh=True)
                _LAST_INDIAN_SCAN_TIME = time.time()
                logger.info("Periodic background Indian Press scan completed successfully.")
            except Exception as e:
                logger.error(f"Error in background Indian Press scan cycle: {e}")

        # On-demand brief/translation strategy: do not auto-run background summarization/translation on incoming feeds

        # Automated continuous X scanning
        now_sec = time.time()
        if now_sec - _LAST_X_SCAN_TIME >= X_SCAN_INTERVAL_SECS:
            try:
                from nepal_x_scanner import scan_popular_nepal_x_posts
                logger.info("Triggering periodic background X scan across verified Nepali accounts...")
                scan_popular_nepal_x_posts(force_refresh=True)
                _LAST_X_SCAN_TIME = now_sec
                logger.info("Periodic background X scan completed successfully.")
            except Exception as e:
                logger.error(f"Error in background X scan cycle: {e}")

        # Sleep for 60 seconds between cycle evaluations
        _STOP_EVENT.wait(60.0)

def start_monitoring_daemon():
    """Starts the continuous news monitoring worker in a background daemon thread."""
    global _MONITOR_THREAD
    if _MONITOR_THREAD and _MONITOR_THREAD.is_alive():
        return
    _STOP_EVENT.clear()
    _MONITOR_THREAD = threading.Thread(target=_monitoring_daemon_loop, name="NepalNewsMonitorDaemon", daemon=True)
    _MONITOR_THREAD.start()
    logger.info("Launched NepalNewsMonitorDaemon thread.")


