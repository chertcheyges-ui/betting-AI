"""Refresh only imminent paper-trading matches before kickoff.

The scheduled task runs frequently, but calls the data providers only when an
open match is 30–90 minutes away.  It is a paper-trading check and never
places a real bet.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PAPER_PATH = ROOT / "dashboard" / "site-static" / "paper-trading.json"


def load_paper():
    try:
        return json.loads(PAPER_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"trades": []}


def imminent_open_match(trades):
    now = datetime.now(timezone.utc)
    earliest = now + timedelta(minutes=30)
    latest = now + timedelta(minutes=90)
    for trade in trades:
        if not isinstance(trade, dict) or trade.get("status") != "OPEN":
            continue
        try:
            kickoff = datetime.fromisoformat(str(trade.get("kickoff")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        if earliest <= kickoff.astimezone(timezone.utc) <= latest:
            return True
    return False


def main():
    paper = load_paper()
    if not imminent_open_match(paper.get("trades", [])):
        print("No imminent open matches; skipped pre-match refresh.")
        return 0
    result = subprocess.run([sys.executable, str(ROOT / "export_system_status.py")], cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
