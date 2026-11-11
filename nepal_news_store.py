"""
nepal_news_store.py
Persistent, thread-safe, SQLite-backed news intelligence store and source-monitoring engine.
Guarantees idempotent ingestion, canonical deduplication, per-source health tracking,
discovery checkpoints, and metric aggregation for all 34 Nepali Media Portals.
"""

import os
import sqlite3
import hashlib
import json
import logging
import datetime
import zoneinfo
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple

NEPAL_TZ = zoneinfo.ZoneInfo("Asia/Kathmandu")

logger = logging.getLogger("nepal_news_store")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

DB_PATH = os.path.join(os.path.dirname(__file__), "nepal_news_store.db")

def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn

def normalize_canonical_url(url: str) -> str:
    """Normalizes URL by stripping UTM parameters, session tokens, and trailing slashes."""
    if not url or not url.startswith("http"):
        return url or ""
    try:
        parsed = urllib.parse.urlparse(url)
        # Filter tracking parameters
        query_params = urllib.parse.parse_qsl(parsed.query)
        clean_params = [
            (k, v) for k, v in query_params
            if not k.lower().startswith("utm_") and k.lower() not in ("ref", "fbclid", "gclid", "source", "pk_campaign")
        ]
        clean_query = urllib.parse.urlencode(clean_params)
        path = parsed.path.rstrip("/")
        normalized = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            clean_query,
            ""  # Strip fragment
        ))
        return normalized
    except Exception:
        return url.strip().rstrip("/")

def generate_canonical_id(source: str, url: str, title: str) -> str:
    """Generates an unambiguous, reproducible hash representing an article record."""
    norm_url = normalize_canonical_url(url)
    norm_title = " ".join(title.lower().split()) if title else ""
    raw = f"{norm_url}::{norm_title}" if norm_url else f"{source}::{norm_title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

