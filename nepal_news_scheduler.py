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
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple, Callable
from nepal_config import format_exc

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

def _cache_resource_if_available(fn):
    if st is not None and hasattr(st, "cache_resource"):
        return st.cache_resource(fn)
    return fn

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
        articles = fetch_single_portal(
            source_config,
            now_npt,
            max_entries=max_articles,
            persist=False,
            raise_on_error=True,
        )
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
        err_msg = format_exc(e, limit=300)
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

def _normalize_to_utc_dt(raw_val: Any) -> Optional[datetime.datetime]:
    """Normalizes a datetime object or SQL/ISO timestamp string to timezone-aware UTC."""
    if isinstance(raw_val, datetime.datetime):
        if raw_val.tzinfo is not None:
            return raw_val.astimezone(datetime.timezone.utc)
        return raw_val.replace(tzinfo=datetime.timezone.utc)
    if isinstance(raw_val, str):
        s = raw_val.strip()
        if not s:
            return None
        try:
            norm = s.replace("Z", "+00:00")
            if len(norm) >= 3 and norm[-3] in ("+", "-") and norm[-2:].isdigit():
                norm = f"{norm}:00"
            dt = datetime.datetime.fromisoformat(norm)
            return dt.astimezone(datetime.timezone.utc) if dt.tzinfo is not None else dt.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            try:
                return datetime.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
            except Exception:
                return None
    return None


def run_all_sources_discovery(
    parallel_workers: int = 15,
    force_all: bool = False,
    cycle_timeout_secs: Optional[float] = 55.0,
) -> Dict[str, Any]:
    """
    Runs an ingestion cycle across all enabled Nepali media outlets.
    If force_all=False, only polls sources whose check_interval_mins have elapsed.
    """
    import concurrent.futures
    from nepal_fetcher import TOP_NEPAL_NEWS_PORTALS

    if len(TOP_NEPAL_NEWS_PORTALS) >= 10:
        try:
            register_portal_sources(TOP_NEPAL_NEWS_PORTALS)
        except Exception:
            pass

    portal_map = {p["name"]: p for p in TOP_NEPAL_NEWS_PORTALS}
    health_rows = get_all_source_health()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

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

        # Check interval using timezone-aware UTC timestamps (self-healing future NPT/UTC clock skew)
        interval_mins = h.get("check_interval_mins", 15)
        last_disc = h.get("last_discovery_time")
        if not last_disc:
            portals_to_run.append(portal_cfg)
            continue

        try:
            last_dt_utc = _normalize_to_utc_dt(last_disc)
            if last_dt_utc is None:
                portals_to_run.append(portal_cfg)
                continue
            elapsed = (now_utc - last_dt_utc).total_seconds() / 60.0
            if elapsed >= interval_mins or elapsed < -1.0:
                portals_to_run.append(portal_cfg)
        except Exception:
            portals_to_run.append(portal_cfg)

    if not portals_to_run:
        logger.info("All sources are currently up-to-date within their configured intervals.")
        return {"total_checked": 0, "total_ingested": 0, "results": {}}

    logger.info(f"Starting scheduled discovery for {len(portals_to_run)} of {len(TOP_NEPAL_NEWS_PORTALS)} portals...")
    results = {}
    total_ingested = 0

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=parallel_workers)
    try:
        future_map = {executor.submit(run_single_source_discovery, p): p["name"] for p in portals_to_run}
        try:
            for future in concurrent.futures.as_completed(future_map, timeout=cycle_timeout_secs):
                src_name = future_map[future]
                try:
                    res = future.result(timeout=1.0)
                    results[src_name] = res
                    total_ingested += res.get("ingested", 0)
                except Exception as e:
                    results[src_name] = {"status": "ERROR", "error": format_exc(e)}
        except concurrent.futures.TimeoutError:
            timed_out = [name for name in future_map.values() if name not in results]
            for name in timed_out:
                results[name] = {
                    "status": "TIMEOUT",
                    "error": f"Discovery timed out after {int(cycle_timeout_secs or 0)}s",
                }
            if timed_out:
                logger.warning(
                    f"Scheduled discovery reached {cycle_timeout_secs}s budget; deferred {len(timed_out)} slow portal(s): {', '.join(timed_out[:6])}"
                )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

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

    batch_fetch_full_content(target_batch, max_workers=12, summarize_english=False)
    logger.info(f"Full-content backfill completed for {len(target_batch)} articles (on-demand AI briefs enabled).")
    return len(target_batch)


