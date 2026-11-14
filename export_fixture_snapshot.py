"""Fetch a factual football snapshot for the public dashboard."""

import argparse
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from export_match_report import save_report

ROOT = Path(__file__).resolve().parent
HISTORY_PATH = ROOT / "dashboard/site-static/history.json"
REPORT_ARCHIVE_DIR = ROOT / "dashboard/site-static/reports"
REPORT_INDEX_PATH = REPORT_ARCHIVE_DIR / "index.json"
PRIORITY_LEAGUES = {2, 3, 848, 39, 140, 135, 78, 61, 235, 116, 103, 113}
PLAYED_STATUSES = {"FT", "AET", "PEN", "1H", "2H", "HT", "ET", "BT", "P", "LIVE"}
STAT_FIELDS = {
    "Shots on Goal": "shots_on_goal",
    "Total Shots": "total_shots",
    "Ball Possession": "possession",
    "Corner Kicks": "corners",
    "Fouls": "fouls",
    "Yellow Cards": "yellow_cards",
    "Red Cards": "red_cards",
}


class FootballClient:
    def __init__(self, key):
        self.key = key
        self.session = requests.Session()
        self.last_call = None
        self.rate_limited = False
        self.calls = 0

    def get(self, endpoint, **params):
        if self.rate_limited:
            raise RuntimeError("API ограничил запросы; дальнейшие обращения пропущены.")
        if self.last_call is not None:
            time.sleep(max(0, 7.5 - (time.monotonic() - self.last_call)))
        self.last_call = time.monotonic()
        self.calls += 1
        response = None
        for attempt in range(3):
            try:
                response = self.session.get(
                    "https://v3.football.api-sports.io" + endpoint,
                    headers={"x-apisports-key": self.key},
                    params=params, timeout=20,
                )
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        if response is None:
            raise RuntimeError("Не удалось получить ответ от источника.")
        if response.status_code == 429:
            self.rate_limited = True
            raise RuntimeError("Достигнут лимит API (HTTP 429).")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("errors"):
            raise RuntimeError("API вернул ошибку: доступность данных или лимит тарифа.")
        results = payload.get("response")
        if not isinstance(results, list):
            raise RuntimeError("API вернул неожиданный формат.")
        return results


class FallbackScoreClient:
    """Read fixtures and final scores from football-data.org as a reserve."""

    API_URL = "https://api.football-data.org/v4/matches"

    def __init__(self, key):
        self.key = key
        self.session = requests.Session()

    @staticmethod
    def _name(value):
        value = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
        return " ".join(word for word in value.split() if word not in {"fc", "afc", "cf", "sc"})

    @classmethod
    def _same_team(cls, first, second):
        first, second = cls._name(first), cls._name(second)
        return bool(first and second and (first == second or first in second or second in first))

    def finished_score(self, trade):
        """Return one finished match mapped to the paper-trading fixture id."""
        if not self.key:
            return None
        try:
            kickoff = datetime.fromisoformat(str(trade.get("kickoff")).replace("Z", "+00:00"))
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=timezone.utc)
            event_home, event_away = str(trade.get("event") or "").split(" vs ", 1)
            response = self.session.get(
                self.API_URL,
                headers={"X-Auth-Token": self.key},
                params={"date": kickoff.astimezone(timezone.utc).date().isoformat()},
                timeout=20,
            )
            response.raise_for_status()
            for match in response.json().get("matches", []):
                home = (match.get("homeTeam") or {}).get("name")
                away = (match.get("awayTeam") or {}).get("name")
                score = match.get("score") or {}
                full_time = score.get("fullTime") or {}
                if (
                    match.get("status") == "FINISHED"
                    and self._same_team(home, event_home)
                    and self._same_team(away, event_away)
                    and isinstance(full_time.get("home"), int)
                    and isinstance(full_time.get("away"), int)
                ):
                    return {
                        "fixture_id": trade.get("fixture_id"),
                        "home": home, "away": away,
                        "kickoff": match.get("utcDate") or trade.get("kickoff"),
                        "status": "FT",
                        "goals_home": full_time["home"],
                        "goals_away": full_time["away"],
                    }
        except (requests.RequestException, ValueError, AttributeError):
            return None
        return None

    def daily_fixtures(self, requested):
        """Return a provider-neutral schedule when API-Football is empty."""
        if not self.key:
            return []
        try:
            response = self.session.get(
                self.API_URL,
                headers={"X-Auth-Token": self.key},
                params={"dateFrom": requested.isoformat(), "dateTo": requested.isoformat()},
                timeout=20,
            )
            response.raise_for_status()
            status_map = {"SCHEDULED": "NS", "TIMED": "NS", "IN_PLAY": "LIVE", "PAUSED": "HT", "FINISHED": "FT"}
            result = []
            for item in response.json().get("matches", []):
                home, away = item.get("homeTeam") or {}, item.get("awayTeam") or {}
                if not home.get("name") or not away.get("name"):
                    continue
                score = item.get("score") or {}
                full_time = score.get("fullTime") or {}
                competition = item.get("competition") or {}
                result.append({
                    "fixture_id": "fd-" + str(item.get("id")), "home": home["name"], "away": away["name"],
                    "league": competition.get("name") or "Лига не указана",
                    "country": (competition.get("area") or {}).get("name") or "", "kickoff": item.get("utcDate"),
                    "status": status_map.get(str(item.get("status") or "").upper(), "TBD"), "elapsed": None,
                    "goals_home": full_time.get("home"), "goals_away": full_time.get("away"),
                    "home_form": None, "away_form": None, "h2h_count": None, "home_stats": None, "away_stats": None,
                    "statistics_state": "reserve_source", "missing": ["recent_form", "match_statistics"],
                    "source": "football-data.org",
                })
            return result
        except (requests.RequestException, ValueError, AttributeError):
            return []