def init_news_store():
    """Initializes tables, indexes, and source registry."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Sources Registry Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                url TEXT NOT NULL,
                alt_urls TEXT,
                lang TEXT NOT NULL DEFAULT 'Nepali',
                category TEXT NOT NULL DEFAULT 'General News',
                priority TEXT NOT NULL DEFAULT 'standard',
                check_interval_mins INTEGER NOT NULL DEFAULT 15,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Source Health and Checkpoint Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_health (
                source_name TEXT PRIMARY KEY,
                last_discovery_time TIMESTAMP,
                last_ingestion_time TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'operational',
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                total_discovered INTEGER NOT NULL DEFAULT 0,
                total_ingested INTEGER NOT NULL DEFAULT 0,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                failed_retrievals INTEGER NOT NULL DEFAULT 0,
                latest_article_pub_dt TIMESTAMP,
                latest_article_title TEXT,
                latest_article_link TEXT,
                last_error_message TEXT,
                discovery_latency_avg_secs REAL NOT NULL DEFAULT 0.0,
                last_checkpoint TEXT,
                FOREIGN KEY (source_name) REFERENCES sources(name)
            )
        """)

        # 3. Canonical Articles Store Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                canonical_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                headline_english TEXT,
                link TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                summary TEXT,
                full_content TEXT,
                published_dt TIMESTAMP NOT NULL,
                relative_time TEXT,
                exact_time TEXT,
                language TEXT NOT NULL DEFAULT 'Nepali',
                portal_category TEXT,
                primary_section TEXT NOT NULL,
                sections TEXT NOT NULL,
                secondary_tags TEXT NOT NULL,
                classification_confidence REAL NOT NULL DEFAULT 0.85,
                low_confidence INTEGER NOT NULL DEFAULT 0,
                is_viral INTEGER NOT NULL DEFAULT 0,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. Discovery Activity Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovery_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                discovered_count INTEGER NOT NULL DEFAULT 0,
                ingested_count INTEGER NOT NULL DEFAULT 0,
                duplicates_count INTEGER NOT NULL DEFAULT 0,
                latency_secs REAL NOT NULL DEFAULT 0.0,
                status TEXT NOT NULL DEFAULT 'OK',
                error_msg TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Broadcast distribution logs for WhatsApp Group & Channel
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_key TEXT NOT NULL,
                source_name TEXT NOT NULL,
                stream_type TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'delivered',
                message_id TEXT,
                attempts INTEGER DEFAULT 1,
                channel_id TEXT,
                dispatched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_msg TEXT
            )
        """)

        # Central archive for all scraped Indian Media articles (retains relevant, borderline, and excluded items)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS indian_media_articles (
                canonical_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                headline_english TEXT,
                link TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                summary TEXT,
                full_content TEXT,
                published_dt TIMESTAMP NOT NULL,
                relative_time TEXT,
                exact_time TEXT,
                language TEXT NOT NULL DEFAULT 'English',
                primary_section TEXT NOT NULL DEFAULT 'India Section',
                sections TEXT NOT NULL DEFAULT '["India Section"]',
                secondary_tags TEXT NOT NULL DEFAULT '[]',
                classification_confidence REAL NOT NULL DEFAULT 0.85,
                nepal_relevance_score REAL NOT NULL DEFAULT 0.0,
                relevance_status TEXT NOT NULL DEFAULT 'excluded',
                relevance_reason TEXT,
                nepal_dimensions TEXT,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for fast querying, filtering, and metrics
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_art_published ON articles(published_dt DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_art_source ON articles(source);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_art_primary ON articles(primary_section);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_art_ingested ON articles(ingested_at DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_source_time ON discovery_logs(source_name, timestamp DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bcast_key ON broadcast_logs(item_key);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bcast_src ON broadcast_logs(source_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bcast_time ON broadcast_logs(dispatched_at DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ind_rel_status ON indian_media_articles(relevance_status, published_dt DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ind_rel_score ON indian_media_articles(nepal_relevance_score DESC);")

        conn.commit()

# Ensure database tables exist on module load
init_news_store()

def register_portal_sources(portals_list: List[Dict[str, Any]]):
    """Syncs the canonical 34 portal list into the sources registry table."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for p in portals_list:
            name = p["name"]
            stype = p.get("type", "rss")
            url = p.get("url", "")
            alt_urls = json.dumps(p.get("alt_urls", []))
            lang = p.get("lang", "Nepali")
            cat = p.get("category", "General News")
            priority = p.get("priority", "standard")
            interval = p.get("check_interval_mins", 15)

            cursor.execute("""
                INSERT INTO sources (name, type, url, alt_urls, lang, category, priority, check_interval_mins, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(name) DO UPDATE SET
                    type=excluded.type,
                    url=excluded.url,
                    lang=excluded.lang,
                    category=excluded.category
            """, (name, stype, url, alt_urls, lang, cat, priority, interval))

            # Initialize health row if not present
            cursor.execute("""
                INSERT OR IGNORE INTO source_health (source_name, status)
                VALUES (?, 'operational')
            """, (name,))
        conn.commit()

