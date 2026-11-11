---
name: nepal-media-agent
description: Specialized intelligence agent for Nepal Social & Media Monitor. Scans 34 Nepali news portals, Indian press on Nepal, and 281+ X accounts. Deduplicates, categorizes into 8 geopolitical buckets, formats, broadcasts to WhatsApp via Green-API, monitors daemon health, and generates analytical intelligence reports.
---

# Nepal Media & Intelligence Agent Guide

This agent manages and operates the **Nepal Social Media & News Intelligence Monitor**.

## Core System Architecture

1. **Dashboard UI**: Streamlit web app (`app.py`) on port `8501`.
2. **Fetchers & Scanners**:
   - `nepal_fetcher.py`: Scrapes and standardizes 34 Nepali portals + Indian press coverage of Nepal.
   - `nepal_x_scanner.py`: Scans 281+ verified Nepali Twitter/X handles.
3. **Broadcasting & Deduplication**:
   - `whatsapp_dispatcher.py`: Message formatting (title, summary, link), Green-API gateway, webhook integration.
   - `whatsapp_sent_cache.json`: Persistent SHA256 key deduplication store (ensures 0 duplicate broadcasts).
   - `whatsapp_auto_worker.py`: Background daemon operating **06:00 AM to 10:00 PM NPT** on the first minute of each hour (`:00`). Holds overnight stories (10:00 PM to 06:00 AM) and broadcasts them at 06:00 AM all at once.
4. **Cloud Automation**:
   - `.github/workflows/whatsapp_broadcast.yml`: 24/7 cloud backup worker on GitHub Actions scheduled at `15 0-16 * * *` (06:00 to 22:00 NPT hourly).

---

## Agent Operations Runbook

### 1. Check Health & Running Services
```bash
# Check if Streamlit UI is running
lsof -i :8501

# Check if local background broadcast worker is active
ps aux | grep -i whatsapp_auto_worker

# Inspect recent broadcast log
tail -n 30 whatsapp_worker.log
```

### 2. Trigger an Immediate Broadcast Scan Cycle
```bash
# Dry-run (simulate without sending messages)
./.venv/bin/python whatsapp_auto_worker.py --dry-run --once

# Live run (broadcast all fresh stories right now)
./.venv/bin/python whatsapp_auto_worker.py --once

# Broadcast capped at top 10 stories
./.venv/bin/python whatsapp_auto_worker.py --once --max-per-cycle 10
```

### 3. Verify WhatsApp Connection & Send Test Ping
```bash
./.venv/bin/python -c '
from whatsapp_dispatcher import send_test_green_api_message, get_env_variable
chat_id = get_env_variable("GREEN_API_CHAT_ID")
ok, res = send_test_green_api_message(chat_id)
print("WhatsApp Gateway Status:", ok, res)
'
```

### 4. Check Cloud Broadcast Status
```bash
gh run list --limit 5
gh run view --log
```

### 5. Inspect Broadcast Statistics
```bash
./.venv/bin/python -c '
from whatsapp_dispatcher import get_broadcasted_stats
stats = get_broadcasted_stats()
print("Total Broadcasted:", stats["total_broadcasted"])
print("Breakdown:", stats["by_type"])
print("Last Broadcast At:", stats["last_broadcast_at"])
'
```

