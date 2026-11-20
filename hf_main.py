"""
hf_main.py
Headless entrypoint for Hugging Face Docker Space backend.
Runs FastAPI on port 7860 for health checks and orchestrates the
24/7 news monitoring daemon in a supervised background loop.
"""

import os
import sys
import time
import logging
import threading
import traceback
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hf_backend")

_START_TIME = time.time()
_SUPERVISOR_STOP_EVENT = threading.Event()
_SUPERVISOR_THREAD: threading.Thread | None = None
_DAEMON_THREAD: threading.Thread | None = None


def _supervisor_loop():
    """Supervises the news monitor daemon with exponential backoff on unexpected exits."""
    global _DAEMON_THREAD
    backoff = 5.0
    while not _SUPERVISOR_STOP_EVENT.is_set():
        try:
            logger.info("Supervisor starting NepalNewsMonitorDaemon...")
            import nepal_news_scheduler as sched
            _DAEMON_THREAD = sched.start_monitoring_daemon()

            while not _SUPERVISOR_STOP_EVENT.is_set():
                if _DAEMON_THREAD is None or not _DAEMON_THREAD.is_alive():
                    logger.warning("NepalNewsMonitorDaemon thread stopped unexpectedly!")
                    break
                _SUPERVISOR_STOP_EVENT.wait(10.0)

            if _SUPERVISOR_STOP_EVENT.is_set():
                break

            logger.info(f"Supervisor waiting {backoff}s before restarting daemon...")
            _SUPERVISOR_STOP_EVENT.wait(backoff)
            backoff = min(backoff * 1.5, 60.0)
        except Exception as exc:
            logger.error(f"Error in supervisor loop: {exc}\n{traceback.format_exc()}")
            _SUPERVISOR_STOP_EVENT.wait(backoff)
            backoff = min(backoff * 2.0, 120.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _SUPERVISOR_THREAD
    logger.info("Initializing nepal-media-monitor backend worker...")
    _SUPERVISOR_STOP_EVENT.clear()
    _SUPERVISOR_THREAD = threading.Thread(
        target=_supervisor_loop,
        name="BackendDaemonSupervisor",
        daemon=True,
    )
    _SUPERVISOR_THREAD.start()
    yield
    logger.info("Shutting down nepal-media-monitor backend worker...")
    _SUPERVISOR_STOP_EVENT.set()
    try:
        import nepal_news_scheduler as sched
        if hasattr(sched, "_STOP_EVENT") and sched._STOP_EVENT:
            sched._STOP_EVENT.set()
    except Exception:
        pass


app = FastAPI(
    title="Nepal Media Monitor Backend",
    version="2026.11-split",
    lifespan=lifespan,
)


@app.get("/")
def root_endpoint() -> Dict[str, str]:
    return {
        "service": "nepal-media-monitor-backend",
        "status": "running",
    }


@app.get("/health")
def health_endpoint() -> Dict[str, Any]:
    from nepal_summarizer import ENABLE_LOCAL_TRANSLATION_FALLBACK
    daemon_alive = bool(_DAEMON_THREAD and _DAEMON_THREAD.is_alive())
    uptime = int(time.time() - _START_TIME)
    is_healthy = daemon_alive or uptime < 30  # startup grace period
    status_str = "healthy" if is_healthy else "degraded"

    return {
        "status": status_str,
        "daemon_alive": daemon_alive,
        "local_translation_enabled": ENABLE_LOCAL_TRANSLATION_FALLBACK,
        "uptime_seconds": uptime,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run("hf_main:app", host="0.0.0.0", port=port, log_level="info")
