#!/usr/bin/env bash
# run.sh - One-click launcher for Nepal Social Monitor & Automated Hourly WhatsApp Worker
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "🇳🇵 Starting Nepal Social Media Monitor..."

# Start background automated WhatsApp hourly dispatch worker if not already running
if ! pgrep -f "whatsapp_auto_worker.py" > /dev/null; then
    echo "📢 Launching background automated hourly WhatsApp broadcast worker..."
    nohup "$DIR/.venv/bin/python" "$DIR/whatsapp_auto_worker.py" >> "$DIR/whatsapp_worker.log" 2>&1 &
fi

"$DIR/.venv/bin/streamlit" run "$DIR/app.py" --server.port 8501 --server.headless false