def upsert_article(article: Dict[str, Any], conn: sqlite3.Connection = None) -> Tuple[bool, bool]:
    """
    Idempotently upserts an article into the store.
    Returns: (is_new, is_updated)
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        source = article.get("source", "Unknown")
        title = (article.get("title") or "").strip()
        link = article.get("link", "#")
        canonical_url = normalize_canonical_url(link)
        canonical_id = article.get("canonical_id") or generate_canonical_id(source, canonical_url, title)

        # Parse or format dates
        pub_dt = article.get("published_dt")
        if isinstance(pub_dt, datetime.datetime):
            pub_dt_str = pub_dt.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(pub_dt, str):
            pub_dt_str = pub_dt
        else:
            pub_dt_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        headline_en = article.get("headline_english", "")
        summary = article.get("summary", "")
        full_content = article.get("full_content", "") or summary
        relative_time = article.get("relative_time", "Recent")
        exact_time = article.get("exact_time", "")
        lang = article.get("language", "Nepali")
        portal_category = article.get("portal_category", "General News")
        primary_section = article.get("primary_section") or article.get("structured_category", "Nepal – Others")
        
        sections = article.get("sections") or [primary_section]
        sections_json = json.dumps(sections if isinstance(sections, list) else [sections])

        sec_tags = article.get("secondary_tags") or []
        sec_tags_json = json.dumps(sec_tags if isinstance(sec_tags, list) else [sec_tags])

        confidence = float(article.get("classification_confidence", 0.85))
        low_confidence = 1 if article.get("low_confidence") else 0
        is_viral = 1 if article.get("is_viral") else 0

        cursor = conn.cursor()
        # Check existing
        cursor.execute("SELECT canonical_id, title, full_content FROM articles WHERE canonical_id = ?", (canonical_id,))
        existing = cursor.fetchone()

        if existing is None:
            # Insert new record
            cursor.execute("""
                INSERT INTO articles (
                    canonical_id, source, title, headline_english, link, canonical_url,
                    summary, full_content, published_dt, relative_time, exact_time,
                    language, portal_category, primary_section, sections, secondary_tags,
                    classification_confidence, low_confidence, is_viral, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                canonical_id, source, title, headline_en, link, canonical_url,
                summary, full_content, pub_dt_str, relative_time, exact_time,
                lang, portal_category, primary_section, sections_json, sec_tags_json,
                confidence, low_confidence, is_viral
            ))
            return True, False
        else:
            # Check if updated content
            old_len = len(existing["full_content"] or "")
            new_len = len(full_content or "")
            if new_len > old_len + 40:
                cursor.execute("""
                    UPDATE articles SET
                        title = ?, summary = ?, full_content = ?, relative_time = ?,
                        sections = ?, secondary_tags = ?, classification_confidence = ?, low_confidence = ?
                    WHERE canonical_id = ?
                """, (title, summary, full_content, relative_time, sections_json, sec_tags_json, confidence, low_confidence, canonical_id))
                return False, True
            return False, False
    finally:
        if should_close:
            conn.commit()
            conn.close()

def batch_upsert_articles(articles: List[Dict[str, Any]], source_name: str, latency_secs: float = 0.0) -> Dict[str, int]:
    """
    Ingests a list of articles for a source, tracking duplicates, new items, and health.
    """
    if not articles:
        return {"discovered": 0, "ingested": 0, "duplicates": 0, "updated": 0}

    discovered = len(articles)
    ingested = 0
    duplicates = 0
    updated = 0
    latest_pub = None
    latest_title = None
    latest_link = None

    with get_db_connection() as conn:
        for a in articles:
            is_new, is_up = upsert_article(a, conn=conn)
            if is_new:
                ingested += 1
            elif is_up:
                updated += 1
            else:
                duplicates += 1

            # Track latest pub date
            pdt = a.get("published_dt")
            if isinstance(pdt, datetime.datetime):
                if latest_pub is None or pdt > latest_pub:
                    latest_pub = pdt
                    latest_title = a.get("title")
                    latest_link = a.get("link")

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        latest_pub_str = latest_pub.strftime("%Y-%m-%d %H:%M:%S") if latest_pub else None

        # Update source health
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE source_health SET
                last_discovery_time = ?,
                last_ingestion_time = CASE WHEN ? > 0 THEN ? ELSE last_ingestion_time END,
                status = 'operational',
                consecutive_failures = 0,
                total_discovered = total_discovered + ?,
                total_ingested = total_ingested + ?,
                duplicate_count = duplicate_count + ?,
                latest_article_pub_dt = COALESCE(?, latest_article_pub_dt),
                latest_article_title = COALESCE(?, latest_article_title),
                latest_article_link = COALESCE(?, latest_article_link),
                last_error_message = NULL,
                discovery_latency_avg_secs = (discovery_latency_avg_secs * 0.7) + (? * 0.3)
            WHERE source_name = ?
        """, (
            now_str, ingested, now_str,
            discovered, ingested, duplicates,
            latest_pub_str, latest_title, latest_link,
            latency_secs, source_name
        ))

        # Record activity log
        cursor.execute("""
            INSERT INTO discovery_logs (source_name, discovered_count, ingested_count, duplicates_count, latency_secs, status)
            VALUES (?, ?, ?, ?, ?, 'OK')
        """, (source_name, discovered, ingested, duplicates, latency_secs))

        conn.commit()

    return {
        "discovered": discovered,
        "ingested": ingested,
        "duplicates": duplicates,
        "updated": updated
    }

def record_source_error(source_name: str, error_msg: str, latency_secs: float = 0.0):
    """Records an error for a portal and adjusts health state (operational -> degraded -> failing)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("SELECT consecutive_failures FROM source_health WHERE source_name = ?", (source_name,))
        row = cursor.fetchone()
        consec = (row["consecutive_failures"] if row else 0) + 1

        # State transition: 1-2 failures = degraded, >= 3 failures = failing
        new_status = "failing" if consec >= 3 else "degraded"

        cursor.execute("""
            UPDATE source_health SET
                last_discovery_time = ?,
                status = ?,
                consecutive_failures = ?,
                failed_retrievals = failed_retrievals + 1,
                last_error_message = ?
            WHERE source_name = ?
        """, (now_str, new_status, consec, error_msg, source_name))

        cursor.execute("""
            INSERT INTO discovery_logs (source_name, discovered_count, ingested_count, duplicates_count, latency_secs, status, error_msg)
            VALUES (?, 0, 0, 0, ?, ?, ?)
        """, (source_name, latency_secs, new_status.upper(), error_msg))

        conn.commit()

