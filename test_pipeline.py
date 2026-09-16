from agents.risk_manager import RiskManager
from agents.cfo_agent import CFOAgent
from agents.auditor_agent import AuditorAgent


def make_candidate():
    return {
        "status": "READY",
        "event": "Synthetic Test FC vs Test United",
        "prediction": "HOME_WIN",
        "selection": "HOME_WIN",
        "odds": 2.10,
        "model_probability": 55.0,
        "market_probability": 50.0,
        "edge": 5.0,
        "ev": 3.0,
        "bookmaker": "SYNTHETIC_TEST",
        "market": "Match Winner",
        "missing_data": [],
    }


def show(title, data):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)

    for key in (
        "status",
        "risk_level",
        "stake_decision",
        "financial_status",
        "audit_status",
        "recommendation",
        "message",
    ):
        if key in data:
            print(key + ":", data[key])


def main():
    print()
    print("=" * 60)
    print("INTEGRATION PIPELINE TEST")
    print("=" * 60)
    print("Synthetic data only.")
    print("No real bets.")

    # ==========================================================
    # ANALYST
    # ==========================================================

    candidate = make_candidate()

    analyst_output = {
        "status": "success",
        "agent": "Quantitative Sports Analyst",
        "results": [candidate],
        "ready_count": 1,
        "candidate_count": 1,
        "candidates": [candidate],
    }

    print()
    print("ANALYST")
    print("Event:", candidate["event"])
    print("Selection:", candidate["selection"])
    print("Model probability:", candidate["model_probability"])
    print("Market probability:", candidate["market_probability"])
    print("Edge:", candidate["edge"])
    print("EV:", candidate["ev"])

    # ==========================================================
    # RISK MANAGER
    # ==========================================================

    risk = RiskManager()
    risk_output = risk.run(analyst_output)

    show("RISK MANAGER", risk_output)

    # ==========================================================
    # CFO
    # ==========================================================

    cfo = CFOAgent()

    cfo_output = cfo.run(
        risk_output,
        current_exposure=0.0,
    )

    show("CFO", cfo_output)

    # ==========================================================
    # AUDITOR
    # ==========================================================

    auditor = AuditorAgent()

    system_data = {
        "research": {
            "status": "success",
            "fixtures_found": 1,
        },
        "analysis": analyst_output,
        "risk": risk_output,
        "financial_review": cfo_output,
    }

    audit_output = auditor.run(system_data)

    show("AUDITOR", audit_output)

    # ==========================================================
    # FINAL
    # ==========================================================

    print()
    print("=" * 60)
    print("FINAL PIPELINE RESULT")
    print("=" * 60)

    print("Analyst:", analyst_output["status"])
    print("Risk:", risk_output["stake_decision"])
    print("CFO:", cfo_output["financial_status"])
    print("Auditor:", audit_output["audit_status"])
    print("Recommendation:", audit_output["recommendation"])

    print()

    if audit_output["audit_status"] == "FAIL":
        print("PIPELINE TEST: FAIL")
    elif audit_output["audit_status"] == "PASS WITH WARNINGS":
        print("PIPELINE TEST: PASS WITH WARNINGS")
    else:
        print("PIPELINE TEST: PASS")


if __name__ == "__main__":
    main()
