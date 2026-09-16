"""Final decision gate for reviewed betting candidates."""


class InvestmentCommittee:
    """Make APPROVE, REJECT, or HOLD decisions from all control reports."""

    def __init__(self):
        self.name = "Investment Committee"

    @staticmethod
    def _as_dict(value):
        return value if isinstance(value, dict) else {}

    def run(self, committee_package):
        print(f"{self.name} started.")
        if not isinstance(committee_package, dict):
            return {
                "status": "error",
                "agent": self.name,
                "decision": "REJECT",
                "reason": "Expected the reviewed committee package.",
                "approved_candidates": [],
            }

        risk = self._as_dict(committee_package.get("risk"))
        financial = self._as_dict(committee_package.get("financial_review"))
        audit = self._as_dict(committee_package.get("audit"))
        audit_status = audit.get("audit_status")

        if audit_status == "FAIL":
            decision = "REJECT"
            reason = "Audit found control failures."
        elif audit.get("recommendation") != "READY FOR INVESTMENT COMMITTEE":
            decision = "HOLD"
            reason = "Audit has not cleared the candidate for committee review."
        elif risk.get("stake_decision") != "CFO REVIEW REQUIRED":
            decision = "HOLD"
            reason = "Risk Manager has not cleared a candidate."
        elif financial.get("financial_status") != "REVIEW COMPLETE":
            decision = "HOLD"
            reason = "CFO financial review is incomplete or blocked."
        elif not financial.get("approved_candidates"):
            decision = "HOLD"
            reason = "CFO did not provide an approved position limit."
        else:
            decision = "APPROVE"
            reason = (
                "All control gates passed. Approval is for manual review and "
                "does not place a bet automatically."
            )

        return {
            "status": "success",
            "agent": self.name,
            "risk_data_received": committee_package,
            "decision": decision,
            "reason": reason,
            "approved_candidates": (
                financial.get("approved_candidates", []) if decision == "APPROVE" else []
            ),
            "message": "Investment Committee decision completed.",
        }


if __name__ == "__main__":
    package = {
        "risk": {"stake_decision": "NO BET"},
        "financial_review": {"financial_status": "NO ACTION"},
        "audit": {"audit_status": "PASS WITH WARNINGS", "recommendation": "HOLD"},
    }
    print(InvestmentCommittee().run(package))
