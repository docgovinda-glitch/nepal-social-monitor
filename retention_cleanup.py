"""
retention_cleanup.py
Deletes stories older than RETENTION_DAYS (default 90) from the three feed tables so the database
stays inside its storage plan. Runs from GitHub Actions (retention.yml); safe to run by hand.

  RETENTION_DAYS  days to keep (minimum 30)
  DRY_RUN         "1"/"true" counts only and deletes nothing
"""
import os
import sys

from nepal_news_store import query_supabase

TABLES = ("articles", "indian_media_articles", "x_posts")
BATCH = 5000
MAX_BATCHES = 40
MAX_DELETE_SHARE = 0.9


def _count(sql: str):
    rows = query_supabase(sql)
    if not rows:
        return None
    return int(next(iter(rows[0].values())) or 0)


def main() -> int:
    try:
        days = int(os.getenv("RETENTION_DAYS", "90") or 90)
    except ValueError:
        print("RETENTION_DAYS must be a number")
        return 2
    if days < 30:
        print("Refusing to keep fewer than 30 days")
        return 2
    dry = (os.getenv("DRY_RUN", "0") or "0").strip().lower() in ("1", "true", "yes")
    cutoff = f"(NOW() - INTERVAL '{days} days')"
    failed = False

    for table in TABLES:
        total = _count(f"SELECT COUNT(*) AS n FROM {table};")
        old = _count(f"SELECT COUNT(*) AS n FROM {table} WHERE published_dt < {cutoff};")
        if total is None or old is None:
            print(f"[{table}] could not read counts; skipping")
            failed = True
            continue
        print(f"[{table}] total={total:,} older_than_{days}d={old:,}")
        if old == 0:
            continue
        if total >= 100 and old / total > MAX_DELETE_SHARE:
            print(f"[{table}] would delete over {int(MAX_DELETE_SHARE * 100)}% of rows; aborting this table")
            failed = True
            continue
        if dry:
            print(f"[{table}] dry run: nothing deleted")
            continue
        deleted = 0
        for _ in range(MAX_BATCHES):
            n = _count(
                f"WITH d AS (DELETE FROM {table} WHERE ctid IN "
                f"(SELECT ctid FROM {table} WHERE published_dt < {cutoff} LIMIT {BATCH}) RETURNING 1) "
                f"SELECT COUNT(*) AS n FROM d;"
            )
            if n is None:
                print(f"[{table}] delete batch failed")
                failed = True
                break
            deleted += n
            if n < BATCH:
                break
        print(f"[{table}] deleted={deleted:,}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
