import json
import os
import urllib.request
import urllib.parse

# Load .env without python-dotenv
env_path = ".env"

if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and value:
                os.environ.setdefault(key, value)

api_key = os.getenv("API_FOOTBALL_KEY")

if not api_key:
    print("ERROR: API_FOOTBALL_KEY was not loaded from .env")
    raise SystemExit(1)

fixture_id = 1208021

url = "https://v3.football.api-sports.io/odds?" + urllib.parse.urlencode({
    "fixture": fixture_id
})

request = urllib.request.Request(
    url,
    headers={
        "x-apisports-key": api_key
    }
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        status = response.status
        data = json.load(response)

    print("=" * 70)
    print("API-FOOTBALL ODDS TEST")
    print("=" * 70)

    print("HTTP STATUS:", status)
    print("RESULTS:", len(data.get("response", [])))

    if data.get("errors"):
        print("\nAPI ERRORS:")
        print(json.dumps(data["errors"], indent=2))

    results = data.get("response", [])

    if not results:
        print("\nNo odds returned for fixture:", fixture_id)
        raise SystemExit(0)

    first = results[0]

    print("\nFIXTURE:")
    print(first.get("fixture"))

    bookmakers = first.get("bookmakers", [])

    print("\nBOOKMAKERS:", len(bookmakers))

    for bookmaker in bookmakers[:5]:
        print("\nBOOKMAKER:", bookmaker.get("name"))

        for market in bookmaker.get("bets", []):
            market_name = market.get("name")

            if market_name in (
                "Match Winner",
                "Both Teams Score",
                "Goals Over/Under",
            ):
                print("\nMARKET:", market_name)

                for value in market.get("values", []):
                    print(
                        " ",
                        value.get("value"),
                        "=>",
                        value.get("odd")
                    )

    print("\n" + "=" * 70)
    print("ODDS TEST COMPLETE")
    print("=" * 70)

except Exception as e:
    print("ERROR:", e)