# Background Monitoring Worker Thread
_DAEMON_CODE_VERSION = "2026-11-19-v2"
_MONITOR_THREAD = None
_STOP_EVENT = threading.Event()
_LAST_X_SCAN_TIME = 0.0
_LAST_INDIAN_SCAN_TIME = 0.0
X_SCAN_INTERVAL_SECS = 15 * 60  # Automatically scan X every 15 minutes
INDIAN_SCAN_INTERVAL_SECS = 15 * 60  # Automatically poll 18 Indian outlets every 15 minutes

_MANUAL_SYNC_LOCK = threading.Lock()
_INGEST_RUN_LOCK = threading.Lock()
_ALL_SYNC_STREAMS = ("nepali", "indian", "x")
_MANUAL_SYNC_STATE: Dict[str, Any] = {
    "running": False,
    "started_at": 0.0,
    "finished_at": 0.0,
    "elapsed_secs": 0.0,
    "completed_seq": 0,
    "stream_seqs": {s: 0 for s in _ALL_SYNC_STREAMS},
    "pipelines": {
        s: {"status": "idle", "count": 0, "elapsed_secs": 0.0, "error": ""}
        for s in _ALL_SYNC_STREAMS
    },
    "results": {},
    "errors": {},
}


def get_manual_sync_status() -> Dict[str, Any]:
    """Returns a thread-safe snapshot of concurrent manual refresh and per-pipeline progress."""
    with _MANUAL_SYNC_LOCK:
        snap = dict(_MANUAL_SYNC_STATE)
        snap["results"] = dict(_MANUAL_SYNC_STATE["results"])
        snap["errors"] = dict(_MANUAL_SYNC_STATE["errors"])
        snap["stream_seqs"] = dict(_MANUAL_SYNC_STATE["stream_seqs"])
        snap["pipelines"] = {k: dict(v) for k, v in _MANUAL_SYNC_STATE["pipelines"].items()}
        return snap


