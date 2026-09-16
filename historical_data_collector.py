import csv
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()


class HistoricalDataCollector:
    """
    Collect historical football fixtures available through API-Football Free plan.

    First target:
        Premier League
        League ID: 39
        Seasons: 2022, 2023, 2024

    Important:
        This collector deliberately does NOT use the `last` parameter.
    """

    BASE_URL = "https://v3.football.api-sports.io"

    LEAGUES = {
        "premier_league": 39,
    }

    SEASONS = (2022, 2023, 2024)

    def __init__(self):
        self.api_key = os.getenv("API_FOOTBALL_KEY")

        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update({
                "x-apisports-key": self.api_key,
            })

        self.raw_dir = Path("data/raw")
        self.processed_dir = Path("data/processed")

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def get(self, endpoint, **params):
        """Make one API request and return response/error."""

        try:
            response = self.session.get(
                f"{self.BASE_URL}{endpoint}",
                params=params,
                timeout=30,
            )

            response.raise_for_status()

            payload = response.json()

            if payload.get("errors"):
                return None, payload["errors"]

            return payload.get("response", []), None

        except requests.RequestException as error:
            return None, str(error)

        except ValueError as error:
            return None, f"Invalid JSON response: {error}"

    @staticmethod
    def compact_fixture(fixture):
        """Convert API fixture into a model-friendly row."""

        fixture_data = fixture.get("fixture", {})
        league = fixture.get("league", {})
        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})

        home = teams.get("home", {})
        away = teams.get("away", {})

        return {
            "fixture_id": fixture_data.get("id"),
            "date": fixture_data.get("date"),

            "league_id": league.get("id"),
            "league": league.get("name"),
            "season": league.get("season"),
            "round": league.get("round"),

            "home_team_id": home.get("id"),
            "home_team": home.get("name"),

            "away_team_id": away.get("id"),
            "away_team": away.get("name"),

            "home_goals": goals.get("home"),
            "away_goals": goals.get("away"),

            "status": fixture_data.get("status", {}).get("short"),
        }

    def collect_league_season(self, league_id, league_name, season):
        print("\n" + "=" * 70)
        print(f"COLLECTING: {league_name}")
        print(f"SEASON:     {season}")
        print(f"LEAGUE ID:  {league_id}")
        print("=" * 70)

        fixtures, error = self.get(
            "/fixtures",
            league=league_id,
            season=season,
        )

        if error:
            print(f"API ERROR: {error}")
            return []

        print(f"Fixtures returned: {len(fixtures)}")

        compact = [
            self.compact_fixture(fixture)
            for fixture in fixtures
        ]

        compact = [
            fixture
            for fixture in compact
            if fixture["fixture_id"]
        ]

        print(f"Valid fixtures: {len(compact)}")

        return compact

    def save_raw(self, league_key, season, fixtures):
        filename = self.raw_dir / f"{league_key}_{season}.json"

        with filename.open("w", encoding="utf-8") as file:
            json.dump(
                fixtures,
                file,
                ensure_ascii=False,
                indent=2,
            )

        print(f"Raw data saved: {filename}")

    def save_csv(self, rows):
        filename = self.processed_dir / "historical_fixtures.csv"

        if not rows:
            print("No rows to save.")
            return

        fieldnames = [
            "fixture_id",
            "date",
            "league_id",
            "league",
            "season",
            "round",
            "home_team_id",
            "home_team",
            "away_team_id",
            "away_team",
            "home_goals",
            "away_goals",
            "status",
        ]

        with filename.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )

            writer.writeheader()
            writer.writerows(rows)

        print(f"\nProcessed dataset saved: {filename}")
        print(f"Rows: {len(rows)}")

    @staticmethod
    def print_summary(rows):
        if not rows:
            print("\nNo historical data collected.")
            return

        completed = [
            row
            for row in rows
            if row.get("status") == "FT"
        ]

        print("\n" + "=" * 70)
        print("COLLECTION SUMMARY")
        print("=" * 70)

        print(f"Total fixtures:      {len(rows)}")
        print(f"Completed fixtures:  {len(completed)}")

        seasons = sorted({
            row.get("season")
            for row in rows
            if row.get("season")
        })

        print(f"Seasons:             {seasons}")

        leagues = sorted({
            row.get("league")
            for row in rows
            if row.get("league")
        })

        print(f"Leagues:             {leagues}")

        if completed:
            print("\nExample completed fixtures:")

            for row in completed[:5]:
                print(
                    f"  {row['date']} | "
                    f"{row['home_team']} "
                    f"{row['home_goals']} - "
                    f"{row['away_goals']} "
                    f"{row['away_team']}"
                )

    def run(self):
        if not self.api_key:
            print(
                "ERROR: API_FOOTBALL_KEY not found in .env"
            )
            return

        all_rows = []

        for league_key, league_id in self.LEAGUES.items():

            for season in self.SEASONS:

                fixtures = self.collect_league_season(
                    league_id=league_id,
                    league_name=league_key,
                    season=season,
                )

                self.save_raw(
                    league_key,
                    season,
                    fixtures,
                )

                all_rows.extend(fixtures)

                # Small pause between requests.
                time.sleep(1)

        self.save_csv(all_rows)

        self.print_summary(all_rows)


if __name__ == "__main__":
    HistoricalDataCollector().run()