"""Export neutral match statistics for the dashboard, without private config."""

import argparse
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parent
FORM_FIELDS = ("matches", "wins", "draws", "losses", "goals_for",
               "goals_against", "points_per_game")


def clean_form(value):
    if not isinstance(value, dict):
        return None
    count = value.get("matches")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        return None
    return {
        key: number if (
            not isinstance(number := value.get(key), bool)
            and isinstance(number, (int, float))
            and math.isfinite(number) and number >= 0
        ) else None
        for key in FORM_FIELDS
    }


def make_report(research, data):
    matches = []
    for item in data.get("fixtures", []):
        if not isinstance(item, dict):
            continue
        recent = item.get("recent_form")
        recent = recent if isinstance(recent, dict) else {}
        h2h = item.get("h2h")
        matches.append({
            "home": str(item.get("home") or item.get("home_team") or "Неизвестная команда"),
            "away": str(item.get("away") or item.get("away_team") or "Неизвестная команда"),
            "league": str(item.get("league") or "Лига не указана"),
            "kickoff": item.get("date"),
            "missing": [str(field) for field in item.get("missing_data", [])],
            "home_form": clean_form(recent.get("home")),
            "away_form": clean_form(recent.get("away")),
            "h2h_count": len(h2h) if isinstance(h2h, list) else None,
        })
    status = data.get("status", "error")
    if research.get("status") != "success":
        status = "error"
    if status not in ("success", "degraded", "error"):
        status = "error"
    return {
        "schema_version": 1,
        "demo": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "API-Football и локальный архив проекта",
        "collection_status": status,
        "rate_limited": bool(data.get("api_rate_limited")),
        "matches": matches,
    }


def save_report(report, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                prefix=".match-report-", delete=False) as file:
            temp = Path(file.name)
            json.dump(report, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")
        temp.replace(path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/match-report.json")
    args = parser.parse_args()
    output = args.output.resolve()
    # Existing agent paths resolve relative to the project.
    os.chdir(ROOT)
    from agents.research_agent import ResearchAgent
    from agents.data_manager import DataManager
    research = ResearchAgent().run()
    data = (DataManager().run(research) if research.get("status") == "success"
            else {"status": "error", "fixtures": []})
    report = make_report(research, data)
    save_report(report, output)
    print("Отчёт сохранён:", output)
    print("Матчей:", len(report["matches"]), "| Статус:", report["collection_status"])
    if report["rate_limited"]:
        print("API ограничил запросы. Отчёт содержит неполные данные.")
    return 1 if report["collection_status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
