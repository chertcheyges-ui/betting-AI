"""Financial controls for candidates cleared by RiskManager."""

import os

from dotenv import load_dotenv


load_dotenv()


class CFOAgent:
    """Enforce user-configured bankroll and exposure limits."""

    def __init__(self):
        self.name = "CFO & Accounting Manager"
        self.bankroll = self._positive_number(os.getenv("BANKROLL"))
        self.max_position_percent = self._positive_number(
            os.getenv("MAX_POSITION_PERCENT")
        )
        self.daily_risk_limit_percent = self._positive_number(
            os.getenv("DAILY_RISK_LIMIT_PERCENT")
        )

    @staticmethod
    def _positive_number(value):
        try:
            result = float(value)
            return result if result > 0 else None
        except (TypeError, ValueError):
            return None

    def _configuration_missing(self):
        return [
            name
            for name, value in (
                ("BANKROLL", self.bankroll),
                ("MAX_POSITION_PERCENT", self.max_position_percent),
                ("DAILY_RISK_LIMIT_PERCENT", self.daily_risk_limit_percent),
            )
            if value is None
        ]

    def run(self, risk_data, current_exposure=0.0):
        print(f"{self.name} started.")

        if not isinstance(risk_data, dict):
            return {
                "status": "error",
                "agent": self.name,
                "risk_data_received": risk_data,
                "bank_status": "BLOCKED",
                "financial_status": "BLOCKED",
                "message": "Expected Risk Manager output as a dictionary.",
                "approved_candidates": [],
            }

        candidates = risk_data.get("candidates_for_cfo", [])
        if not candidates:
            return {
                "status": "success",
                "agent": self.name,
                "risk_data_received": risk_data,
                "bank_status": "NO ACTION",
                "financial_status": "NO ACTION",
                "approved_candidates": [],
                "message": "No candidates passed Risk Manager review.",
            }

        missing_config = self._configuration_missing()
        if missing_config:
            return {
                "status": "success",
                "agent": self.name,
                "risk_data_received": risk_data,
                "bank_status": "NOT CONFIGURED",
                "financial_status": "BLOCKED",
                "missing_configuration": missing_config,
                "approved_candidates": [],
                "message": "Financial limits must be configured before approval.",
            }

        exposure = self._positive_number(current_exposure) or 0.0
        daily_limit = self.bankroll * self.daily_risk_limit_percent / 100
        available_daily_risk = max(0.0, daily_limit - exposure)
        max_position = self.bankroll * self.max_position_percent / 100

        if available_daily_risk <= 0:
            return {
                "status": "success",
                "agent": self.name,
                "risk_data_received": risk_data,
                "bank_status": "DAILY LIMIT REACHED",
                "financial_status": "BLOCKED",
                "approved_candidates": [],
                "message": "No daily risk budget remains.",
            }

        approved = []
        remaining_risk = available_daily_risk
        for candidate in candidates:
            if remaining_risk <= 0:
                break
            limit = round(min(max_position, remaining_risk), 2)
            approved.append({
                "event": candidate.get("event", "Unknown event"),
                "financial_decision": "POSITION LIMIT SET",
                "maximum_position": limit,
                "currency": "bankroll currency",
                "reason": "Limit calculated from user-configured risk parameters.",
            })
            remaining_risk -= limit

        return {
            "status": "success",
            "agent": self.name,
            "risk_data_received": risk_data,
            "bank_status": "WITHIN LIMITS",
            "financial_status": "REVIEW COMPLETE",
            "bankroll": self.bankroll,
            "daily_risk_limit": round(daily_limit, 2),
            "current_exposure": exposure,
            "remaining_daily_risk": round(remaining_risk, 2),
            "approved_candidates": approved,
            "message": "Position limits are ceilings, not automatic bets.",
        }


if __name__ == "__main__":
    print(CFOAgent().run({"candidates_for_cfo": []}))
