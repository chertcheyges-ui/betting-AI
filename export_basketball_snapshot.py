"""Save a separate basketball schedule and score snapshot for the dashboard."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dashboard" / "site-static" / "basketball-report.json"
HISTORY = ROOT / "dashboard" / "site-static" / "basketball-history.json"
SOURCE = "https://www.thesportsdb.com/api/v1/json/123/eventsday.php"
BALLDONTLIE_SOURCE = "https://api.balldontlie.io/v1/games"
ODDS_SOURCE = "https://api.the-odds-api.com/v4/sports"
ODDS_CACHE = ROOT / "data" / "basketball-other-odds-cache.json"


def save(payload):
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=OUTPUT.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temporary.replace(OUTPUT)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def save_history(matches):
    try:
        current = json.loads(HISTORY.read_text(encoding="utf-8"))
        records = current.get("matches", []) if isinstance(current, dict) else []
    except (OSError, ValueError):
        records = []
    by_id = {str(item.get("id")): item for item in records if isinstance(item, dict) and item.get("id")}
    for match in matches:
        if match.get("status") in {"FT", "AOT", "FINAL"}:
            by_id[str(match["id"])] = match
    payload = {"schema_version": 1, "sport": "basketball", "updated_at": datetime.now(ZoneInfo("UTC")).isoformat(), "matches": list(by_id.values())}
    temporary = HISTORY.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(HISTORY)


def basketball_game(item):
    home = item.get("home_team") or {}
    away = item.get("visitor_team") or item.get("away_team") or {}
    home_name = home.get("full_name") or home.get("name")
    away_name = away.get("full_name") or away.get("name")
    if not home_name or not away_name:
        return None
    status = str(item.get("status") or "NS").upper()
    if "T" in status and status.endswith("Z"):
        status = "NS"
    if status in {"FINAL", "FT"}:
        status = "FT"
    raw_time = str(item.get("datetime") or "")
    try:
        local_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Minsk"))
        match_date, match_time = local_time.date().isoformat(), local_time.strftime("%H:%M:%S")
    except ValueError:
        match_date, match_time = raw_time[:10], raw_time[11:19] or None
    return {
        "id": "bdl-" + str(item.get("id")),
        "home": home_name,
        "away": away_name,
        "league": "NBA",
        "date": match_date,
        "time": match_time,
        "status": status,
        "home_score": item.get("home_team_score"),
        "away_score": item.get("visitor_team_score"),
        "source": "BALLDONTLIE",
    }


def load_nba(day, key):
    if not key:
        return []
    local_day = datetime.fromisoformat(day).date()
    tomorrow = (local_day + timedelta(days=1)).isoformat()
    provider_dates = [(local_day + timedelta(days=offset)).isoformat() for offset in (-1, 0, 1)]
    response = requests.get(
        BALLDONTLIE_SOURCE,
        params=[("dates[]", value) for value in provider_dates] + [("per_page", 100)],
        headers={"Authorization": key},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    result = []
    for item in payload.get("data", []):
        if isinstance(item, dict):
            match = basketball_game(item)
            if match and (match["date"] == day or (
                match["date"] == tomorrow and match["status"] in {"NS", "SCHEDULED"}
            )):
                result.append(match)
    return result


def normal_name(value):
    return " ".join("".join(char if char.isalnum() else " " for char in str(value or "").lower()).split())


def odds_sport(league):
    name = normal_name(league)
    if "euroleague" in name:
        return "basketball_euroleague"
    if "nbl" in name:
        return "basketball_nbl"
    if "ncaa" in name:
        return "basketball_ncaab"
    return None


def attach_bookmaker_odds(matches, key):
    """Add real moneyline prices for supported non-NBA leagues only."""
    if not key:
        return
    sports = sorted({sport for match in matches if match.get("source") != "BALLDONTLIE" and (sport := odds_sport(match.get("league")))})
    if not sports:
        return
    try:
        cached = json.loads(ODDS_CACHE.read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(cached.get("generated_at", ""))
        cache = cached.get("events") if datetime.now(ZoneInfo("UTC")) - generated.astimezone(ZoneInfo("UTC")) < timedelta(minutes=15) else {}
    except (OSError, ValueError, TypeError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    for sport in sports:
        if sport in cache:
            continue
        response = requests.get(ODDS_SOURCE + "/" + sport + "/odds", params={"apiKey": key, "regions": "us", "markets": "h2h", "oddsFormat": "decimal"}, timeout=20)
        response.raise_for_status()
        events = {}
        for event in response.json():
            home, away = event.get("home_team"), event.get("away_team")
            for bookmaker in event.get("bookmakers") or []:
                market = next((item for item in bookmaker.get("markets") or [] if item.get("key") == "h2h"), None)
                outcomes = {item.get("name"): item.get("price") for item in (market or {}).get("outcomes") or []}
                if home and away and isinstance(outcomes.get(home), (int, float)) and isinstance(outcomes.get(away), (int, float)):
                    events[normal_name(home) + "|" + normal_name(away)] = {"bookmaker": bookmaker.get("title") or bookmaker.get("key") or "Букмекер", "home": round(float(outcomes[home]), 2), "away": round(float(outcomes[away]), 2), "updated_at": bookmaker.get("last_update")}
                    break
        cache[sport] = events
    ODDS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    ODDS_CACHE.write_text(json.dumps({"generated_at": datetime.now(ZoneInfo("UTC")).isoformat(), "events": cache}), encoding="utf-8")
    for match in matches:
        sport = odds_sport(match.get("league"))
        market = (cache.get(sport) or {}).get(normal_name(match.get("home")) + "|" + normal_name(match.get("away")))
        if market:
            match["bookmaker_odds"] = market


def main(*, record_new=True):
    load_dotenv(ROOT / ".env")
    day = datetime.now(ZoneInfo("Europe/Minsk")).date().isoformat()
    tomorrow = (datetime.fromisoformat(day) + timedelta(days=1)).date().isoformat()
    payload = {
        "schema_version": 1,
        "sport": "basketball",
        "requested_date": day,
        "generated_at": datetime.now(ZoneInfo("UTC")).isoformat(),
        "source": "BALLDONTLIE + TheSportsDB",
        "collection_status": "success",
        "matches": [],
    }
    matches = []
    try:
        matches.extend(load_nba(day, os.getenv("BALLDONTLIE_API_KEY")))
    except (requests.RequestException, ValueError):
        payload["collection_status"] = "degraded"
    try:
        response = requests.get(SOURCE, params={"d": day, "s": "Basketball"}, timeout=20)
        response.raise_for_status()
        events = response.json().get("events") or []
        for event in events:
            if not isinstance(event, dict) or not event.get("strHomeTeam") or not event.get("strAwayTeam"):
                continue
            match = {
                "id": event.get("idEvent"),
                "home": event.get("strHomeTeam"),
                "away": event.get("strAwayTeam"),
                "league": event.get("strLeague") or "Лига не указана",
                "date": event.get("dateEvent"),
                "time": event.get("strTime"),
                "status": event.get("strStatus") or "NS",
                "home_score": event.get("intHomeScore"),
                "away_score": event.get("intAwayScore"),
                "source": "TheSportsDB",
            }
            duplicate = any(item["home"] == match["home"] and item["away"] == match["away"] for item in matches)
            if not duplicate:
                matches.append(match)
    except (requests.RequestException, ValueError):
        payload["collection_status"] = "degraded" if matches else "error"
    try:
        attach_bookmaker_odds(matches, os.getenv("ODDS_API_KEY"))
    except (requests.RequestException, ValueError):
        payload["collection_status"] = "degraded" if matches else "error"
    payload["matches"] = [match for match in matches if match["date"] != tomorrow]
    payload["upcoming_matches"] = [match for match in matches if match["date"] == tomorrow]
    save(payload)
    save_history(payload["matches"])
    from basketball_model import build as build_model
    analysis = build_model(matches)
    from basketball_paper_trading import publish as publish_paper, update as update_paper
    if record_new:
        update_paper(payload, analysis)
    else:
        publish_paper()
    from export_shared_finance import main as update_shared_finance
    update_shared_finance()
    print("Баскетбол:", len(payload["matches"]), "матчей за", day,
          "и", len(payload["upcoming_matches"]), "предстоящих матчей за", tomorrow)


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("--forecasts-only", action="store_true",
                        help="Refresh forecasts and results without opening new virtual bets.")
    main(record_new=not parser.parse_args().forecasts_only)
