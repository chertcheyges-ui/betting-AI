import os
from datetime import date, timedelta

import requests
from dotenv import load_dotenv


load_dotenv()

BASE_URL = "https://v3.football.api-sports.io"
API_KEY = os.getenv("API_FOOTBALL_KEY")


def call_api(endpoint, **params):
    print(f"\n{'=' * 70}")
    print(f"ENDPOINT: {endpoint}")
    print(f"PARAMS:   {params}")

    try:
        response = requests.get(
            f"{BASE_URL}{endpoint}",
            headers={"x-apisports-key": API_KEY},
            params=params,
            timeout=15,
        )

        print(f"HTTP STATUS: {response.status_code}")

        payload = response.json()

        if payload.get("errors"):
            print("API ERRORS:")
            print(payload["errors"])
            return None

        results = payload.get("response", [])

        print(f"RESULT COUNT: {len(results)}")

        if results:
            first = results[0]

            if isinstance(first, dict):
                print("FIRST RESULT KEYS:")
                print(sorted(first.keys()))

        return results

    except Exception as error:
        print(f"ERROR: {error}")
        return None


def print_fixture_details(fixtures):
    if not fixtures:
        return

    fixture = fixtures[0]

    print("\nFIRST FIXTURE SUMMARY:")

    details = fixture.get("fixture", {})
    league = fixture.get("league", {})
    teams = fixture.get("teams", {})
    goals = fixture.get("goals", {})

    print("fixture_id:", details.get("id"))
    print("date:", details.get("date"))
    print("league:", league.get("name"))
    print("home:", teams.get("home", {}).get("name"))
    print("away:", teams.get("away", {}).get("name"))
    print("home_goals:", goals.get("home"))
    print("away_goals:", goals.get("away"))


def main():
    print("\n=== API-FOOTBALL DIAGNOSTIC ===\n")

    if not API_KEY:
        print("ERROR: API_FOOTBALL_KEY not found in .env")
        return

    # ------------------------------------------------------------------
    # 1. Fixtures for today
    # ------------------------------------------------------------------

    today = date.today().isoformat()

    fixtures = call_api(
        "/fixtures",
        date=today,
    )

    print_fixture_details(fixtures)

    if not fixtures:
        print("\nNo fixtures returned for today.")
        return

    # Pick the first fixture that has valid IDs.
    selected = None

    for fixture in fixtures:
        fixture_id = fixture.get("fixture", {}).get("id")
        teams = fixture.get("teams", {})

        home_id = teams.get("home", {}).get("id")
        away_id = teams.get("away", {}).get("id")

        if fixture_id and home_id and away_id:
            selected = {
                "fixture_id": fixture_id,
                "home_id": home_id,
                "away_id": away_id,
                "home": teams.get("home", {}).get("name"),
                "away": teams.get("away", {}).get("name"),
            }
            break

    if not selected:
        print("\nCould not find a usable fixture.")
        return

    print("\nSELECTED FIXTURE:")
    print(selected)

    fixture_id = selected["fixture_id"]
    home_id = selected["home_id"]
    away_id = selected["away_id"]

    # ------------------------------------------------------------------
    # 2. Head-to-head
    # ------------------------------------------------------------------

    h2h = call_api(
        "/fixtures/headtohead",
        h2h=f"{home_id}-{away_id}",
    )

    if h2h:
        print("\nH2H FIRST MATCH:")
        print_fixture_details(h2h)

    # ------------------------------------------------------------------
    # 3. Injuries
    # ------------------------------------------------------------------

    injuries = call_api(
        "/injuries",
        fixture=fixture_id,
    )

    if injuries:
        print("\nINJURIES FIRST RESULT:")
        print(injuries[0])

    # ------------------------------------------------------------------
    # 4. Lineups
    # ------------------------------------------------------------------

    lineups = call_api(
        "/fixtures/lineups",
        fixture=fixture_id,
    )

    if lineups:
        print("\nLINEUPS FIRST RESULT:")
        print(lineups[0])

    # ------------------------------------------------------------------
    # 5. Odds
    # ------------------------------------------------------------------

    odds = call_api(
        "/odds",
        fixture=fixture_id,
    )

    if odds:
        print("\nODDS FIRST RESULT:")

        bookmaker_list = odds[0].get("bookmakers", [])

        print("BOOKMAKERS:", len(bookmaker_list))

        if bookmaker_list:
            bookmaker = bookmaker_list[0]

            print("BOOKMAKER:", bookmaker.get("name"))

            for market in bookmaker.get("bets", []):
                print(
                    "MARKET:",
                    market.get("name"),
                    "| values:",
                    market.get("values"),
                )

    # ------------------------------------------------------------------
    # 6. Historical fixtures WITHOUT `last`
    # ------------------------------------------------------------------

    historical_date = (date.today() - timedelta(days=7)).isoformat()

    historical = call_api(
        "/fixtures",
        team=home_id,
        date=historical_date,
    )

    print("\nHISTORICAL TEST:")
    print(f"Team ID: {home_id}")
    print(f"Date: {historical_date}")
    print(f"Returned matches: {len(historical or [])}")

    # ------------------------------------------------------------------
    # 7. Team fixtures by season
    # ------------------------------------------------------------------

    current_year = date.today().year

    season_test = call_api(
        "/fixtures",
        team=home_id,
        season=current_year,
    )

    print("\nSEASON TEST:")
    print(f"Team ID: {home_id}")
    print(f"Season: {current_year}")
    print(f"Returned matches: {len(season_test or [])}")

    # ------------------------------------------------------------------
    # Final
    # ------------------------------------------------------------------

    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)

    print(
        """
DO NOT SEND YOUR API KEY.

Send me the terminal output from this script.
I only need the diagnostic results.
"""
    )


if __name__ == "__main__":
    main()