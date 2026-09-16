[16.09.26 21:28] Даниил: import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(name)

API_URL = "https://v3.football.api-sports.io/fixtures"

# Часовой пояс, в котором считается "сегодня" и в котором API вернёт время матчей.
DEFAULT_TIMEZONE = "Europe/Moscow"

# Приоритеты по league_id: id в API-Football не меняются, а названия меняются.
# ВАЖНО: id сверить через get_leagues_for_date() перед использованием.
LEAGUE_PRIORITIES = {
    2: 95,    # UEFA Champions League
    3: 90,    # UEFA Europa League
    848: 82,  # UEFA Conference League
    13: 92,   # CONMEBOL Libertadores
    11: 85,   # CONMEBOL Sudamericana
    39: 95,   # Premier League (England)
    140: 94,  # La Liga (Spain)
    135: 93,  # Serie A (Italy)
    78: 93,   # Bundesliga (Germany)
    61: 88,   # Ligue 1 (France)
    137: 76,  # Coppa Italia
    772: 75,  # Leagues Cup
}
DEFAULT_PRIORITY = 30
MIN_PRIORITY = 50

# Берём только матчи, которые ещё не начались.
ALLOWED_STATUSES = {"NS"}  # NS = Not Started

EXCLUDED_KEYWORDS = (
    "u17", "u18", "u19", "u20", "u21", "u23",
    "women", "reserve", "friendl",  # "friendl" ловит и friendly, и friendlies
)

# Данные, которые Research не собирает — их обязан собрать DataManager.
FIELDS_TO_COLLECT = (
    "recent_form", "home_away_form", "h2h", "injuries",
    "lineups", "odds", "odds_movement", "schedule_load",
)


class ResearchAgent:
    """Find and rank priority football fixtures for the data pipeline."""

    def init(self, timezone=DEFAULT_TIMEZONE):
        self.name = "Research Agent"
        self.api_key = os.getenv("API_FOOTBALL_KEY")
        self.timezone = timezone

    def get_priority(self, league_id):
        return LEAGUE_PRIORITIES.get(league_id, DEFAULT_PRIORITY)

    def is_excluded(self, league_name):
        name = (league_name or "").lower()
        return any(keyword in name for keyword in EXCLUDED_KEYWORDS)

    def _error(self, message):
        return {
            "status": "error",
            "agent": self.name,
            "message": message,
            "fixtures": [],
        }

    def _request_fixtures(self, requested_date):
        response = requests.get(
            API_URL,
            headers={"x-apisports-key": self.api_key},
            params={"date": requested_date, "timezone": self.timezone},
            timeout=15,
        )
        remaining = response.headers.get("x-ratelimit-requests-remaining")
        if remaining is not None:
            logger.info("API-Football: осталось запросов на сегодня: %s", remaining)
        response.raise_for_status()
        return response.json()

    def get_leagues_for_date(self, target_date=None):
        """Вспомогательный метод: все лиги за дату, чтобы сверить league_id."""
        requested_date = target_date or datetime.now(ZoneInfo(self.timezone)).date().isoformat()
        payload = self._request_fixtures(requested_date)
        leagues = {}
        for fixture in payload.get("response", []):
            league = fixture.get("league", {})
            leagues[league.get("id")] = (league.get("name"), league.get("country"))
        return leagues

    def run(self, target_date=None):
        """Return not-started priority matches for target_date (today by default)."""
        logger.info("Research Agent started.")

        if not self.api_key:
            return self._error("API_FOOTBALL_KEY not found in .env")

        requested_date = target_date or datetime.now(ZoneInfo(self.timezone)).date().isoformat()

        try:
            payload = self._request_fixtures(requested_date)
        except (requests.RequestException, ValueError) as error:
            return self._error(str(error))

        if payload.get("errors"):
            return self._error(str(payload["errors"]))

        results = []
        skipped = {"status": 0, "excluded": 0, "low_priority": 0, "no_id": 0}
[16.09.26 21:28] Даниил: for fixture in payload.get("response", []):
            fixture_data = fixture.get("fixture", {})
            league = fixture.get("league", {})
            teams = fixture.get("teams", {})
            home = teams.get("home", {})
            away = teams.get("away", {})

            fixture_id = fixture_data.get("id")
            if not fixture_id or not home.get("id") or not away.get("id"):
                skipped["no_id"] += 1
                continue

            status = (fixture_data.get("status") or {}).get("short")
            if status not in ALLOWED_STATUSES:
                skipped["status"] += 1
                continue

            league_name = league.get("name") or ""
            if self.is_excluded(league_name):
                skipped["excluded"] += 1
                continue

            priority = self.get_priority(league.get("id"))
            if priority < MIN_PRIORITY:
                skipped["low_priority"] += 1
                continue

            results.append({
                "fixture_id": fixture_id,
                "id": fixture_id,  # временно, для совместимости; убрать после перехода DataManager на fixture_id
                "date": fixture_data.get("date"),
                "timestamp": fixture_data.get("timestamp"),
                "status": status,
                "home": home.get("name"),
                "away": away.get("name"),
                "home_team_id": home.get("id"),
                "away_team_id": away.get("id"),
                "league": league_name,
                "league_id": league.get("id"),
                "season": league.get("season"),
                "country": league.get("country") or "",
                "round": league.get("round"),
                "research_priority": priority,
                "missing_data": list(FIELDS_TO_COLLECT),
            })

        # Сначала важные лиги, внутри — по времени начала.
        results.sort(key=lambda item: (-item["research_priority"], item["timestamp"] or 0))

        logger.info("Fixtures selected: %s, skipped: %s", len(results), skipped)

        return {
            "status": "success",
            "agent": self.name,
            "requested_date": requested_date,
            "timezone": self.timezone,
            "fixtures_found": len(results),
            "skipped": skipped,
            "fixtures": results,
        }