from agents.research_agent import ResearchAgent
from agents.data_manager import DataManager
from agents.analyst_agent import QuantitativeSportsAnalyst
from agents.risk_manager import RiskManager
from agents.cfo_agent import CFOAgent
from agents.auditor_agent import AuditorAgent
from agents.investment_committee import InvestmentCommittee


def print_summary(research, data, analysis, risk, financial, audit, decision):
    """Print the operating result without dumping raw API data."""
    print("\n=== SYSTEM SUMMARY ===")
    print(f"Research: {research.get('fixtures_found', 0)} priority fixture(s)")
    print(
        "Data: "
        f"{data.get('fixtures_processed', 0)}/{data.get('fixtures_received', 0)} "
        f"processed | {data.get('plan', 'unknown plan')}"
    )

    for event in data.get("fixtures", []):
        print(
            f"  Dataset: {event.get('home')} — {event.get('away')} | "
            f"{event.get('dataset_quality', 0)}% | "
            f"missing: {', '.join(event.get('missing_data', [])) or 'none'}"
        )

    for result in analysis.get("results", []):
        print(
            f"  Analysis: {result.get('event')} | {result.get('status')} | "
            f"missing: {', '.join(result.get('missing_data', [])) or 'none'}"
        )

    print(f"Risk: {risk.get('risk_level')} | {risk.get('stake_decision')}")
    print(
        f"CFO: {financial.get('financial_status')} | "
        f"{financial.get('bank_status')}"
    )
    print(
        f"Audit: {audit.get('audit_status')} | "
        f"{audit.get('recommendation')}"
    )
    print(f"Committee: {decision.get('decision')} | {decision.get('reason')}")


def main():
    print("\n=== BETTING AI SYSTEM ===\n")

    research_data = ResearchAgent().run()
    prepared_data = DataManager().run(research_data)
    analysis = QuantitativeSportsAnalyst().run(prepared_data)
    risk = RiskManager().run(analysis)
    financial_review = CFOAgent().run(risk)
    audit = AuditorAgent().run({
        "research": research_data,
        "analysis": analysis,
        "risk": risk,
        "financial_review": financial_review,
    })
    decision = InvestmentCommittee().run({
        "risk": risk,
        "financial_review": financial_review,
        "audit": audit,
    })

    print_summary(
        research_data,
        prepared_data,
        analysis,
        risk,
        financial_review,
        audit,
        decision,
    )


if __name__ == "__main__":
    main()
