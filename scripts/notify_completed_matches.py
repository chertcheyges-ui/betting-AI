"""Show one macOS notification for each newly processed virtual match."""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TRADES = ROOT / "data" / "paper_trades.json"
STATE = ROOT / "data" / "notified_completed_matches.json"


def load(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def notify(title, message):
    safe_title = title.replace('"', "'")
    safe_message = message.replace('"', "'")
    subprocess.run(
        ["/usr/bin/osascript", "-e", f'display notification "{safe_message}" with title "{safe_title}"'],
        check=False,
        capture_output=True,
    )


def main():
    ledger = load(TRADES, {"trades": []})
    if not STATE.exists():
        initial = [str(item.get("fixture_id")) for item in ledger.get("trades", []) if item.get("status") == "SETTLED"]
        STATE.write_text(json.dumps({"fixture_ids": sorted(initial)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    state = load(STATE, {"fixture_ids": []})
    notified = {str(item) for item in state.get("fixture_ids", [])}
    completed = [item for item in ledger.get("trades", []) if item.get("status") == "SETTLED"]
    fresh = [item for item in completed if str(item.get("fixture_id")) not in notified]

    for trade in fresh:
        event = trade.get("event") or "Матч"
        result = "прогноз сыграл ✅" if trade.get("was_correct") else "прогноз не сыграл ❌"
        notify("Betting AI: матч обработан", f"{event}: {result}. Открой «Готовые матчи».")
        notified.add(str(trade.get("fixture_id")))

    STATE.write_text(json.dumps({"fixture_ids": sorted(notified)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
