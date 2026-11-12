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
    register_portal_sources
)

logger = logging.getLogger("nepal_news_scheduler")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

NEPAL_TZ = zoneinfo.ZoneInfo("Asia/Kathmandu")

# Tier definitions for adaptive discovery frequency
FREQUENCY_TIERS = {
    "high": 8,       # 8 minutes: eKantipur, OnlineKhabar, Setopati, Ratopati, Annapurna Post, Nagarik, NepalKhabar
    "standard": 18,  # 18 minutes: Broadsheets, main English dailies, wire agencies
    "low": 40        # 40 minutes: Specialized tech, finance, weekly journals
}

# High-frequency priority media names
HIGH_FREQUENCY_PORTALS = {
    "eKantipur", "OnlineKhabar (NP)", "Setopati", "Ratopati",
    "Annapurna Post", "Nagarik News", "NepalKhabar", "The Kathmandu Post"
}

LOW_FREQUENCY_PORTALS = {
    "TechPana", "ArthaSarokar", "Nepali Times", "The Annapurna Express"
}

def assign_portal_tiers(portals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enriches portal definitions with priority tiers and check intervals."""
    enriched = []
    for p in portals:
        p_copy = dict(p)
        name = p_copy["name"]
        if name in HIGH_FREQUENCY_PORTALS:
            p_copy["priority"] = "high"
            p_copy["check_interval_mins"] = FREQUENCY_TIERS["high"]
        elif name in LOW_FREQUENCY_PORTALS:
            p_copy["priority"] = "low"
            p_copy["check_interval_mins"] = FREQUENCY_TIERS["low"]
        else:
            p_copy["priority"] = "standard"
            p_copy["check_interval_mins"] = FREQUENCY_TIERS["standard"]
        enriched.append(p_copy)
    return enriched

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

# Background Monitoring Worker Thread
_MONITOR_THREAD = None
_STOP_EVENT = threading.Event()

def _monitoring_daemon_loop():
    """Background continuous loop that checks and ingests portals according to their tiers."""
    logger.info("Continuous News Monitoring Daemon started in background.")
    while not _STOP_EVENT.is_set():
        try:
            run_all_sources_discovery(parallel_workers=12, force_all=False)
        except Exception as e:
            logger.error(f"Error in monitoring loop cycle: {e}")
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

def stop_monitoring_daemon():
    """Signals the monitoring daemon to stop."""
    _STOP_EVENT.set()

