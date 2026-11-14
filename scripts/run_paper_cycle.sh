#!/bin/zsh
# Daily paper-trading cycle. No real bets are placed by this script.
set -u

PROJECT_DIR="/Users/newnew/sasha edu"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"
exec "$PROJECT_DIR/.venv/bin/python" run_paper_cycle.py >> "$LOG_DIR/paper-trading.log" 2>&1