def get_all_source_health() -> List[Dict[str, Any]]:
    """Returns comprehensive health, volume counts, and checkpoints for all configured portals."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                s.name, s.type, s.url, s.lang, s.category, s.priority, s.check_interval_mins, s.enabled,
                h.last_discovery_time, h.last_ingestion_time, h.status, h.consecutive_failures,
                h.total_discovered, h.total_ingested, h.duplicate_count, h.failed_retrievals,
                h.latest_article_pub_dt, h.latest_article_title, h.latest_article_link,
                h.last_error_message, h.discovery_latency_avg_secs,
                (SELECT COUNT(*) FROM articles a WHERE a.source = s.name AND a.published_dt >= datetime('now', '-1 hour')) as count_1h,
                (SELECT COUNT(*) FROM articles a WHERE a.source = s.name AND a.published_dt >= datetime('now', '-24 hour')) as count_24h,
                (SELECT COUNT(*) FROM articles a WHERE a.source = s.name AND a.published_dt >= datetime('now', '-7 day')) as count_7d,
                (SELECT COUNT(*) FROM articles a WHERE a.source = s.name) as count_total
            FROM sources s
            LEFT JOIN source_health h ON s.name = h.source_name
            ORDER BY s.enabled DESC, s.name ASC
        """)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def get_stored_articles(
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    source: Optional[str] = None,
    primary_section: Optional[str] = None,
    limit: int = 1500
) -> List[Dict[str, Any]]:
    """Retrieves articles from SQLite store filtered by time window, source, or section."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM articles WHERE 1=1"
        params = []

        if start_dt:
            query += " AND published_dt >= ?"
            params.append(start_dt.strftime("%Y-%m-%d %H:%M:%S"))
        if end_dt:
            query += " AND published_dt <= ?"
            params.append(end_dt.strftime("%Y-%m-%d %H:%M:%S"))
        if source and source != "All Portals" and not source.startswith("All Portals"):
            query += " AND source = ?"
            params.append(source)
        if primary_section and not primary_section.startswith("🌐 All"):
            query += " AND (primary_section = ? OR sections LIKE ?)"
            params.append(primary_section)
            params.append(f'%"{primary_section}"%')

        query += " ORDER BY published_dt DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        articles = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("published_dt"), str):
                try:
                    dt = datetime.datetime.fromisoformat(d["published_dt"])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=NEPAL_TZ)
                    d["published_dt"] = dt
                except Exception:
                    pass
            # Parse JSON fields
            try:
                d["sections"] = json.loads(d.get("sections") or "[]")
            except Exception:
                d["sections"] = [d.get("primary_section")]
            try:
                d["secondary_tags"] = json.loads(d.get("secondary_tags") or "[]")
            except Exception:
                d["secondary_tags"] = []
            d["low_confidence"] = bool(d.get("low_confidence"))
            d["is_viral"] = bool(d.get("is_viral"))
            d["structured_category"] = d.get("primary_section")
            articles.append(d)
        return articles

def set_source_enabled(source_name: str, enabled: bool):
    """Enables or disables monitoring for a specific source."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE sources SET enabled = ? WHERE name = ?", (1 if enabled else 0, source_name))
        conn.commit()

