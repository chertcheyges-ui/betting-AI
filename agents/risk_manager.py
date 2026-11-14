"""Risk controls for candidate bets produced by QuantitativeSportsAnalyst."""


class RiskManager:
    """Apply hard risk gates before a candidate reaches the CFO agent."""

    MIN_EDGE_PERCENT = 3.0
    MIN_EV_PERCENT = 2.0
    MAX_EDGE_PERCENT = 12.0
    MIN_DATASET_QUALITY = 85.0
    PROVISIONAL_MIN_DATASET_QUALITY = 70.0

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
        dataset_quality = self._number(analysis.get("dataset_quality"))

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
        provisional_flags = []
        if edge < self.MIN_EDGE_PERCENT:
            flags.append(f"Edge below {self.MIN_EDGE_PERCENT:.1f}%.")
        if ev < self.MIN_EV_PERCENT:
            flags.append(f"EV below {self.MIN_EV_PERCENT:.1f}%.")
        if edge > self.MAX_EDGE_PERCENT:
            flags.append("Преимущество над коэффициентом слишком велико: сначала нужна повторная проверка данных.")
        if dataset_quality is None or dataset_quality < self.PROVISIONAL_MIN_DATASET_QUALITY:
            flags.append("Недостаточно подтверждённых данных для виртуальной ставки.")
        elif dataset_quality < self.MIN_DATASET_QUALITY:
            provisional_flags.append("Данные неполные: виртуальная ставка будет уменьшена.")
        if not analysis.get("lineups_confirmed"):
            provisional_flags.append("Нет подтверждённых стартовых составов: виртуальная ставка будет уменьшена.")
        if model_probability is not None and model_probability > 75 and not analysis.get("lineups_confirmed"):
            flags.append("Высокая уверенность без составов считается ненадёжной.")

        if flags:
            return {
                "event": event,
                "risk_level": "HIGH",
                "stake_decision": "NO BET",
                "risk_flags": flags,
                "edge": edge,
                "ev": ev,
            "message": "Матч не прошёл строгую проверку риска.",
            }

        return {
            "event": event,
            "risk_level": "MEDIUM" if not provisional_flags else "MEDIUM WITH CONDITIONS",
            "stake_decision": "CFO REVIEW REQUIRED",
            "risk_flags": provisional_flags + ["Position size must be set by the CFO agent."],
            "edge": edge,
            "ev": ev,
            "message": "Матч прошёл активную проверку риска." if provisional_flags else "Матч прошёл первоначальную проверку риска.",
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

        assessments = []
        forecast_fields = (
            "status", "prediction", "selection", "odds", "model_probability",
            "market_probability", "edge", "ev", "market", "bookmaker",
            "dataset_quality", "lineups_confirmed", "confidence_cap",
        )
        for item in results:
            if not isinstance(item, dict):
                continue
            assessment = self.assess(item)
            # Preserve the model explanation for the dashboard and audit trail.
            for field in forecast_fields:
                if field in item:
                    assessment[field] = item[field]
            assessments.append(assessment)
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
