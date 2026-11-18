"""Apply idempotent SQL migrations to Supabase PostgreSQL."""
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from nepal_news_store import query_supabase


def apply_migrations() -> None:
    mig_dir = os.path.dirname(os.path.abspath(__file__))
    sql_files = sorted(f for f in os.listdir(mig_dir) if f.endswith(".sql"))
    for fname in sql_files:
        path = os.path.join(mig_dir, fname)
        with open(path, "r", encoding="utf-8") as fh:
            sql_text = fh.read()
        print(f"Applying {fname}...")
        # Split on statement terminators cleanly so partial errors are isolated cleanly
        stmts = [s.strip() for s in sql_text.split(";") if s.strip() and not all(ln.strip().startswith("--") or not ln.strip() for ln in s.splitlines())]
        for idx, stmt in enumerate(stmts, 1):
            query_supabase(stmt + ";")
        print(f"Applied {fname} ({len(stmts)} statements).")


if __name__ == "__main__":
    apply_migrations()