class OpenLigaScoreClient:
    """No-key fallback for finished German Bundesliga fixtures."""

    API_URL = "https://api.openligadb.de/getmatchdata"

    def __init__(self):
        self.session = requests.Session()

    def finished_score(self, trade):
        league = str(trade.get("league") or "").casefold()
        if "bundesliga" not in league:
            return None
        try:
            kickoff = datetime.fromisoformat(str(trade.get("kickoff")).replace("Z", "+00:00"))
            event_home, event_away = str(trade.get("event") or "").split(" vs ", 1)
            response = self.session.get(f"{self.API_URL}/bl1/{kickoff.year}", timeout=20)
            response.raise_for_status()
            for match in response.json():
                home = (match.get("team1") or {}).get("teamName")
                away = (match.get("team2") or {}).get("teamName")
                results = match.get("matchResults") or []
                final = next((item for item in reversed(results) if item.get("pointsTeam1") is not None and item.get("pointsTeam2") is not None), None)
                if (
                    match.get("matchIsFinished")
                    and final
                    and FallbackScoreClient._same_team(home, event_home)
                    and FallbackScoreClient._same_team(away, event_away)
                ):
                    return {
                        "fixture_id": trade.get("fixture_id"), "home": home, "away": away,
                        "kickoff": trade.get("kickoff"), "status": "FT",
                        "goals_home": int(final["pointsTeam1"]), "goals_away": int(final["pointsTeam2"]),
                        "score_source": "OpenLigaDB",
                    }
        except (requests.RequestException, ValueError, AttributeError, TypeError):
            return None
        return None


class SportsDbScoreClient:
    """Last-resort public lookup through TheSportsDB's free v1 endpoint."""

    API_URL = "https://www.thesportsdb.com/api/v1/json/123/searchevents.php"

    def __init__(self):
        self.session = requests.Session()

    def finished_score(self, trade):
        try:
            event_home, event_away = str(trade.get("event") or "").split(" vs ", 1)
            kickoff = datetime.fromisoformat(str(trade.get("kickoff")).replace("Z", "+00:00"))
            response = self.session.get(
                self.API_URL,
                params={"e": f"{event_home}_vs_{event_away}"}, timeout=20,
            )
            response.raise_for_status()
            for match in response.json().get("event") or []:
                home, away = match.get("strHomeTeam"), match.get("strAwayTeam")
                match_date = match.get("dateEvent")
                home_score, away_score = match.get("intHomeScore"), match.get("intAwayScore")
                if (
                    match_date == kickoff.date().isoformat()
                    and FallbackScoreClient._same_team(home, event_home)
                    and FallbackScoreClient._same_team(away, event_away)
                    and str(home_score).isdigit() and str(away_score).isdigit()
                ):
                    return {
                        "fixture_id": trade.get("fixture_id"), "home": home, "away": away,
                        "kickoff": trade.get("kickoff"), "status": "FT",
                        "goals_home": int(home_score), "goals_away": int(away_score),
                        "score_source": "TheSportsDB",
                    }
        except (requests.RequestException, ValueError, AttributeError):
            return None
        return None


