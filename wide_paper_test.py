"""Record and score a larger, no-money forecast test from football-data.org."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
LEDGER_PATH = ROOT / "data" / "wide_test_forecasts.json"
DASHBOARD_PATH = ROOT / "dashboard" / "site-static" / "wide-testing.json"
OUTCOMES = {"HOME_TEAM": "HOME_WIN", "DRAW": "DRAW", "AWAY_TEAM": "AWAY_WIN"}

load_dotenv(ROOT / ".env")


def _load(path, default):
    try:
        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
        return value if isinstance(value, dict) else default
    except (OSError, ValueError):
        return default


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record(scan):
    """Save first predictions before the results are known; never use money."""
    ledger = _load(LEDGER_PATH, {"schema_version": 1, "tests": []})
    known = {str(item.get("match_id")) for item in ledger["tests"]}
    for match in scan.get("matches", []) if isinstance(scan, dict) else []:
        prediction = match.get("prediction")
        match_id = match.get("match_id")
        if prediction not in {"HOME_WIN", "DRAW", "AWAY_WIN"} or match_id is None:
            continue
        if str(match_id) in known:
            continue
        ledger["tests"].append({
            "match_id": match_id,
            "event": match.get("event"),
            "kickoff": match.get("kickoff"),
            "league": match.get("league"),
            "prediction": prediction,
            "confidence": match.get("confidence"),
            "data_used": match.get("data_used"),
            "created_at": scan.get("generated_at"),
            "status": "OPEN",
            "money_used": 0,
        })
    _save(LEDGER_PATH, ledger)
    return ledger


def evaluate():
    """Use one date-range request to close as many test forecasts as possible."""
    ledger = _load(LEDGER_PATH, {"schema_version": 1, "tests": []})
    open_tests = [item for item in ledger["tests"] if item.get("status") == "OPEN"]
    if not open_tests:
        return publish(ledger)
    token = os.getenv("FOOTBALL_DATA_API_KEY")
    dates = [str(item.get("kickoff") or "")[:10] for item in open_tests]
    dates = [value for value in dates if len(value) == 10]
    if not token or not dates:
        return publish(ledger)
    matches = None
    for attempt in range(3):
        try:
            response = requests.get(
                "https://api.football-data.org/v4/matches",
                headers={"X-Auth-Token": token},
                params={"dateFrom": min(dates), "dateTo": datetime.now(timezone.utc).date().isoformat()},
                timeout=20,
            )
            response.raise_for_status()
            matches = {str(item.get("id")): item for item in response.json().get("matches", [])}
            break
        except requests.RequestException as error:
            ledger["last_evaluation_error"] = str(error)
            if attempt < 2:
                time.sleep(attempt + 1)
    if matches is None:
        return publish(ledger)
    ledger.pop("last_evaluation_error", None)
    for test in open_tests:
        match = matches.get(str(test.get("match_id")))
        if not match or match.get("status") != "FINISHED":
            continue
        winner = (match.get("score") or {}).get("winner")
        actual = OUTCOMES.get(winner)
        if actual:
            test["actual_outcome"] = actual
            test["was_correct"] = actual == test.get("prediction")
            test["status"] = "SETTLED"
            test["settled_at"] = datetime.now(timezone.utc).isoformat()
    ledger["last_evaluated_at"] = datetime.now(timezone.utc).isoformat()
    _save(LEDGER_PATH, ledger)
    return publish(ledger)


def publish(ledger=None):
    ledger = ledger or _load(LEDGER_PATH, {"schema_version": 1, "tests": []})
    tests = ledger.get("tests", [])
    settled = [item for item in tests if item.get("status") == "SETTLED"]
    payload = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "experiment": "50-match forecast test only — no money used.",
        "total_count": len(tests),
        "open_count": len(tests) - len(settled),
        "settled_count": len(settled),
        "accuracy": (
            sum(bool(item.get("was_correct")) for item in settled) / len(settled)
            if settled else None
        ),
        "last_evaluated_at": ledger.get("last_evaluated_at"),
        "last_evaluation_error": ledger.get("last_evaluation_error"),
        "tests": tests,
    }
    _save(DASHBOARD_PATH, payload)
    return payload
