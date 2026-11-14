"""Combine football and basketball training ledgers into one finance view."""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "dashboard" / "site-static"


def load(name):
    try:
        return json.loads((STATIC / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main():
    football, basketball = load("paper-trading.json"), load("basketball-paper-trading.json")
    trades = [{**item, "sport": item.get("sport") or sport} for sport, source in (("football", football), ("basketball", basketball)) for item in source.get("trades", []) if isinstance(item, dict)]
    operations = list(football.get("operations") or []) + list(basketball.get("operations") or [])
    operations.sort(key=lambda item: item.get("date") or "", reverse=True)
    settled = [item for item in trades if item.get("status") == "SETTLED"]
    opened = [item for item in trades if item.get("status") == "OPEN" and item.get("decision") == "PAPER BET"]
    pnl = round(sum(float(item.get("virtual_pnl") or 0) for item in settled), 2)
    exposure = round(sum(float(item.get("stake") or 0) for item in opened), 2)
    reserve = round(sum(max(0, float(item.get("virtual_pnl") or 0)) for item in settled) * 0.5, 2)
    payload = {"schema_version": 1, "updated_at": datetime.now(timezone.utc).isoformat(), "experiment": "Только виртуальные деньги.", "starting_bankroll": 1000.0, "bankroll": round(1000.0 + pnl, 2), "open_exposure": exposure, "profit_reserve_percent": 50.0, "profit_reserve": reserve, "available_bankroll": round(max(0, 1000.0 + pnl - reserve - exposure), 2), "virtual_pnl": pnl, "open_count": len(opened), "settled_count": len(settled), "trades": trades, "operations": operations, "financial_policy": football.get("financial_policy") or {"profit_reserve_percent": 50, "increase_after_loss": False, "limit_review_min_matches": 20, "limit_review_target_matches": 50}}
    (STATIC / "shared-finance.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    main()