class SofaScoreClient:
    """Independent public web fallback for final football scores."""

    API_URL = "https://www.sofascore.com/api/v1/sport/football/scheduled-events"

    def __init__(self):
        self.session = requests.Session()

    def finished_score(self, trade):
        try:
            event_home, event_away = str(trade.get("event") or "").split(" vs ", 1)
            kickoff = datetime.fromisoformat(str(trade.get("kickoff")).replace("Z", "+00:00"))
            date_key = kickoff.astimezone(timezone.utc).date().isoformat()
            response = self.session.get(f"{self.API_URL}/{date_key}", timeout=20)
            response.raise_for_status()
            for event in response.json().get("events") or []:
                home = (event.get("homeTeam") or {}).get("name")
                away = (event.get("awayTeam") or {}).get("name")
                status = (event.get("status") or {}).get("type")
                home_score = (event.get("homeScore") or {}).get("current")
                away_score = (event.get("awayScore") or {}).get("current")
                if (
                    status == "finished"
                    and FallbackScoreClient._same_team(home, event_home)
                    and FallbackScoreClient._same_team(away, event_away)
                    and isinstance(home_score, int) and isinstance(away_score, int)
                ):
                    return {
                        "fixture_id": trade.get("fixture_id"), "home": home, "away": away,
                        "kickoff": trade.get("kickoff"), "status": "FT",
                        "goals_home": home_score, "goals_away": away_score,
                        "score_source": "SofaScore (резервный интернет-источник)",
                    }
        except (requests.RequestException, ValueError, AttributeError):
            return None
        return None


def reserve_finished_score(trade, providers):
    """Ask every independent fallback before leaving an overdue match open."""
    for provider in providers:
        result = provider.finished_score(trade)
        if result:
            return result
    return None


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(str(value).rstrip("%"))
        return result if 0 <= result < float("inf") else None
    except (TypeError, ValueError):
        return None


def compact_fixture(item):
    fixture = item.get("fixture") or {}
    teams = item.get("teams") or {}
    league = item.get("league") or {}
    home, away = teams.get("home") or {}, teams.get("away") or {}
    goals = item.get("goals") or {}
    status = fixture.get("status") or {}
    status_code = status.get("short") or "TBD"
    return {
        "fixture_id": fixture.get("id"),
        "home": home.get("name") or "Не указано",
        "away": away.get("name") or "Не указано",
        "league": league.get("name") or "Лига не указана",
        "country": league.get("country") or "",
        "kickoff": fixture.get("date"),
        "status": status_code,
        "elapsed": status.get("elapsed"),
        "goals_home": goals.get("home"),
        "goals_away": goals.get("away"),
        "home_form": None, "away_form": None, "h2h_count": None,
        "home_stats": None, "away_stats": None,
        "statistics_state": "not_requested",
        "missing": ["recent_form", "match_statistics"],
        "score_source": "API-Football" if status_code in {"FT", "AET", "PEN", "AWD", "WO"} else None,
    }


def attach_stats(match, payload, home_id, away_id):
    found = {}
    for entry in payload:
        team_id = (entry.get("team") or {}).get("id")
        stats = {}
        for item in entry.get("statistics") or []:
            key = STAT_FIELDS.get(item.get("type"))
            if key:
                value = number(item.get("value"))
                stats[key] = value if key != "possession" or value is None or value <= 100 else None
        if any(value is not None for value in stats.values()):
            found[team_id] = stats
    match["home_stats"], match["away_stats"] = found.get(home_id), found.get(away_id)
    if match["home_stats"] and match["away_stats"]:
        match["statistics_state"] = "available"
        match["missing"] = ["recent_form"]
    else:
        match["statistics_state"] = "unavailable"


