from agents.risk_manager import RiskManager

risk = RiskManager()

tests = [
    {
        "name": "HIGH EDGE",
        "data": {
            "status": "READY",
            "event": "Test High Edge",
            "model_probability": 64.75,
            "market_probability": 47.62,
            "edge": 17.13,
            "ev": 35.97,
        },
    },
    {
        "name": "NORMAL EDGE",
        "data": {
            "status": "READY",
            "event": "Test Normal Edge",
            "model_probability": 55.0,
            "market_probability": 50.0,
            "edge": 5.0,
            "ev": 3.0,
        },
    },
    {
        "name": "LOW EDGE",
        "data": {
            "status": "READY",
            "event": "Test Low Edge",
            "model_probability": 50.0,
            "market_probability": 49.0,
            "edge": 1.0,
            "ev": 0.5,
        },
    },
]

for test in tests:
    print("=" * 60)
    print(test["name"])
    print("=" * 60)

    result = risk.assess(test["data"])

    print("Event:", result["event"])
    print("Risk:", result["risk_level"])
    print("Decision:", result["stake_decision"])
    print("Edge:", result.get("edge"))
    print("EV:", result.get("ev"))
    print("Flags:", result.get("risk_flags"))
    print()
