"""Risk controls for candidate bets produced by QuantitativeSportsAnalyst."""


class RiskManager:
    """Apply hard risk gates before a candidate reaches the CFO agent."""

    MIN_EDGE_PERCENT = 2.0
    MIN_EV_PERCENT = 1.0
    MAX_EDGE_PERCENT = 15.0

    def __init__(self):
        self.name = "Risk Manager"

    @staticmethod
    def _number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def assess(self, analysis):
        """Return a no-bet decision unless the analyst provides valid metrics."""
        event = analysis.get("event", "Unknown event")
        missing_data = analysis.get("missing_data", [])

        if analysis.get("status") != "READY":
            return {
                "event": event,
                "risk_level": "BLOCKED",
                "stake_decision": "NO BET",
                "risk_flags": ["Dataset is incomplete."],
                "missing_data": missing_data,
                "message": "Risk review stopped until the analyst dataset is complete.",
            }

        edge = self._number(analysis.get("edge"))
        ev = self._number(analysis.get("ev"))
        model_probability = self._number(analysis.get("model_probability"))
        market_probability = self._number(analysis.get("market_probability"))

        missing_metrics = [
            name for name, value in (
                ("model_probability", model_probability),
                ("market_probability", market_probability),
                ("edge", edge),
                ("ev", ev),
            )
            if value is None
        ]
        if missing_metrics:
            return {
                "event": event,
                "risk_level": "BLOCKED",
                "stake_decision": "NO BET",
                "risk_flags": ["Required quantitative metrics are missing."],
                "missing_metrics": missing_metrics,
                "message": "Risk review requires validated model probability, edge, and EV.",
            }

        flags = []
        if edge < self.MIN_EDGE_PERCENT:
            flags.append(f"Edge below {self.MIN_EDGE_PERCENT:.1f}%.")
        if ev < self.MIN_EV_PERCENT:
            flags.append(f"EV below {self.MIN_EV_PERCENT:.1f}%.")
        if edge > self.MAX_EDGE_PERCENT:
            flags.append("Edge is unusually high and requires data validation.")

        if flags:
            return {
                "event": event,
                "risk_level": "HIGH",
                "stake_decision": "NO BET",
                "risk_flags": flags,
                "edge": edge,
                "ev": ev,
                "message": "Candidate failed the risk gate.",
            }

        return {
            "event": event,
            "risk_level": "MEDIUM",
            "stake_decision": "CFO REVIEW REQUIRED",
            "risk_flags": ["Position size must be set by the CFO agent."],
            "edge": edge,
            "ev": ev,
            "message": "Candidate passed initial risk gates.",
        }

    def run(self, analysis_data):
        print(f"{self.name} started.")

        if not isinstance(analysis_data, dict):
            return {
                "status": "error",
                "agent": self.name,
                "analysis_received": analysis_data,
                "risk_level": "BLOCKED",
                "stake_decision": "NO BET",
                "message": "Expected analyst output as a dictionary.",
                "results": [],
            }

        results = analysis_data.get("results")
        if results is None:
            results = [analysis_data]
        if not isinstance(results, list):
            results = []

        assessments = [self.assess(item) for item in results if isinstance(item, dict)]
        candidates = [
            assessment for assessment in assessments
            if assessment["stake_decision"] == "CFO REVIEW REQUIRED"
        ]
        if candidates:
            risk_level = "MEDIUM"
            stake_decision = "CFO REVIEW REQUIRED"
            message = "At least one candidate passed initial risk gates."
        elif assessments:
            risk_level = "BLOCKED"
            stake_decision = "NO BET"
            message = "No candidate passed risk gates."
        else:
            risk_level = "BLOCKED"
            stake_decision = "NO BET"
            message = "No analyst results were available for risk review."

        return {
            "status": "success",
            "agent": self.name,
            "analysis_received": analysis_data,
            "risk_level": risk_level,
            "stake_decision": stake_decision,
            "candidates_for_cfo": candidates,
            "results": assessments,
            "message": message,
        }


if __name__ == "__main__":
    sample = {
        "status": "READY",
        "event": "Test Event",
        "model_probability": 55.0,
        "market_probability": 50.0,
        "edge": 5.0,
        "ev": 3.0,
    }
    print(RiskManager().run({"results": [sample]}))