def set_source_interval(source_name: str, interval_mins: int):
    """Updates the check interval for a portal."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE sources SET check_interval_mins = ? WHERE name = ?", (interval_mins, source_name))
        conn.commit()

def get_system_kpis() -> Dict[str, Any]:
    """Computes global intelligence KPIs for the admin dashboard."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END) as active FROM sources")
        src_row = cursor.fetchone()

        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status='operational' THEN 1 ELSE 0 END) as operational,
                SUM(CASE WHEN status='degraded' THEN 1 ELSE 0 END) as degraded,
                SUM(CASE WHEN status='failing' THEN 1 ELSE 0 END) as failing,
                AVG(discovery_latency_avg_secs) as avg_latency
            FROM source_health
        """)
        health_row = cursor.fetchone()

        cursor.execute("""
            SELECT 
                COUNT(*) as total_articles,
                SUM(CASE WHEN published_dt >= datetime('now', '-1 hour') THEN 1 ELSE 0 END) as count_1h,
                SUM(CASE WHEN published_dt >= datetime('now', '-24 hour') THEN 1 ELSE 0 END) as count_24h,
                SUM(CASE WHEN published_dt >= datetime('now', '-7 day') THEN 1 ELSE 0 END) as count_7d
            FROM articles
        """)
        art_row = cursor.fetchone()

        return {
            "total_sources": src_row["total"] if src_row else 34,
            "active_sources": src_row["active"] if src_row else 34,
            "operational": health_row["operational"] or 0,
            "degraded": health_row["degraded"] or 0,
            "failing": health_row["failing"] or 0,
            "avg_latency_secs": round(health_row["avg_latency"] or 0.0, 2),
            "articles_1h": art_row["count_1h"] or 0,
            "articles_24h": art_row["count_24h"] or 0,
            "articles_7d": art_row["count_7d"] or 0,
            "total_stored_articles": art_row["total_articles"] or 0
        }

def log_broadcast_delivery(
    item_key: str,
    source_name: str,
    stream_type: str,
    title: str,
    link: str,
    status: str = "delivered",
    message_id: str = "",
    attempts: int = 1,
    channel_id: str = "",
    error_msg: str = ""
):
    """Records a single message broadcast attempt and status in durable SQLite audit log."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO broadcast_logs 
                (item_key, source_name, stream_type, title, link, status, message_id, attempts, channel_id, error_msg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_key,
                source_name,
                stream_type,
                title[:250],
                link,
                status,
                message_id,
                attempts,
                channel_id,
                error_msg
            ))
            conn.commit()
    except Exception as e:
        logger.warning(f"Error logging broadcast delivery to database: {e}")

