from agents.data_manager import DataManager
from agents.research_agent import ResearchAgent

print("=" * 60)
print("DATA MANAGER TEST")
print("=" * 60)

research = ResearchAgent()
research_result = research.run()

print("\nResearch status:", research_result.get("status"))
print("Fixtures found:", research_result.get("fixtures_found"))

if not research_result.get("fixtures"):
    print("No fixtures found.")
    raise SystemExit(1)

manager = DataManager(max_fixtures=1)
result = manager.run(research_result)

print("\n" + "=" * 60)
print("DATA MANAGER RESULT")
print("=" * 60)

print("Status:", result.get("status"))
print("Fixtures received:", result.get("fixtures_received"))
print("Fixtures processed:", result.get("fixtures_processed"))

if result.get("fixtures"):
    fixture = result["fixtures"][0]

    print("\nEvent:", fixture.get("home"), "vs", fixture.get("away"))
    print("League:", fixture.get("league"))
    print("Dataset quality:", fixture.get("dataset_quality"))
    print("Dataset complete:", fixture.get("dataset_complete"))

    print("\nRecent form:")
    print(fixture.get("recent_form"))

    print("\nHome/Away form:")
    print(fixture.get("home_away_form"))

    print("\nH2H:")
    print(fixture.get("h2h"))

    print("\nInjuries:")
    print(fixture.get("injuries"))

    print("\nLineups:")
    print(fixture.get("lineups"))

    print("\nOdds:")
    print(fixture.get("odds"))

    print("\nSchedule load:")
    print(fixture.get("schedule_load"))

    print("\nMissing data:")
    print(fixture.get("missing_data"))

    print("\nCollection errors:")
    print(fixture.get("collection_errors"))
