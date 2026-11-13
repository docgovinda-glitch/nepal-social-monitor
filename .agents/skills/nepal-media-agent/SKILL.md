---
name: nepal-media-agent
description: Specialized intelligence agent for Nepal Social & Media Monitor. Scans 34 Nepali news portals, Indian press on Nepal, and 281+ X accounts. Deduplicates, categorizes into 8 geopolitical buckets, monitors portal health, and generates analytical intelligence reports.
---

# Nepal Media & Intelligence Agent Guide

This agent manages and operates the **Nepal Social Media & News Intelligence Monitor**.

## Core System Architecture

1. **Dashboard UI**: Streamlit web app (`app.py`) on port `8501`.
2. **Fetchers & Scanners**:
   - `nepal_fetcher.py`: Scrapes and standardizes 34 Nepali portals + Indian press coverage of Nepal.
   - `nepal_x_scanner.py`: Scans 281+ verified Nepali Twitter/X handles.
3. **Database & Storage**:
   - `nepal_news_store.py`: Canonical PostgreSQL (Supabase) + local SQLite article and portal health storage.

---

## Agent Operations Runbook

### 1. Check Health & Running Services
```bash
# Check if Streamlit UI is running
lsof -i :8501
```

### 2. Manual Media Ingestion Trigger
```bash
./.venv/bin/python -c '
from nepal_fetcher import fetch_top_nepal_media
arts = fetch_top_nepal_media(force_refresh=True)
print(f"Fetched {len(arts)} articles")
'
```