def archive_completed_matches(report):
    """Keep a compact, de-duplicated archive for the dashboard history tab."""
    finished = {"FT", "AET", "PEN", "AWD", "WO"}
    existing = {"schema_version": 1, "updated_at": None, "matches": []}
    try:
        with HISTORY_PATH.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict) and isinstance(loaded.get("matches"), list):
            existing = loaded
    except (OSError, ValueError):
        pass

    records = {
        str(item.get("fixture_id")): item
        for item in existing.get("matches", [])
        if isinstance(item, dict) and item.get("fixture_id") is not None
    }
    for match in report.get("matches", []):
        if match.get("status") not in finished or match.get("fixture_id") is None:
            continue
        fixture_id = str(match["fixture_id"])
        records[fixture_id] = {
            key: match.get(key) for key in (
                "fixture_id", "home", "away", "league", "country", "kickoff",
                "status", "goals_home", "goals_away", "home_stats", "away_stats",
                "score_source",
            )
        }

    archive = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "matches": sorted(
            records.values(), key=lambda item: item.get("kickoff") or "", reverse=True
        )[:1000],
    }
    save_report(archive, HISTORY_PATH)


def open_trade_fixtures(now=None):
    """Return only unfinished matches that should reasonably be over.

    Calling the score provider before kickoff wastes the limited free quota.
    A match is first checked two hours after its scheduled start; if it is
    still in play, a later scheduled run will check it again.
    """
    path = ROOT / "data" / "paper_trades.json"
    try:
        with path.open("r", encoding="utf-8") as file:
            trades = json.load(file).get("trades", [])
    except (OSError, ValueError, AttributeError):
        return []
    now = now or datetime.now(timezone.utc)
    result = []
    for trade in trades:
        if not isinstance(trade, dict) or trade.get("status") != "OPEN":
            continue
        fixture_id = trade.get("fixture_id")
        if fixture_id is None:
            continue
        try:
            kickoff = datetime.fromisoformat(str(trade.get("kickoff")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            # Old records without a valid time are checked rather than lost.
            result.append({"fixture_id": fixture_id, "event": trade.get("event"), "kickoff": trade.get("kickoff"), "league": (trade.get("evidence_at_decision") or {}).get("league")})
            continue
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        if now >= kickoff.astimezone(timezone.utc) + timedelta(minutes=110):
            result.append({"fixture_id": fixture_id, "event": trade.get("event"), "kickoff": trade.get("kickoff"), "league": (trade.get("evidence_at_decision") or {}).get("league")})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--max-fixtures", type=int, default=16)
    parser.add_argument("--statistics", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT / "dashboard/site-static/latest-report.json")
    args = parser.parse_args()
    if not 1 <= args.max_fixtures <= 100 or not 0 <= args.statistics <= 5:
        parser.error("max-fixtures: 1–100; statistics: 0–5")
    load_dotenv(ROOT / ".env")
    key = os.getenv("API_FOOTBALL_KEY")
    if not key:
        print("В .env отсутствует API_FOOTBALL_KEY.")
        return 1
    requested = args.date or datetime.now(ZoneInfo("Europe/Minsk")).date()
    client = FootballClient(key)
    fallback = FallbackScoreClient(os.getenv("FOOTBALL_DATA_API_KEY"))
    openliga = OpenLigaScoreClient()
    sportsdb = SportsDbScoreClient()
    sofascore = SofaScoreClient()
    score_providers = (fallback, openliga, sportsdb, sofascore)
    degraded = False
    matches_by_id = {}
    # First close old virtual matches. This always takes priority over new fixtures.
    for trade in open_trade_fixtures():
        fixture_id = trade["fixture_id"]
        match = None
        try:
            result = client.get("/fixtures", id=fixture_id, timezone="Europe/Minsk")
            if result:
                match = compact_fixture(result[0])
                matches_by_id[str(match["fixture_id"])] = match
        except (requests.RequestException, ValueError, RuntimeError) as error:
            degraded = True
            print(f"Не удалось проверить старый матч {fixture_id}: {error}")
        # The primary API can answer with an unfinished or empty record long
        # after the final whistle.  Always ask reserve sources in that case.
        if not match or match.get("status") not in {"FT", "AET", "PEN", "AWD", "WO"}:
            backup = reserve_finished_score(trade, score_providers)
            if backup:
                matches_by_id[str(fixture_id)] = backup
                print(f"Итог матча {fixture_id} получен из резервного источника: {backup.get('score_source', 'резерв')}.")
            elif not match:
                print(f"Аудит счёта: для завершённого матча {fixture_id} пока не найден подтверждённый итог ни в одном источнике.")
    used_reserve_schedule = False
    try:
        fixtures = client.get("/fixtures", date=requested.isoformat(), timezone="Europe/Minsk")
    except (requests.RequestException, ValueError, RuntimeError) as error:
        print("Не удалось обновить снимок:", error)
        fixtures = []
        degraded = True
    usable = [item for item in fixtures if isinstance(item, dict)
              and (item.get("fixture") or {}).get("id")
              and ((item.get("teams") or {}).get("home") or {}).get("name")
              and ((item.get("teams") or {}).get("away") or {}).get("name")]
    usable.sort(key=lambda item: (
        0 if (item.get("league") or {}).get("id") in PRIORITY_LEAGUES else 1,
        (item.get("fixture") or {}).get("timestamp") or 0,
    ))
    selected = usable[:args.max_fixtures]
    matches = [compact_fixture(item) for item in selected]
    # A blank primary answer is often a temporary free-tier outage.  The
    # reserve source keeps the dashboard informative, but marks its limits.
    if not matches:
        reserve_matches = fallback.daily_fixtures(requested)
        if reserve_matches:
            matches = reserve_matches[:args.max_fixtures]
            used_reserve_schedule = True
            degraded = True
    for match in matches:
        matches_by_id[str(match["fixture_id"])] = match
    requested_stats = 0
    for item, match in zip(selected, matches):
        if match["status"] not in PLAYED_STATUSES:
            match["statistics_state"] = "not_started"
            continue
        if requested_stats >= args.statistics:
            continue
        requested_stats += 1
        teams = item.get("teams") or {}
        try:
            result = client.get("/fixtures/statistics", fixture=match["fixture_id"])
            attach_stats(match, result, teams["home"]["id"], teams["away"]["id"])
        except (requests.RequestException, ValueError, RuntimeError, KeyError):
            degraded = True
            match["statistics_state"] = "request_error"
    report = {
        "schema_version": 1, "demo": False, "report_kind": "fixture_statistics",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "requested_date": requested.isoformat(), "source": "football-data.org (резерв)" if used_reserve_schedule else "API-Football",
        "collection_status": "degraded" if degraded else "success",
        "rate_limited": client.rate_limited,
        "fixtures_found": len(matches) if used_reserve_schedule else len(usable), "matches": list(matches_by_id.values()),
    }
    # If the source is temporarily unavailable, retain the last good screen
    # instead of replacing it with an empty list of matches.
    if matches_by_id or not degraded:
        save_report(report, args.output.resolve())
        # The main screen uses one current snapshot, but past dates need their
        # own immutable copy so they remain available in the match archive.
        REPORT_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archive_path = REPORT_ARCHIVE_DIR / f"{requested.isoformat()}.json"
        save_report(report, archive_path)
        try:
            index = json.loads(REPORT_INDEX_PATH.read_text(encoding="utf-8"))
            reports = index.get("reports", []) if isinstance(index, dict) else []
        except (OSError, ValueError):
            reports = []
        reports = [item for item in reports if isinstance(item, dict) and item.get("date") != requested.isoformat()]
        reports.append({"date": requested.isoformat(), "generated_at": report["generated_at"], "matches": len(report["matches"])})
        reports.sort(key=lambda item: str(item.get("date", "")), reverse=True)
        REPORT_INDEX_PATH.write_text(json.dumps({"reports": reports}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        print("Снимок не перезаписан: источник временно недоступен, сохранены последние удачные данные.")
    archive_completed_matches(report)
    from paper_trading import evaluate
    evaluate(HISTORY_PATH)
    print("Дата матчей:", requested)
    print("Найдено:", len(usable), "| В снимке:", len(matches_by_id), "| Запросов API:", client.calls)
    print("Матчей со статистикой:", sum(m["statistics_state"] == "available" for m in matches))
    print("Сохранено:", args.output.resolve())
    for match in matches[:5]:
        print(match["home"], "—", match["away"], "|", match["status"],
              "|", match["goals_home"], ":", match["goals_away"])
    # A degraded-but-populated fallback is useful.  A completely empty result
    # after an outage is not a valid refresh and lets the caller preserve the
    # last complete dashboard status.
    return 1 if degraded and not matches_by_id else 0


if __name__ == "__main__":
    raise SystemExit(main())
