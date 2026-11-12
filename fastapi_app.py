"""
fastapi_app.py
--------------
High-performance, instant-loading FastAPI web service for Nepal Social & Media Monitor.
Serves an Apple-grade, lightweight HTML dashboard with sub-100ms load times,
while running the automated hourly WhatsApp news broadcast daemon in a background thread.
"""

import os
import sys
import time
import json
import threading
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("fastapi_app")

# Project imports
from nepal_news_store import (
    get_stored_articles,
    get_all_source_health,
    get_system_kpis,
    get_recent_broadcast_logs,
    get_stored_indian_articles,
    NEPAL_TZ
)
from whatsapp_auto_worker import get_next_run_time, run_single_broadcast_cycle

app = FastAPI(title="Nepal Social & Media Monitor API", docs_url="/api/docs")

# Enable GZip compression for ultra-fast response transfer
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATUS_TRACKER = {
    "status": "initializing",
    "started_at": datetime.now(NEPAL_TZ).isoformat(),
    "last_run": None,
    "last_summary": None,
    "runs_completed": 0
}

def background_broadcast_loop():
    """Runs 24/7 inside the same container without blocking web requests."""
    logger.info("==================================================================")
    logger.info("FastAPI: Nepal Monitor 24/7 Broadcast Daemon Thread Initialized")
    logger.info("Schedule: 06:00 AM to 10:00 PM NPT (every hour at :00)")
    logger.info("==================================================================")
    STATUS_TRACKER["status"] = "running"

    # Catch-up run on startup
    try:
        logger.info("[Daemon] Running initial container catch-up broadcast cycle...")
        summary = run_single_broadcast_cycle(force=False)
        STATUS_TRACKER["last_run"] = datetime.now(NEPAL_TZ).isoformat()
        STATUS_TRACKER["last_summary"] = summary
        STATUS_TRACKER["runs_completed"] += 1
    except Exception as ex:
        logger.error(f"[Daemon] Startup broadcast error: {ex}")

    while True:
        try:
            now_nepal = datetime.now(NEPAL_TZ)
            next_run = get_next_run_time(now_nepal)
            sleep_secs = max(5, int((next_run - now_nepal).total_seconds()))

            logger.info(
                f"[Daemon] Next broadcast at: {next_run.strftime('%Y-%m-%d %I:%M:%S %p')} NPT "
                f"(sleeping for {sleep_secs}s / {sleep_secs // 60}m)..."
            )
            time.sleep(sleep_secs)

            logger.info("[Daemon] Waking up for scheduled hourly broadcast cycle...")
            summary = run_single_broadcast_cycle(force=False)
            STATUS_TRACKER["last_run"] = datetime.now(NEPAL_TZ).isoformat()
            STATUS_TRACKER["last_summary"] = summary
            STATUS_TRACKER["runs_completed"] += 1
        except Exception as ex:
            logger.error(f"[Daemon] Loop exception: {ex}")
            time.sleep(30)


@app.on_event("startup")
def start_background_daemon():
    thread = threading.Thread(target=background_broadcast_loop, daemon=True)
    thread.start()


@app.get("/api/health")
def api_health():
    return {
        "status": "healthy",
        "worker_status": STATUS_TRACKER["status"],
        "started_at": STATUS_TRACKER["started_at"],
        "current_time_npt": datetime.now(NEPAL_TZ).isoformat(),
        "runs_completed": STATUS_TRACKER["runs_completed"],
        "last_run": STATUS_TRACKER["last_run"],
        "last_summary": STATUS_TRACKER["last_summary"]
    }


@app.get("/api/kpis")
def api_kpis():
    try:
        return get_system_kpis()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/news")
def api_news(
    section: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(60, ge=1, le=500)
):
    try:
        articles = get_stored_articles(source=source, primary_section=section, limit=limit)
        return {"count": len(articles), "articles": articles}
    except Exception as e:
        return {"error": str(e), "articles": []}


@app.get("/api/sources")
def api_sources():
    try:
        health = get_all_source_health()
        return {"count": len(health), "sources": health}
    except Exception as e:
        return {"error": str(e), "sources": []}


