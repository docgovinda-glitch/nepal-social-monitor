#!/usr/bin/env bash
# run.sh - Simple one-click launcher for Nepal Social Monitor
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "🇳🇵 Starting Nepal Social Media Monitor..."
"$DIR/.venv/bin/streamlit" run "$DIR/app.py" --server.port 8501 --server.headless false