def _run_concurrent_ingest_pipelines(
    include_nepali: bool = True,
    include_indian: bool = True,
    include_x: bool = True,
    nepali_workers: int = 12,
    indian_workers: int = 8,
    pipeline_timeout_secs: float = 90.0,
    on_pipeline_done: Optional[Any] = None,
) -> Tuple[Dict[str, int], Dict[str, str]]:
    """
    Runs Nepali Media, Indian Press, and X ingestion pipelines concurrently with
    isolated error handling, per-pipeline completion callbacks, and hard timeouts.
    """
    tasks: Dict[str, Any] = {}
    results: Dict[str, int] = {}
    errors: Dict[str, str] = {}
    started_times: Dict[str, float] = {}

    def _run_nepali() -> int:
        from nepal_fetcher import fetch_top_nepal_media
        items = fetch_top_nepal_media(max_workers=nepali_workers, force_refresh=True, return_all_stored=False)
        return len(items)

    def _run_indian() -> int:
        from nepal_fetcher import fetch_nepal_in_indian_media
        items = fetch_nepal_in_indian_media(max_workers=indian_workers, force_refresh=True, return_all_stored=False)
        return len(items)

    def _run_x() -> int:
        from nepal_x_scanner import scan_popular_nepal_x_posts
        items = scan_popular_nepal_x_posts(force_refresh=True)
        return len(items)

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)
    try:
        t_submit = time.time()
        if include_nepali:
            started_times["nepali"] = t_submit
            tasks["nepali"] = pool.submit(_run_nepali)
        if include_indian:
            started_times["indian"] = t_submit
            tasks["indian"] = pool.submit(_run_indian)
        if include_x:
            started_times["x"] = t_submit
            tasks["x"] = pool.submit(_run_x)

        future_to_name = {fut: name for name, fut in tasks.items()}
        done_names = set()
        try:
            for fut in concurrent.futures.as_completed(future_to_name, timeout=pipeline_timeout_secs):
                name = future_to_name[fut]
                done_names.add(name)
                elapsed = round(time.time() - started_times.get(name, t_submit), 2)
                try:
                    cnt = int(fut.result(timeout=1) or 0)
                    results[name] = cnt
                    if on_pipeline_done is not None:
                        on_pipeline_done(name, "done", cnt, elapsed, "")
                except Exception as exc:
                    err_str = format_exc(exc)
                    errors[name] = err_str
                    logger.warning(f"Pipeline '{name}' failed during sync: {err_str}")
                    if on_pipeline_done is not None:
                        on_pipeline_done(name, "error", 0, elapsed, err_str)
        except concurrent.futures.TimeoutError:
            for fut, name in future_to_name.items():
                if name not in done_names:
                    err_str = f"Timed out after {int(pipeline_timeout_secs)}s"
                    errors[name] = err_str
                    logger.warning(f"Pipeline '{name}' timed out after {pipeline_timeout_secs}s")
                    if on_pipeline_done is not None:
                        elapsed = round(time.time() - started_times.get(name, t_submit), 2)
                        on_pipeline_done(name, "timeout", 0, elapsed, err_str)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    return results, errors


def _invalidate_store_caches_after_sync(targets: Optional[Tuple[str, ...]] = None) -> None:
    """Selectively clears backend store caches only for the pipeline(s) that completed."""
    target_set = set(targets) if targets else set(_ALL_SYNC_STREAMS)
    try:
        import nepal_news_store as store
        if "nepali" in target_set and hasattr(store, "_clear_health_caches"):
            store._clear_health_caches()
        if "x" in target_set and hasattr(store, "get_x_account_kpis") and hasattr(store.get_x_account_kpis, "clear"):
            store.get_x_account_kpis.clear()
    except Exception:
        pass


def _manual_sync_worker(target_streams: Tuple[str, ...]) -> None:
    t0 = time.time()
    results: Dict[str, int] = {}
    errors: Dict[str, str] = {}
    acquired = _INGEST_RUN_LOCK.acquire(timeout=1.0)

    def _on_stream_done(name: str, status: str, count: int, elapsed: float, err: str) -> None:
        if status == "done":
            _invalidate_store_caches_after_sync(targets=(name,))
        with _MANUAL_SYNC_LOCK:
            _MANUAL_SYNC_STATE["pipelines"][name] = {
                "status": status,
                "count": int(count),
                "elapsed_secs": elapsed,
                "error": err,
            }
            if status == "done":
                _MANUAL_SYNC_STATE["results"][name] = int(count)
                _MANUAL_SYNC_STATE["errors"].pop(name, None)
                _MANUAL_SYNC_STATE["stream_seqs"][name] = int(_MANUAL_SYNC_STATE["stream_seqs"].get(name, 0)) + 1
            else:
                _MANUAL_SYNC_STATE["errors"][name] = err

    try:
        target_set = set(target_streams)
        results, errors = _run_concurrent_ingest_pipelines(
            include_nepali=("nepali" in target_set),
            include_indian=("indian" in target_set),
            include_x=("x" in target_set),
            nepali_workers=12,
            indian_workers=12,
            pipeline_timeout_secs=90.0,
            on_pipeline_done=_on_stream_done,
        )
    except Exception as exc:
        errors["sync"] = format_exc(exc)
    finally:
        if acquired:
            _INGEST_RUN_LOCK.release()
        with _MANUAL_SYNC_LOCK:
            _MANUAL_SYNC_STATE["running"] = False
            _MANUAL_SYNC_STATE["finished_at"] = time.time()
            _MANUAL_SYNC_STATE["elapsed_secs"] = round(_MANUAL_SYNC_STATE["finished_at"] - t0, 2)
            _MANUAL_SYNC_STATE["completed_seq"] = int(_MANUAL_SYNC_STATE["completed_seq"]) + 1
            for k, v in results.items():
                _MANUAL_SYNC_STATE["results"][k] = v
            for k, v in errors.items():
                _MANUAL_SYNC_STATE["errors"][k] = v