@app.get("/api/broadcasts")
def api_broadcasts(limit: int = Query(30, ge=1, le=100)):
    try:
        logs = get_recent_broadcast_logs(limit=limit)
        return {"count": len(logs), "logs": logs}
    except Exception as e:
        return {"error": str(e), "logs": []}


@app.get("/", response_class=HTMLResponse)
def index_page():
    return HTML_DASHBOARD_TEMPLATE


HTML_DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nepal Social & Media Monitor | Real-Time Intelligence</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif; background-color: #0b0f19; color: #f3f4f6; }
    .glass-card { background: rgba(17, 24, 39, 0.7); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .glass-card:hover { border-color: rgba(99, 102, 241, 0.3); }
    .badge { padding: 3px 8px; border-radius: 9999px; font-size: 0.72rem; font-weight: 600; text-transform: uppercase; }
  </style>
</head>
<body class="min-h-screen">
  <!-- Top Navigation -->
  <header class="sticky top-0 z-50 glass-card border-b border-gray-800 bg-[#0b0f19]/90 px-6 py-4 flex flex-wrap items-center justify-between">
    <div class="flex items-center space-x-3">
      <div class="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-rose-500 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/30">🇳🇵</div>
      <div>
        <h1 class="text-lg font-bold tracking-tight text-white flex items-center gap-2">
          Nepal Social & Media Monitor
          <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span class="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-400 animate-pulse"></span>Live
          </span>
        </h1>
        <p class="text-xs text-gray-400">Monitoring 34 Top Nepali Portals, Indian Press & X</p>
      </div>
    </div>
    
    <div class="flex items-center space-x-3 mt-3 sm:mt-0">
      <a href="https://whatsapp.com/channel/0029Vb92VH61iUxbhQ4HpB38" target="_blank" class="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition flex items-center gap-1.5 shadow-md shadow-emerald-600/20">
        <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24"><path d="M.057 24l1.687-6.163c-1.041-1.804-1.588-3.849-1.587-5.946.003-6.556 5.338-11.891 11.893-11.891 3.181.001 6.167 1.24 8.413 3.488 2.245 2.248 3.481 5.236 3.48 8.414-.003 6.557-5.338 11.892-11.893 11.892-1.99-.001-3.951-.5-5.688-1.448l-6.305 1.654zm6.597-3.807c1.676.995 3.276 1.591 5.392 1.592 5.448 0 9.886-4.434 9.889-9.885.002-5.462-4.415-9.89-9.881-9.892-5.452 0-9.887 4.434-9.889 9.884-.001 2.225.651 3.891 1.746 5.634l-.999 3.648 3.742-.981z"/></svg>
        WhatsApp Channel
      </a>
      <button onclick="fetchNews()" class="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition" title="Refresh">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
      </button>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
    <!-- Quick Stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4" id="kpi-cards">
      <div class="glass-card rounded-2xl p-4">
        <p class="text-xs text-gray-400 font-medium">Total Stories Ingested</p>
        <h3 class="text-2xl font-bold text-white mt-1" id="kpi-total">Loading...</h3>
      </div>
      <div class="glass-card rounded-2xl p-4">
        <p class="text-xs text-gray-400 font-medium">Active Portals Monitored</p>
        <h3 class="text-2xl font-bold text-indigo-400 mt-1" id="kpi-portals">34</h3>
      </div>
      <div class="glass-card rounded-2xl p-4">
        <p class="text-xs text-gray-400 font-medium">WhatsApp Broadcasts Sent</p>
        <h3 class="text-2xl font-bold text-emerald-400 mt-1" id="kpi-broadcasts">--</h3>
      </div>
      <div class="glass-card rounded-2xl p-4">
        <p class="text-xs text-gray-400 font-medium">Cloud Daemon Status</p>
        <h3 class="text-2xl font-bold text-emerald-400 mt-1 flex items-center gap-2">
          Active <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300">24/7</span>
        </h3>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none" id="section-filters">
      <button onclick="setFilter('')" class="filter-btn active px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-indigo-600 text-white shadow-sm transition">All Stories</button>
      <button onclick="setFilter('India Section')" class="filter-btn px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-gray-800 text-gray-300 hover:bg-gray-700 transition">India & Bilateral</button>
      <button onclick="setFilter('China Section')" class="filter-btn px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-gray-800 text-gray-300 hover:bg-gray-700 transition">China & BRI</button>
      <button onclick="setFilter('Bangladesh Section')" class="filter-btn px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-gray-800 text-gray-300 hover:bg-gray-700 transition">Bangladesh & Tri-Power</button>
      <button onclick="setFilter('National Politics')" class="filter-btn px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-gray-800 text-gray-300 hover:bg-gray-700 transition">Politics & Governance</button>
      <button onclick="setFilter('Economy & Finance')" class="filter-btn px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-gray-800 text-gray-300 hover:bg-gray-700 transition">Economy & Markets</button>
      <button onclick="setFilter('Security & Defence')" class="filter-btn px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-gray-800 text-gray-300 hover:bg-gray-700 transition">Security & Crime</button>
    </div>

    <!-- News Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5" id="news-container">
      <div class="col-span-full py-16 text-center text-gray-400">Loading real-time news stories...</div>
    </div>
  </main>

  <script>
    let currentSection = '';

    async function loadStats() {
      try {
        const res = await fetch('/api/kpis');
        const data = await res.json();
        document.getElementById('kpi-total').textContent = (data.total_articles || 0).toLocaleString();
        document.getElementById('kpi-broadcasts').textContent = (data.total_broadcasts || 0).toLocaleString();
      } catch (e) { console.error(e); }
    }

    async function fetchNews() {
      const container = document.getElementById('news-container');
      container.innerHTML = '<div class="col-span-full py-12 text-center text-gray-400"><div class="inline-block animate-spin w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full mb-2"></div><p>Fetching latest articles...</p></div>';
      try {
        const url = currentSection ? `/api/news?section=${encodeURIComponent(currentSection)}&limit=90` : '/api/news?limit=90';
        const res = await fetch(url);
        const data = await res.json();
        const articles = data.articles || [];
        
        if (articles.length === 0) {
          container.innerHTML = '<div class="col-span-full py-12 text-center text-gray-400">No recent articles found for this section.</div>';
          return;
        }

        container.innerHTML = articles.map(a => {
          const sec = a.primary_section || 'General';
          const pub = a.relative_time || a.exact_time || 'Just now';
          const src = a.source || 'Nepal Media';
          const title = a.title || 'Untitled Story';
          const link = a.link || '#';
          const summary = a.summary ? a.summary.substring(0, 160) + '...' : '';

          return `
            <article class="glass-card rounded-2xl p-5 flex flex-col justify-between hover:shadow-xl hover:shadow-indigo-500/5 transition">
              <div>
                <div class="flex items-center justify-between gap-2 mb-2.5">
                  <span class="text-xs font-bold text-indigo-400 truncate max-w-[150px]">${src}</span>
                  <span class="text-[11px] text-gray-400 font-medium">${pub}</span>
                </div>
                <h2 class="text-base font-bold text-white hover:text-indigo-300 transition leading-snug line-clamp-3">
                  <a href="${link}" target="_blank" rel="noopener noreferrer">${title}</a>
                </h2>
                ${summary ? `<p class="mt-2.5 text-xs text-gray-400 line-clamp-2 leading-relaxed">${summary}</p>` : ''}
              </div>
              <div class="mt-4 pt-3 border-t border-gray-800/80 flex items-center justify-between">
                <span class="badge bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">${sec}</span>
                <a href="${link}" target="_blank" rel="noopener noreferrer" class="text-xs font-semibold text-gray-300 hover:text-white flex items-center gap-1">
                  Read source
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                </a>
              </div>
            </article>
          `;
        }).join('');
      } catch (e) {
        container.innerHTML = `<div class="col-span-full py-12 text-center text-rose-400">Error loading articles: ${e.message}</div>`;
      }
    }

    function setFilter(sec) {
      currentSection = sec;
      document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('bg-indigo-600', 'text-white');
        btn.classList.add('bg-gray-800', 'text-gray-300');
      });
      event.target.classList.remove('bg-gray-800', 'text-gray-300');
      event.target.classList.add('bg-indigo-600', 'text-white');
      fetchNews();
    }

    loadStats();
    fetchNews();
    setInterval(loadStats, 60000);
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("fastapi_app:app", host="0.0.0.0", port=port, log_level="info")
