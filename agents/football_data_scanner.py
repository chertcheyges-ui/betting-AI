"""Wide, low-cost pre-match scan using football-data.org's free tier."""

import os
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv


load_dotenv()


class FootballDataScanner:
    """Give up to 50 upcoming matches a transparent first-pass assessment."""

    API_URL = "https://api.football-data.org/v4"
    MAX_MATCHES = 50
    # The free endpoint accepts a date period of at most ten days.
    LOOKAHEAD_DAYS = 10
    MAX_COMPETITIONS_FOR_TABLE = 8

    def __init__(self, token=None, session=None):
        self.token = token or os.getenv("FOOTBALL_DATA_API_KEY")
        self.session = session or requests.Session()
        self.standings = {}
        self.table_requests = 0

    def _get(self, path, **params):
        response = self.session.get(
            self.API_URL + path,
            headers={"X-Auth-Token": self.token},
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _points_per_game(row):
        played = row.get("playedGames") or 0
        return (row.get("points") or 0) / played if played else 0.0

    def _table(self, code):
        if not code:
            return {}
        if code in self.standings:
            return self.standings[code]
        if self.table_requests >= self.MAX_COMPETITIONS_FOR_TABLE:
            return {}
        try:
            self.table_requests += 1
            payload = self._get(f"/competitions/{code}/standings")
            table = next(
                (item.get("table", []) for item in payload.get("standings", [])
                 if item.get("type") == "TOTAL"),
                [],
            )
            result = {
                item.get("team", {}).get("id"): item
                for item in table if item.get("team", {}).get("id") is not None
            }
        except requests.RequestException:
            result = {}
        self.standings[code] = result
        # The free tier permits 10 calls/minute; stay comfortably below it.
        time.sleep(6.2)
        return result

    def _analyse(self, match):
        competition = match.get("competition") or {}
        home = match.get("homeTeam") or {}
        away = match.get("awayTeam") or {}
        table = self._table(competition.get("code"))
        home_row, away_row = table.get(home.get("id")), table.get(away.get("id"))
        if not home_row or not away_row:
            return {
                "prediction": None,
                "confidence": None,
                "message": "Недостаточно данных таблицы для первого прогноза.",
                "data_used": {"standings": False},
            }

        home_strength = self._points_per_game(home_row) + (home_row.get("goalDifference") or 0) / max(home_row.get("playedGames") or 1, 1) * 0.1 + 0.08
        away_strength = self._points_per_game(away_row) + (away_row.get("goalDifference") or 0) / max(away_row.get("playedGames") or 1, 1) * 0.1
        difference = home_strength - away_strength
        if abs(difference) < 0.12:
            prediction = "DRAW"
        else:
            prediction = "HOME_WIN" if difference > 0 else "AWAY_WIN"
        confidence = min(60.0, round(35.0 + abs(difference) * 18.0, 1))
        return {
            "prediction": prediction,
            "confidence": confidence,
            "message": "Первый прогноз по месту и очкам команд в таблице. Для виртуальной ставки этого недостаточно.",
            "data_used": {
                "standings": True,
                "home_position": home_row.get("position"),
                "away_position": away_row.get("position"),
                "home_points": home_row.get("points"),
                "away_points": away_row.get("points"),
                "home_played": home_row.get("playedGames"),
                "away_played": away_row.get("playedGames"),
            },
        }

    def run(self):
        if not self.token:
            return {"status": "error", "message": "FOOTBALL_DATA_API_KEY не найден.", "matches": []}
        today = datetime.now(timezone.utc).date()
        try:
            payload = self._get(
                "/matches",
                dateFrom=today.isoformat(),
                dateTo=(today + timedelta(days=self.LOOKAHEAD_DAYS)).isoformat(),
            )
        except requests.RequestException as error:
            return {"status": "error", "message": str(error), "matches": []}

        candidates = [
            match for match in payload.get("matches", [])
            if match.get("status") in {"SCHEDULED", "TIMED"}
            and (match.get("homeTeam") or {}).get("name")
            and (match.get("awayTeam") or {}).get("name")
        ][:self.MAX_MATCHES]
        rows = []
        for match in candidates:
            competition = match.get("competition") or {}
            home, away = match.get("homeTeam") or {}, match.get("awayTeam") or {}
            rows.append({
                "match_id": match.get("id"),
                "event": f"{home.get('name')} vs {away.get('name')}",
                "kickoff": match.get("utcDate"),
                "league": competition.get("name"),
                "country": (competition.get("area") or {}).get("name"),
                **self._analyse(match),
            })
        return {
            "status": "success",
            "source": "football-data.org",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lookahead_days": self.LOOKAHEAD_DAYS,
            "matches": rows,
            "matches_found": len(rows),
        }