def trigger_manual_sync_async(targets: Optional[List[str]] = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Launches a non-blocking concurrent refresh across requested sources ('nepali', 'indian', 'x').
    Supports independent retry of failed sources and prevents duplicate/overlapping runs.
    """
    req_streams = tuple(s for s in (targets or list(_ALL_SYNC_STREAMS)) if s in _ALL_SYNC_STREAMS) or _ALL_SYNC_STREAMS
    with _MANUAL_SYNC_LOCK:
        now_ts = time.time()
        if _MANUAL_SYNC_STATE["running"] and (now_ts - float(_MANUAL_SYNC_STATE["started_at"])) < 120.0:
            snap = dict(_MANUAL_SYNC_STATE)
            snap["results"] = dict(_MANUAL_SYNC_STATE["results"])
            snap["errors"] = dict(_MANUAL_SYNC_STATE["errors"])
            snap["stream_seqs"] = dict(_MANUAL_SYNC_STATE["stream_seqs"])
            snap["pipelines"] = {k: dict(v) for k, v in _MANUAL_SYNC_STATE["pipelines"].items()}
            return False, snap
        _MANUAL_SYNC_STATE["running"] = True
        _MANUAL_SYNC_STATE["started_at"] = now_ts
        for s in req_streams:
            _MANUAL_SYNC_STATE["errors"].pop(s, None)
            _MANUAL_SYNC_STATE["pipelines"][s] = {
                "status": "running", "count": 0, "elapsed_secs": 0.0, "error": "",
            }
        snap = dict(_MANUAL_SYNC_STATE)
        snap["results"] = dict(_MANUAL_SYNC_STATE["results"])
        snap["errors"] = dict(_MANUAL_SYNC_STATE["errors"])
        snap["stream_seqs"] = dict(_MANUAL_SYNC_STATE["stream_seqs"])
        snap["pipelines"] = {k: dict(v) for k, v in _MANUAL_SYNC_STATE["pipelines"].items()}

    t = threading.Thread(target=_manual_sync_worker, args=(req_streams,), name="NepalManualSyncWorker", daemon=True)
    t.start()
    return True, snap


def _monitoring_daemon_loop(stop_ev: Optional[threading.Event] = None):
    """Background continuous loop that checks and ingests Nepali portals, Indian press, and X posts."""
    global _LAST_X_SCAN_TIME, _LAST_INDIAN_SCAN_TIME
    ev = stop_ev if stop_ev is not None else _STOP_EVENT
    logger.info("Continuous News Monitoring Daemon started in background (15s startup delay).")
    # Delay first cycle so initial UI queries get uncontested bandwidth
    if ev.wait(15.0):
        return
    try:
        from nepal_config import TOP_NEPAL_NEWS_PORTALS
        register_portal_sources(TOP_NEPAL_NEWS_PORTALS)
    except Exception:
        pass
    while not ev.is_set():
        # Skip automated cycle if a manual sync is actively running to avoid overlapping ingestion
        if _INGEST_RUN_LOCK.acquire(blocking=False):
            try:
                now_sec = time.time()
                run_indian = (now_sec - _LAST_INDIAN_SCAN_TIME) >= INDIAN_SCAN_INTERVAL_SECS
                run_x = (now_sec - _LAST_X_SCAN_TIME) >= X_SCAN_INTERVAL_SECS

                def _run_scheduled_nepali():
                    return run_all_sources_discovery(parallel_workers=10, force_all=False, cycle_timeout_secs=45.0)

                pool = concurrent.futures.ThreadPoolExecutor(max_workers=3)
                try:
                    f_np = pool.submit(_run_scheduled_nepali)
                    fut_meta: Dict[concurrent.futures.Future, Tuple[str, Optional[Callable[[], None]]]] = {
                        f_np: ("Nepali", None),
                    }
                    if run_indian:
                        from nepal_config import DEFAULT_NEPAL_RELEVANCE_THRESHOLD
                        from nepal_fetcher import fetch_nepal_in_indian_media
                        def _mark_indian():
                            global _LAST_INDIAN_SCAN_TIME
                            _LAST_INDIAN_SCAN_TIME = time.time()
                        fut_meta[
                            pool.submit(
                                fetch_nepal_in_indian_media,
                                10,
                                DEFAULT_NEPAL_RELEVANCE_THRESHOLD,
                                False,
                                True,
                                False,
                            )
                        ] = ("Indian Press", _mark_indian)
                    if run_x:
                        from nepal_x_scanner import scan_popular_nepal_x_posts
                        def _mark_x():
                            global _LAST_X_SCAN_TIME
                            _LAST_X_SCAN_TIME = time.time()
                        fut_meta[pool.submit(scan_popular_nepal_x_posts, True)] = ("X", _mark_x)

                    done_futs = set()
                    stream_key_map = {"Nepali": "nepali", "Indian Press": "indian", "X": "x"}
                    try:
                        for fut in concurrent.futures.as_completed(fut_meta, timeout=90.0):
                            done_futs.add(fut)
                            label, on_done = fut_meta[fut]
                            try:
                                res_val = fut.result(timeout=0.5)
                                if on_done is not None:
                                    on_done()
                                s_key = stream_key_map.get(label)
                                has_updates = (
                                    (isinstance(res_val, dict) and int(res_val.get("total_ingested", 0) or 0) > 0)
                                    or (isinstance(res_val, list) and len(res_val) > 0)
                                )
                                if s_key and has_updates:
                                    _invalidate_store_caches_after_sync(targets=(s_key,))
                                    with _MANUAL_SYNC_LOCK:
                                        _MANUAL_SYNC_STATE["stream_seqs"][s_key] = int(_MANUAL_SYNC_STATE["stream_seqs"].get(s_key, 0)) + 1
                            except concurrent.futures.TimeoutError:
                                logger.warning(f"Monitoring loop {label} cycle timed out after 90s; continuing.")
                            except Exception as e:
                                err_msg = format_exc(e)
                                if "shutdown" in err_msg.lower():
                                    return
                                logger.error(f"Error in background {label} scan cycle: {err_msg}")
                    except concurrent.futures.TimeoutError:
                        for fut, (label, _cb) in fut_meta.items():
                            if fut not in done_futs:
                                logger.warning(f"Monitoring loop {label} cycle timed out after 90s; continuing.")
                finally:
                    pool.shutdown(wait=False, cancel_futures=True)
            finally:
                _INGEST_RUN_LOCK.release()

        # Sleep for 60 seconds between cycle evaluations
        ev.wait(60.0)

@_cache_resource_if_available
def start_monitoring_daemon(code_version: str = _DAEMON_CODE_VERSION):
    """Starts the continuous news monitoring worker in a background daemon thread."""
    global _MONITOR_THREAD, _STOP_EVENT
    if _MONITOR_THREAD and _MONITOR_THREAD.is_alive() and not _STOP_EVENT.is_set():
        return _MONITOR_THREAD
    _STOP_EVENT = threading.Event()
    _MONITOR_THREAD = threading.Thread(
        target=_monitoring_daemon_loop,
        args=(_STOP_EVENT,),
        name="NepalNewsMonitorDaemon",
        daemon=True,
    )
    _MONITOR_THREAD.start()
    logger.info(f"Launched NepalNewsMonitorDaemon thread ({code_version}).")
    return _MONITOR_THREAD


