"""
render_worker_server.py
-----------------------
Lightweight HTTP server + 24/7 background broadcast daemon for Render Free Web Service.
Exposes a lightweight HTTP health-check endpoint on the PORT assigned by Render,
while keeping the continuous Nepal Monitor hourly broadcast loop alive 24/7 in a daemon thread.
"""

import os
import sys
import time
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("render_worker_server")

# Import the broadcast loop logic
from whatsapp_auto_worker import get_next_run_time, run_single_broadcast_cycle, NEPAL_TZ

STATUS_TRACKER = {
    "status": "starting",
    "started_at": datetime.now(NEPAL_TZ).isoformat(),
    "last_run": None,
    "last_summary": None,
    "runs_completed": 0
}

def broadcast_daemon_thread():
    """Runs continuously in the background on Render 24/7."""
    logger.info("==================================================================")
    logger.info("Nepal Monitor 24/7 Daemon Thread Started on Render Free Web Service")
    logger.info("Schedule: 06:01 AM to 10:01 PM NPT (every hour at :01)")
    logger.info("Streams: Nepali Media & Indian Press only (X excluded)")
    logger.info("Overnight queueing: 24/7 continuous collection, WhatsApp paused 10 PM - 6 AM")
    logger.info("==================================================================")
    STATUS_TRACKER["status"] = "running"

    # Run startup collection and catch-up cycle upon container boot
    try:
        logger.info("Performing container startup queue collection & catch-up scan...")
        summary = run_single_broadcast_cycle(force=False)
        STATUS_TRACKER["last_run"] = datetime.now(NEPAL_TZ).isoformat()
        STATUS_TRACKER["last_summary"] = summary
        STATUS_TRACKER["runs_completed"] += 1
    except Exception as ex:
        logger.error(f"Error during startup broadcast cycle: {ex}")

    while True:
        try:
            now_nepal = datetime.now(NEPAL_TZ)
            next_run = get_next_run_time(now_nepal)
            sleep_secs = max(5, int((next_run - now_nepal).total_seconds()))

            logger.info(
                f"[Render Worker] Next WhatsApp cycle at: {next_run.strftime('%Y-%m-%d %I:%M:%S %p')} NPT "
                f"(sleeping for {sleep_secs}s / {sleep_secs // 60}m)..."
            )
            time.sleep(sleep_secs)

            logger.info("[Render Worker] Waking up for scheduled hourly cycle at minute :01...")
            summary = run_single_broadcast_cycle(force=False)
            STATUS_TRACKER["last_run"] = datetime.now(NEPAL_TZ).isoformat()
            STATUS_TRACKER["last_summary"] = summary
            STATUS_TRACKER["runs_completed"] += 1
        except Exception as ex:
            logger.error(f"[Render Worker] Unhandled exception in loop: {ex}")
            time.sleep(30)


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        import json
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        payload = {
            "service": "nepal-social-monitor-worker",
            "uptime_status": STATUS_TRACKER["status"],
            "started_at": STATUS_TRACKER["started_at"],
            "current_time_npt": datetime.now(NEPAL_TZ).isoformat(),
            "runs_completed": STATUS_TRACKER["runs_completed"],
            "last_run": STATUS_TRACKER["last_run"],
            "last_summary": STATUS_TRACKER["last_summary"]
        }
        self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        # Silence default access logs to keep terminal output clean for news dispatches
        pass


def main():
    port = int(os.environ.get("PORT", 10000))
    # 1. Start the 24/7 background worker thread
    worker_t = threading.Thread(target=broadcast_daemon_thread, daemon=True)
    worker_t.start()

    # 2. Start HTTP server on Render's assigned port to keep the web service alive
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Render HTTP Health Server listening on 0.0.0.0:{port}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down Render worker server...")
        server.server_close()

if __name__ == "__main__":
    main()

