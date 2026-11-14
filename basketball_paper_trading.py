"""Virtual basketball ledger with clearly marked estimated odds."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
TRADES = ROOT / "data" / "basketball_paper_trades.json"
OUTPUT = ROOT / "dashboard" / "site-static" / "basketball-paper-trading.json"
GAMES_URL = "https://api.balldontlie.io/v1/games"
RESERVE_PERCENT = 50.0


def load(path, default):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else default
    except (OSError, ValueError):
        return default


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def outcome(home, away):
    if not isinstance(home, int) or not isinstance(away, int) or home == away:
        return None
    return "HOME_WIN" if home > away else "AWAY_WIN"


def kickoff(match):
    try:
        return datetime.fromisoformat(
            str(match.get("date") or "") + "T" + str(match.get("time") or "00:00:00").replace("Z", "+00:00")
        ).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def record(report, analysis):
    """Record only real bookmaker odds supplied by the data collector.

    Basketball forecasts remain visible without odds, but never affect the
    virtual bank.  This prevents an estimated number from being mistaken for
    a real market price.
    """
    ledger = load(TRADES, {"schema_version": 1, "trades": []})
    matches = {str(item.get("id")): item for item in report.get("matches", []) if isinstance(item, dict)}
    if any(item.get("status") == "OPEN" for item in ledger["trades"]):
        return ledger
    choices = []
    for recommendation in analysis.get("recommendations", []):
        if recommendation.get("status") != "WATCH":
            continue
        match = matches.get(str(recommendation.get("match_id")))
        odds = recommendation.get("bookmaker_odds")
        if match and str(match.get("status") or "").upper() in {"NS", "SCHEDULED"} and isinstance(odds, (int, float)) and odds > 1:
            choices.append((float(recommendation.get("confidence") or 0), recommendation, match))
    if not choices:
        return ledger
    confidence, recommendation, match = max(choices, key=lambda item: item[0])
    fixture_id = str(match["id"])
    existing = next((item for item in ledger["trades"] if str(item.get("fixture_id")) == fixture_id), None)
    if existing and existing.get("status") != "CANCELLED":
        return ledger
    created = datetime.now(timezone.utc).isoformat()
    trade = {
        "fixture_id": fixture_id, "sport": "basketball", "event": recommendation["event"],
        "kickoff": kickoff(match), "prediction": recommendation["prediction"],
        "confidence": round(confidence, 1), "odds": round(float(recommendation["bookmaker_odds"]), 2), "odds_kind": "bookmaker",
        "bookmaker": recommendation.get("bookmaker"), "stake": float(recommendation.get("stake") or 10.0), "decision": "PAPER BET", "status": "OPEN", "created_at": created,
        "reason": recommendation.get("reason"),
        "decision_reasons": [
            "Учебная виртуальная ставка: выбран самый сильный баскетбольный прогноз дня.",
            "Использован настоящий коэффициент букмекера из подключённого источника.",
        ],
    }
    if existing:
        existing.clear()
        existing.update(trade)
    else:
        ledger["trades"].append(trade)
    save(TRADES, ledger)
    return ledger


def game_result(trade, key):
    fixture_id = str(trade.get("fixture_id") or "")
    if not fixture_id.startswith("bdl-") or not key:
        return None
    try:
        when = datetime.fromisoformat(str(trade.get("kickoff")).replace("Z", "+00:00"))
        if datetime.now(timezone.utc) < when.astimezone(timezone.utc) + timedelta(hours=2):
            return None
        response = requests.get(GAMES_URL + "/" + fixture_id.removeprefix("bdl-"), headers={"Authorization": key}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        return payload.get("data") or payload
    except (requests.RequestException, ValueError, AttributeError):
        return None


def operations(trades):
    rows = []
    for trade in trades:
        if trade.get("decision") != "PAPER BET" or trade.get("status") == "CANCELLED" or float(trade.get("stake") or 0) <= 0:
            continue
        stake = float(trade["stake"])
        event = "Баскетбол · " + str(trade.get("event") or "Матч")
        rows.append({"id": "basket-stake-" + str(trade.get("fixture_id")), "type": "expense", "amount": stake, "date": trade.get("created_at"), "title": "Виртуальная ставка", "note": event + " · коэффициент букмекера " + f"{float(trade.get('odds') or 0):.2f}" + "."})
        if trade.get("status") == "SETTLED":
            if trade.get("was_correct"):
                rows.append({"id": "basket-return-" + str(trade.get("fixture_id")), "type": "income", "amount": round(stake + float(trade.get("virtual_pnl") or 0), 2), "date": trade.get("settled_at"), "title": "Виртуальный результат", "note": event + " · прогноз сыграл."})
            else:
                rows.append({"id": "basket-loss-" + str(trade.get("fixture_id")), "type": "loss", "amount": stake, "date": trade.get("settled_at"), "title": "Итог виртуальной ставки", "note": event + " · прогноз не сыграл."})
    return rows


def publish():
    load_dotenv(ROOT / ".env")
    ledger = load(TRADES, {"schema_version": 1, "trades": []})
    key = os.getenv("BALLDONTLIE_API_KEY")
    for trade in ledger["trades"]:
        if trade.get("odds_kind") == "estimated" and trade.get("status") == "OPEN":
            trade.update({"status": "CANCELLED", "cancelled_at": datetime.now(timezone.utc).isoformat(), "virtual_pnl": 0.0, "cancellation_reason": "Ставка отменена: расчётный коэффициент заменён требованием настоящего коэффициента букмекера."})
            continue
        if trade.get("status") != "OPEN":
            continue
        game = game_result(trade, key)
        actual = outcome(game.get("home_team_score"), game.get("visitor_team_score")) if isinstance(game, dict) and str(game.get("status") or "").lower() in {"final", "ft"} else None
        if not actual:
            continue
        stake, odds = float(trade.get("stake") or 0), float(trade.get("odds") or 0)
        trade.update({"actual_outcome": actual, "was_correct": trade.get("prediction") == actual, "virtual_pnl": round(stake * (odds - 1) if trade.get("prediction") == actual else -stake, 2), "status": "SETTLED", "settled_at": datetime.now(timezone.utc).isoformat()})
    save(TRADES, ledger)
    trades = ledger["trades"]
    settled = [item for item in trades if item.get("status") == "SETTLED"]
    pnl = round(sum(float(item.get("virtual_pnl") or 0) for item in settled), 2)
    reserve = round(sum(max(0, float(item.get("virtual_pnl") or 0)) for item in settled) * RESERVE_PERCENT / 100, 2)
    save(OUTPUT, {"schema_version": 1, "sport": "basketball", "updated_at": datetime.now(timezone.utc).isoformat(), "virtual_pnl": pnl, "open_exposure": round(sum(float(item.get("stake") or 0) for item in trades if item.get("status") == "OPEN"), 2), "profit_reserve": reserve, "trades": trades, "operations": operations(trades)})


def update(report, analysis):
    record(report, analysis)
    publish()

