"""Final controls audit for the betting-analysis pipeline."""


class AuditorAgent:
    """Verify data completeness and that downstream agents respected safeguards."""

    def __init__(self):
        self.name = "Auditor Agent"

    @staticmethod
    def _as_dict(value):
        return value if isinstance(value, dict) else {}

    def run(self, system_data):
        print(f"{self.name} started.")

        # ==========================================================
        # INPUT VALIDATION
        # ==========================================================

        if not isinstance(system_data, dict):
            return {
                "status": "error",
                "agent": self.name,
                "audit_status": "FAIL",
                "errors_found": [
                    "System data must be a dictionary."
                ],
                "warnings": [],
                "recommendation": "HOLD",
                "message": "Audit could not start because system data is invalid.",
            }

        # ==========================================================
        # EXTRACT AGENT OUTPUTS
        # ==========================================================

        research = self._as_dict(
            system_data.get("research")
        )

        analysis = self._as_dict(
            system_data.get("analysis")
        )

        risk = self._as_dict(
            system_data.get("risk")
        )

        financial = self._as_dict(
            system_data.get("financial_review")
        )

        errors = []
        warnings = []

        # ==========================================================
        # RESEARCH CHECK
        # ==========================================================

        if research.get("status") != "success":
            errors.append(
                "Research Agent did not complete successfully."
            )

        elif research.get("fixtures_found", 0) == 0:
            warnings.append(
                "Research Agent returned no priority fixtures."
            )

        # ==========================================================
        # ANALYST CHECK
        # ==========================================================

        results = analysis.get("results", [])

        if not isinstance(results, list) or not results:
            warnings.append(
                "Analyst returned no candidate analyses."
            )

        else:
            # Find analyst results that are NOT ready.
            not_ready = [
                item
                for item in results
                if isinstance(item, dict)
                and item.get("status") != "READY"
            ]

            # ------------------------------------------------------
            # IMPORTANT:
            # If there are NOT READY candidates, Risk Manager
            # must block them.
            # ------------------------------------------------------

            if not_ready:
                warnings.append(
                    f"{len(not_ready)} analyst result(s) are not "
                    "ready for a betting decision."
                )

                if risk.get("stake_decision") != "NO BET":
                    errors.append(
                        "Risk Manager did not block an incomplete "
                        "analyst dataset."
                    )

        # ==========================================================
        # RISK MANAGER CHECK
        # ==========================================================

        risk_decision = risk.get("stake_decision")

        if risk_decision not in (
            "NO BET",
            "CFO REVIEW REQUIRED",
        ):
            errors.append(
                "Risk Manager returned an unknown stake decision."
            )

        candidates = risk.get(
            "candidates_for_cfo",
            []
        )

        if not isinstance(candidates, list):
            errors.append(
                "Risk Manager candidates_for_cfo must be a list."
            )
            candidates = []

        # ==========================================================
        # CFO CHECK
        # ==========================================================

        approved = financial.get(
            "approved_candidates",
            []
        )

        if not isinstance(approved, list):
            errors.append(
                "CFO approved_candidates must be a list."
            )
            approved = []

        financial_status = financial.get(
            "financial_status"
        )

        # CFO must never approve something Risk Manager rejected.
        if not candidates and approved:
            errors.append(
                "CFO approved a candidate that Risk Manager "
                "did not pass."
            )

        # If Risk Manager passed nothing, CFO should take no action.
        if (
            not candidates
            and financial_status not in (
                "NO ACTION",
                None,
            )
        ):
            errors.append(
                "CFO should take no action when there are no "
                "risk-approved candidates."
            )

        # If Risk Manager passed candidates but CFO blocked them
        # because configuration is missing, this is a warning,
        # not an audit failure.
        if (
            candidates
            and financial_status == "BLOCKED"
        ):
            warnings.append(
                "CFO blocked candidates because financial "
                "limits are unavailable."
            )

        # ==========================================================
        # CFO APPROVAL CONSISTENCY CHECK
        # ==========================================================

        risk_events = {
            candidate.get("event")
            for candidate in candidates
            if isinstance(candidate, dict)
        }

        approved_events = {
            candidate.get("event")
            for candidate in approved
            if isinstance(candidate, dict)
        }

        unauthorized_approvals = (
            approved_events - risk_events
        )

        if unauthorized_approvals:
            errors.append(
                "CFO contains approved candidates that are not "
                "present in Risk Manager candidates."
            )

        # ==========================================================
        # FINAL AUDIT DECISION
        # ==========================================================

        if errors:
            audit_status = "FAIL"
            recommendation = "HOLD"

        elif warnings:
            audit_status = "PASS WITH WARNINGS"
            recommendation = "HOLD"

        else:
            audit_status = "PASS"
            recommendation = (
                "READY FOR INVESTMENT COMMITTEE"
            )

        # ==========================================================
        # AUDIT OUTPUT
        # ==========================================================

        return {
            "status": "success",
            "agent": self.name,
            "system_data_received": system_data,
            "audit_status": audit_status,
            "errors_found": errors,
            "warnings": warnings,
            "recommendation": recommendation,
            "message": "Audit completed.",
        }


# ==============================================================
# DIRECT TEST
# ==============================================================

if __name__ == "__main__":

    sample = {
        "research": {
            "status": "success",
            "fixtures_found": 1,
        },

        "analysis": {
            "results": [
                {
                    "status": "NOT READY",
                }
            ],
        },

        "risk": {
            "stake_decision": "NO BET",
            "candidates_for_cfo": [],
        },

        "financial_review": {
            "financial_status": "NO ACTION",
            "approved_candidates": [],
        },
    }

    result = AuditorAgent().run(sample)

    print()
    print("=" * 60)
    print("AUDITOR TEST")
    print("=" * 60)

    for key, value in result.items():
        print(f"{key}: {value}")