def get_source_broadcast_stats() -> List[Dict[str, Any]]:
    """Fetches source-wise WhatsApp broadcast volume, latest dispatch, and success counts."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    source_name,
                    stream_type,
                    COUNT(*) as total_dispatches,
                    SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered_count,
                    SUM(CASE WHEN status != 'delivered' THEN 1 ELSE 0 END) as failed_count,
                    MAX(dispatched_at) as last_dispatched_at
                FROM broadcast_logs
                GROUP BY source_name, stream_type
                ORDER BY total_dispatches DESC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Error reading broadcast source stats: {e}")
        return []

def get_recent_broadcast_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves the latest broadcast audit entries."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    id, item_key, source_name, stream_type, title, link, status, message_id, attempts, channel_id, dispatched_at, error_msg
                FROM broadcast_logs
                ORDER BY dispatched_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Error fetching recent broadcast logs: {e}")
        return []

def ingest_indian_articles_batch(articles: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Persists all scraped Indian media articles (including substantive, borderline_review, and excluded)
    into the central SQLite database while preserving original headlines, sources, dates, and URLs.
    """
    counts = {"substantive": 0, "borderline_review": 0, "excluded": 0}
    if not articles:
        return counts
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for a in articles:
                title = (a.get("title") or "").strip()
                link = (a.get("link") or "").strip()
                source = (a.get("source") or "Indian Media").strip()
                if not title or not link:
                    continue
                cid = generate_canonical_id(title, link, source)
                canon_url = normalize_canonical_url(link)
                pub_dt = a.get("published_dt")
                if isinstance(pub_dt, datetime.datetime):
                    pub_dt_str = pub_dt.isoformat()
                else:
                    pub_dt_str = str(pub_dt or datetime.datetime.now(NEPAL_TZ).isoformat())

                rel_score = float(a.get("nepal_relevance_score", 0.0))
                rel_status = str(a.get("relevance_status", "excluded"))
                rel_reason = str(a.get("relevance_reason", ""))
                dims_json = json.dumps(a.get("nepal_dimensions", []), ensure_ascii=False)
                sections_json = json.dumps(a.get("sections", ["India Section"]), ensure_ascii=False)
                tags_json = json.dumps(a.get("secondary_tags", []), ensure_ascii=False)

                if rel_status in counts:
                    counts[rel_status] += 1

                cursor.execute("""
                    INSERT INTO indian_media_articles (
                        canonical_id, source, title, headline_english, link, canonical_url,
                        summary, full_content, published_dt, relative_time, exact_time,
                        language, primary_section, sections, secondary_tags,
                        classification_confidence, nepal_relevance_score,
                        relevance_status, relevance_reason, nepal_dimensions
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(canonical_id) DO UPDATE SET
                        nepal_relevance_score = excluded.nepal_relevance_score,
                        relevance_status = excluded.relevance_status,
                        relevance_reason = excluded.relevance_reason,
                        nepal_dimensions = excluded.nepal_dimensions,
                        relative_time = excluded.relative_time
                """, (
                    cid,
                    source,
                    title,
                    a.get("headline_english", ""),
                    link,
                    canon_url,
                    a.get("summary", ""),
                    a.get("full_content", ""),
                    pub_dt_str,
                    a.get("relative_time", "Recent"),
                    a.get("exact_time", ""),
                    a.get("language", "English"),
                    a.get("primary_section", "India Section"),
                    sections_json,
                    tags_json,
                    float(a.get("classification_confidence", 0.85)),
                    rel_score,
                    rel_status,
                    rel_reason,
                    dims_json
                ))
            conn.commit()
    except Exception as e:
        logger.warning(f"Error persisting Indian media articles to central database: {e}")
    return counts

def get_stored_indian_articles(
    status_filter: Optional[str] = "substantive",
    min_score: float = 0.0,
    limit: int = 200
) -> List[Dict[str, Any]]:
    """
    Retrieves stored Indian media articles from the central database, optionally filtered by
    relevance_status ('substantive', 'borderline_review', 'excluded') and minimum score.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM indian_media_articles WHERE nepal_relevance_score >= ?"
            params: List[Any] = [min_score]
            if status_filter:
                query += " AND relevance_status = ?"
                params.append(status_filter)
            query += " ORDER BY published_dt DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if isinstance(d.get("published_dt"), str):
                    try:
                        dt = datetime.datetime.fromisoformat(d["published_dt"])
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=NEPAL_TZ)
                        d["published_dt"] = dt
                    except Exception:
                        pass
                try:
                    d["sections"] = json.loads(d.get("sections") or '["India Section"]')
                except Exception:
                    d["sections"] = ["India Section"]
                try:
                    d["secondary_tags"] = json.loads(d.get("secondary_tags") or "[]")
                except Exception:
                    d["secondary_tags"] = []
                try:
                    d["nepal_dimensions"] = json.loads(d.get("nepal_dimensions") or "[]")
                except Exception:
                    d["nepal_dimensions"] = []
                d["portal_category"] = "Indian Press"
                d["structured_category"] = d.get("primary_section", "India Section")
                results.append(d)
            return results
    except Exception as e:
        logger.warning(f"Error querying stored Indian media articles: {e}")
        return []

def get_indian_media_audit_stats() -> Dict[str, int]:
    """Returns counts of substantive, borderline_review, and excluded Indian articles in central DB."""
    stats = {"substantive": 0, "borderline_review": 0, "excluded": 0, "total": 0}
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT relevance_status, COUNT(*) as cnt
                FROM indian_media_articles
                GROUP BY relevance_status
            """)
            for r in cursor.fetchall():
                st_name = r["relevance_status"]
                cnt = r["cnt"]
                if st_name in stats:
                    stats[st_name] = cnt
                stats["total"] += cnt
    except Exception as e:
        logger.warning(f"Error reading Indian media audit stats: {e}")
    return stats

