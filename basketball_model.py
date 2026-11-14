"""Small, separate NBA form model used only for basketball recommendations."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dashboard" / "site-static" / "basketball-analysis.json"
CACHE = ROOT / "data" / "basketball-form-cache.json"
ODDS_CACHE = ROOT / "data" / "basketball-odds-cache.json"
GAMES_URL = "https://api.balldontlie.io/v1/games"
ODDS_URL = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"


def save(payload):
    try:
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    archive = previous.get("forecast_history", {})
    for recommendation in previous.get("recommendations", []):
        if recommendation.get("match_id") is not None:
            archive.setdefault(str(recommendation["match_id"]), recommendation)
    for recommendation in payload["recommendations"]:
        archive[str(recommendation["match_id"])] = recommendation
    payload["forecast_history"] = archive
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=OUTPUT.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.close()
            temporary.replace(OUTPUT)
        finally:
            temporary.unlink(missing_ok=True)


def recent_games(day, key):
    try:
        cached = json.loads(CACHE.read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(cached.get("generated_at", ""))
        if datetime.now(ZoneInfo("UTC")) - generated.astimezone(ZoneInfo("UTC")) < timedelta(hours=1):
            return cached.get("games") or []
    except (OSError, ValueError, TypeError):
        pass
    start = (datetime.fromisoformat(day) - timedelta(days=14)).date().isoformat()
    response = requests.get(
        GAMES_URL,
        params={"start_date": start, "end_date": day, "per_page": 100},
        headers={"Authorization": key}, timeout=20,
    )
    response.raise_for_status()
    games = list(response.json().get("data") or [])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"generated_at": datetime.now(ZoneInfo("UTC")).isoformat(), "games": games}), encoding="utf-8")
    return games


def _name(value):
    return " ".join("".join(char if char.isalnum() else " " for char in str(value or "").lower()).split())


def bookmaker_odds(key):
    """Return one current, named bookmaker moneyline for each NBA game.

    The cache prevents hourly updates from spending a request when the odds
    have not had time to materially change.
    """
    try:
        cached = json.loads(ODDS_CACHE.read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(cached.get("generated_at", ""))
        if datetime.now(ZoneInfo("UTC")) - generated.astimezone(ZoneInfo("UTC")) < timedelta(minutes=15):
            return cached.get("odds") or {}
    except (OSError, ValueError, TypeError):
        pass
    if not key:
        return {}
    response = requests.get(
        ODDS_URL,
        params={"apiKey": key, "regions": "us", "markets": "h2h", "oddsFormat": "decimal"},
        timeout=20,
    )
    response.raise_for_status()
    mapped = {}
    for event in response.json():
        home, away = event.get("home_team"), event.get("away_team")
        if not home or not away:
            continue
        for bookmaker in event.get("bookmakers") or []:
            market = next((item for item in bookmaker.get("markets") or [] if item.get("key") == "h2h"), None)
            outcomes = {item.get("name"): item.get("price") for item in (market or {}).get("outcomes") or []}
            if isinstance(outcomes.get(home), (int, float)) and isinstance(outcomes.get(away), (int, float)):
                mapped[_name(home) + "|" + _name(away)] = {
                    "HOME_WIN": float(outcomes[home]), "AWAY_WIN": float(outcomes[away]),
                    "bookmaker": bookmaker.get("title") or bookmaker.get("key") or "Букмекер",
                    "updated_at": bookmaker.get("last_update"),
                }
                break
    ODDS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    ODDS_CACHE.write_text(json.dumps({"generated_at": datetime.now(ZoneInfo("UTC")).isoformat(), "odds": mapped}), encoding="utf-8")
    return mapped


def form(games):
    table = {}
    for game in games:
        if str(game.get("status") or "").lower() not in {"final", "ft"}:
            continue
        home, away = game.get("home_team") or {}, game.get("visitor_team") or {}
        home_name, away_name = home.get("full_name"), away.get("full_name")
        home_score, away_score = game.get("home_team_score"), game.get("visitor_team_score")
        if not home_name or not away_name or not isinstance(home_score, int) or not isinstance(away_score, int):
            continue
        for team, own, other in ((home_name, home_score, away_score), (away_name, away_score, home_score)):
            record = table.setdefault(team, {"games": 0, "wins": 0, "point_difference": 0})
            record["games"] += 1
            record["wins"] += int(own > other)
            record["point_difference"] += own - other
    return table


def build(matches):
    load_dotenv(ROOT / ".env")
    minsk = ZoneInfo("Europe/Minsk")
    now = datetime.now(minsk)
    day = now.date().isoformat()
    key = os.getenv("BALLDONTLIE_API_KEY")
    odds_key = os.getenv("ODDS_API_KEY")
    payload = {"schema_version": 1, "sport": "basketball", "generated_at": datetime.now(ZoneInfo("UTC")).isoformat(), "status": "unavailable", "recommendations": []}
    if not key:
        save(payload)
        return payload
    try:
        table = form(recent_games(day, key))
        current_odds = bookmaker_odds(odds_key)
        for match in matches:
            if match.get("source") != "BALLDONTLIE" or match.get("status") not in {"NS", "SCHEDULED"}:
                continue
            try:
                start = datetime.fromisoformat(f"{match['date']}T{match['time']}").replace(tzinfo=minsk)
            except (KeyError, ValueError):
                continue
            if start <= now:
                continue
            home, away = table.get(match["home"], {}), table.get(match["away"], {})
            if min(home.get("games", 0), away.get("games", 0)) < 3:
                continue
            home_rate = home["wins"] / home["games"]
            away_rate = away["wins"] / away["games"]
            home_diff = home["point_difference"] / home["games"]
            away_diff = away["point_difference"] / away["games"]
            probability = max(0.35, min(0.75, 0.55 + 0.25 * (home_rate - away_rate) + 0.008 * (home_diff - away_diff)))
            prediction = "HOME_WIN" if probability >= 0.5 else "AWAY_WIN"
            confidence = probability if prediction == "HOME_WIN" else 1 - probability
            market = current_odds.get(_name(match["home"]) + "|" + _name(match["away"]), {})
            recommendation = {
                "match_id": match["id"], "event": match["home"] + " vs " + match["away"], "prediction": prediction,
                "confidence": round(confidence * 100, 1), "status": "WATCH" if confidence >= 0.58 else "NO BET",
                "reason": "Форма за последние 14 дней: " + match["home"] + " " + str(home["wins"]) + "/" + str(home["games"]) + ", " + match["away"] + " " + str(away["wins"]) + "/" + str(away["games"]) + ".",
            }
            odds = market.get(prediction)
            if isinstance(odds, (int, float)) and odds > 1:
                recommendation.update({"bookmaker_odds": round(odds, 2), "bookmaker": market.get("bookmaker"), "odds_updated_at": market.get("updated_at")})
                recommendation["reason"] += " Коэффициент букмекера " + str(market.get("bookmaker")) + ": " + f"{odds:.2f}" + "."
            else:
                recommendation["reason"] += " Коэффициент букмекера пока не получен."
            payload["recommendations"].append(recommendation)
        payload["status"] = "success"
    except (requests.RequestException, ValueError, KeyError, TypeError):
        payload["status"] = "error"
    save(payload)
    return payload


if __name__ == "__main__":
    report = json.loads((ROOT / "dashboard" / "site-static" / "basketball-report.json").read_text(encoding="utf-8"))
    print("Баскетбольных рекомендаций:", len(build(report.get("matches") or []).get("recommendations", [])))
