"""Create a safe dashboard snapshot of the full betting-analysis pipeline."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dashboard" / "site-static" / "system-status.json"
BROAD_OUTPUT = ROOT / "dashboard" / "site-static" / "broad-analysis.json"
DASHBOARD_REPORT = ROOT / "dashboard" / "site-static" / "latest-report.json"


def clean_candidate(item):
    """Keep public decision fields only; omit raw provider and configuration data."""
    if not isinstance(item, dict):
        return None
    fields = (
        "event", "selection", "prediction", "odds", "model_probability",
        "market_probability", "edge", "ev", "risk_level", "stake_decision",
        "financial_decision", "maximum_position", "currency", "message",
        "status", "market", "bookmaker", "confidence_cap", "confidence_note",
        "dataset_quality", "lineups_confirmed",
    )
    return {field: item[field] for field in fields if field in item}


def research_fixture_for_dashboard(item):
    """Keep the full low-cost fixture list visible without provider details."""
    if not isinstance(item, dict):
        return None
    home, away = item.get("home"), item.get("away")
    if not home or not away:
        return None
    return {
        "fixture_id": item.get("fixture_id"),
        "event": f"{home} vs {away}",
        "kickoff": item.get("date"),
        "league": item.get("league"),
        "country": item.get("country"),
        "priority": item.get("research_priority"),
    }


def evidence_for_dashboard(fixture):
    """Return the football information used for a forecast, without credentials."""
    if not isinstance(fixture, dict):
        return {}
    fields = (
        "fixture_id", "home", "away", "league", "country", "date",
        "recent_form", "home_away_form", "h2h", "injuries", "lineups",
        "odds", "schedule_load", "missing_data", "collection_errors",
        "external_source_status", "external_search_for", "external_signals", "external_review_required",
        "dataset_complete", "dataset_quality",
    )
    return {field: fixture.get(field) for field in fields if field in fixture}


def save_json(payload, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent,
            prefix=".system-status-", delete=False,
        ) as file:
            temporary = Path(file.name)
            json.dump(payload, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")
        temporary.replace(output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def load_json(path):
    try:
        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def detail_candidates(research, broad):
    """Choose a variable-size shortlist for expensive detailed checks.

    The free first pass only indicates whether a match is worth looking at.
    It never creates a virtual bet: odds, expected value and risk are still
    validated by the detailed pipeline.
    """
    today = datetime.now(ZoneInfo("Europe/Minsk")).date().isoformat()
    # The free wide scan is a useful filter, but a missing standing table
    # must not prevent every detailed check.  In that case, inspect a small
    # set of the highest-priority matches that actually start today.
    if broad.get("status") != "success":
        return [
            fixture for fixture in research.get("fixtures", [])
            if isinstance(fixture, dict) and str(fixture.get("date") or "").startswith(today)
        ][:3]
    first_pass = {
        str(item.get("event")).strip().casefold(): item
        for item in broad.get("matches", [])
        if isinstance(item, dict)
    }
    candidates = []
    for fixture in research.get("fixtures", []):
        if not isinstance(fixture, dict):
            continue
        event = f"{fixture.get('home')} vs {fixture.get('away')}"
        preview = first_pass.get(event.casefold(), {})
        confidence = preview.get("confidence")
        # 50% means the quick scan sees a strong enough difference to spend
        # limited detailed-data requests. It is still not a betting decision.
        if isinstance(confidence, (int, float)) and confidence >= 50:
            candidates.append(fixture)
    if candidates:
        return candidates
    return [
        fixture for fixture in research.get("fixtures", [])
        if isinstance(fixture, dict) and str(fixture.get("date") or "").startswith(today)
    ][:3]


def main():
    os.chdir(ROOT)
    from agents.research_agent import ResearchAgent
    from agents.data_manager import DataManager
    from agents.analyst_agent import QuantitativeSportsAnalyst
    from agents.risk_manager import RiskManager
    from agents.cfo_agent import CFOAgent
    from agents.auditor_agent import AuditorAgent
    from agents.investment_committee import InvestmentCommittee
    from agents.football_data_scanner import FootballDataScanner

    research = ResearchAgent().run()
    broad = FootballDataScanner().run()
    # Keep the latest successful wide scan visible when its free provider is
    # temporarily unavailable. This is display-only and never creates bets.
    if broad.get("status") != "success":
        previous_broad = load_json(BROAD_OUTPUT)
        if previous_broad and previous_broad.get("status") == "success" and previous_broad.get("matches"):
            broad = {
                **previous_broad,
                "stale": True,
                "last_error": broad.get("message", "Источник временно недоступен."),
            }
    from wide_paper_test import evaluate as evaluate_wide_test, record as record_wide_test
    record_wide_test(broad)
    evaluate_wide_test()
    selected_for_detail = detail_candidates(research, broad)
    # The number is intentionally not fixed: detailed API calls are used only
    # for matches that passed the free first-pass scan.
    detail_research = {**research, "fixtures": selected_for_detail}
    data = DataManager(max_fixtures=len(selected_for_detail)).run(detail_research)
    analysis = QuantitativeSportsAnalyst().run(data)
    risk = RiskManager().run(analysis)
    financial = CFOAgent().run(risk)
    audit = AuditorAgent().run({
        "research": research, "data": data, "analysis": analysis,
        "risk": risk, "financial_review": financial,
        "dashboard_report": load_json(DASHBOARD_REPORT),
    })
    decision = InvestmentCommittee().run({
        "risk": risk, "financial_review": financial, "audit": audit,
    })

    # A temporary provider failure can look like a technically successful
    # empty scan.  Do not replace a useful screen (and its active virtual
    # decisions) with a zero-match report in that case.
    previous_status = load_json(OUTPUT)
    empty_refresh = (
        not research.get("fixtures_found", 0)
        and not data.get("fixtures_processed", 0)
        and not analysis.get("results", [])
    )
    if empty_refresh and previous_status and (
        (previous_status.get("analysis") or {}).get("forecasts")
        or (previous_status.get("research") or {}).get("fixtures")
    ):
        print("Пустое обновление пропущено: на странице сохранён предыдущий полноценный отчёт.")
        from export_basketball_snapshot import main as update_basketball
        update_basketball(record_new=False)
        return

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research": {
            "status": research.get("status"),
            "fixtures_found": research.get("fixtures_found", 0),
            "requested_date": research.get("requested_date"),
            "fixtures": [
                fixture for fixture in
                (research_fixture_for_dashboard(item) for item in research.get("fixtures", []))
                if fixture is not None
            ],
        },
        "data": {
            "status": data.get("status"),
            "fixtures_processed": data.get("fixtures_processed", 0),
            "candidates_for_detail": len(selected_for_detail),
            "api_rate_limited": bool(data.get("api_rate_limited")),
        },
        "analysis": {
            "status": analysis.get("status"),
            "ready_count": analysis.get("ready_count", 0),
            "forecasts": [
                candidate for candidate in
                (clean_candidate(item) for item in analysis.get("results", []))
                if candidate is not None
            ],
        },
        "risk": {"risk_level": risk.get("risk_level"), "stake_decision": risk.get("stake_decision"), "candidates": [candidate for candidate in (clean_candidate(item) for item in risk.get("candidates_for_cfo", [])) if candidate is not None]},
        "financial": {"bankroll": financial.get("bankroll"), "daily_risk_limit": financial.get("daily_risk_limit"), "current_exposure": financial.get("current_exposure"), "remaining_daily_risk": financial.get("remaining_daily_risk"), "financial_status": financial.get("financial_status"), "approved_candidates": [candidate for candidate in (clean_candidate(item) for item in financial.get("approved_candidates", [])) if candidate is not None]},
        "audit": {"audit_status": audit.get("audit_status"), "recommendation": audit.get("recommendation"), "dashboard_check": audit.get("dashboard_check")},
        "committee": {"decision": decision.get("decision"), "reason": decision.get("reason")},
    }
    fixtures_by_event = {
        f"{item.get('home')} vs {item.get('away')}": item
        for item in data.get("fixtures", []) if isinstance(item, dict)
    }
    for forecast in payload["analysis"]["forecasts"]:
        fixture = fixtures_by_event.get(forecast.get("event"), {})
        forecast["fixture_id"] = fixture.get("fixture_id")
        forecast["kickoff"] = fixture.get("date")
        forecast["evidence"] = evidence_for_dashboard(fixture)
        source = next((item for item in analysis.get("results", []) if item.get("event") == forecast.get("event")), {})
        forecast["model_probabilities"] = source.get("model_probabilities")
    payload["analysis"]["match_details"] = [
        {
            "fixture_id": fixture.get("fixture_id"),
            "event": f"{fixture.get('home')} vs {fixture.get('away')}",
            "kickoff": fixture.get("date"),
            "recommendation": next(
                (forecast for forecast in payload["analysis"]["forecasts"]
                 if forecast.get("fixture_id") == fixture.get("fixture_id")),
                None,
            ),
            "evidence": evidence_for_dashboard(fixture),
        }
        for fixture in data.get("fixtures", []) if isinstance(fixture, dict)
    ]
    save_json(payload, OUTPUT)
    save_json(broad, BROAD_OUTPUT)
    from paper_trading import record_forecasts, evaluate
    record_forecasts(payload)
    evaluate(ROOT / "dashboard" / "site-static" / "history.json")
    # Basketball has its own data file and never affects football forecasts,
    # finances, or the football audit.
    from export_basketball_snapshot import main as update_basketball
    update_basketball()
    from export_shared_finance import main as update_shared_finance
    update_shared_finance()
    print("Dashboard status saved:", OUTPUT)


if __name__ == "__main__":
    main()
