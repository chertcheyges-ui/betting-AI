"""Final controls audit for the betting-analysis pipeline."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


class AuditorAgent:
    """Verify data completeness and that downstream agents respected safeguards."""

    def __init__(self):
        self.name = "Auditor Agent"

    @staticmethod
    def _as_dict(value):
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _unresolved_scores():
        """List paper bets overdue for a result so the audit cannot miss them."""
        path = Path(__file__).resolve().parents[1] / "data" / "paper_trades.json"
        try:
            trades = json.loads(path.read_text(encoding="utf-8")).get("trades", [])
        except (OSError, ValueError, AttributeError):
            return []
        now = datetime.now(timezone.utc)
        overdue = []
        for trade in trades:
            if not isinstance(trade, dict) or trade.get("status") != "OPEN":
                continue
            try:
                kickoff = datetime.fromisoformat(str(trade.get("kickoff")).replace("Z", "+00:00"))
                if kickoff.tzinfo is None:
                    kickoff = kickoff.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
            if now >= kickoff.astimezone(timezone.utc) + timedelta(minutes=110):
                overdue.append({"fixture_id": trade.get("fixture_id"), "event": trade.get("event")})
        return overdue

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

        data = self._as_dict(
            system_data.get("data")
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
        unresolved_scores = self._unresolved_scores()
        if unresolved_scores:
            warnings.append(
                f"Аудит не видит итог у {len(unresolved_scores)} завершённого матча: запущен поиск по резервным источникам."
            )

        # ==========================================================
        # DASHBOARD FRESHNESS CHECK
        # ==========================================================
        # The dashboard must not silently show a previous day's fixtures.
        # This check is deliberately independent from the research pipeline:
        # it verifies the exact snapshot published for the web page.
        dashboard_report = self._as_dict(system_data.get("dashboard_report"))
        today = datetime.now(ZoneInfo("Europe/Minsk")).date().isoformat()
        dashboard_check = {
            "expected_date": today,
            "report_date": dashboard_report.get("requested_date"),
            "matches": len(dashboard_report.get("matches", [])) if isinstance(dashboard_report.get("matches"), list) else 0,
            "current": False,
        }
        if not dashboard_report:
            errors.append("На сайте нет отчёта по сегодняшним матчам.")
        elif dashboard_report.get("requested_date") != today:
            errors.append(
                "На сайте показан не сегодняшний отчёт по матчам. Нужно обновить данные."
            )
        elif not isinstance(dashboard_report.get("matches"), list) or not dashboard_report["matches"]:
            errors.append("В сегодняшнем отчёте сайта нет матчей.")
        elif dashboard_report.get("collection_status") == "error":
            errors.append("Сегодняшний отчёт сайта не удалось получить из источников.")
        else:
            dashboard_check["current"] = True
            if dashboard_report.get("collection_status") == "degraded":
                warnings.append("Сегодняшний отчёт сайта неполный: часть данных нужно перепроверить.")

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
        # DATA COLLECTION CHECK
        # ==========================================================

        if data.get("api_rate_limited"):
            warnings.append(
                "API-Football rate limit prevented complete data collection."
            )
        elif data and data.get("status") != "success":
            errors.append("Data Manager did not complete successfully.")

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

                risk_results = risk.get("results")
                if isinstance(risk_results, list):
                    blocked_events = {
                        assessment.get("event", "Unknown event")
                        for assessment in risk_results
                        if isinstance(assessment, dict)
                        and assessment.get("stake_decision") == "NO BET"
                    }
                    incomplete_events = {
                        item.get("event", "Unknown event")
                        for item in not_ready
                    }
                    incomplete_data_blocked = incomplete_events.issubset(
                        blocked_events
                    )
                else:
                    # Backward-compatible fallback for older Risk Manager
                    # payloads that do not include per-event assessments.
                    incomplete_data_blocked = (
                        risk.get("stake_decision") == "NO BET"
                    )

                if not incomplete_data_blocked:
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

        if financial.get("status") not in ("success", None):
            errors.append("CFO Agent did not complete successfully.")

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

        if candidates and financial_status == "REVIEW COMPLETE" and not approved:
            errors.append(
                "CFO completed review without setting a position limit."
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
            # A candidate that passed Risk Manager and received a CFO
            # position limit remains safe to send to the committee. Warnings
            # about other, blocked candidates must not veto that position.
            if (
                candidates
                and approved
                and financial_status == "REVIEW COMPLETE"
                and not data.get("api_rate_limited")
            ):
                recommendation = "READY FOR INVESTMENT COMMITTEE"
            else:
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
            "dashboard_check": dashboard_check,
            "unresolved_scores": unresolved_scores,
            "recommendation": recommendation,
            "message": "Audit completed.",
        }

    def review_prediction_quality(self, trades):
        """Explain prediction quality in plain language after matches finish."""
        settled = [item for item in trades if isinstance(item, dict) and item.get("status") == "SETTLED"]
        correct = [item for item in settled if item.get("was_correct") is True]
        incorrect = [item for item in settled if item.get("was_correct") is False]
        improvements = []
        applied_changes = [
            {
                "title": "Слабые прогнозы отмечаются как риск",
                "text": "При уверенности ниже 55% обычная виртуальная ставка не делается. В активном тесте возможна небольшая виртуальная ставка с пометкой о риске.",
            },
            {
                "title": "Почти равные варианты отмечаются как риск",
                "text": "Если преимущество прогноза меньше 10 процентных пунктов, обычная виртуальная ставка не делается. В активном тесте возможна небольшая виртуальная ставка.",
            },
            {
                "title": "Неподтверждённые составы снижают сумму",
                "text": "В активном тесте матч без подтверждённых составов может получить только уменьшенную виртуальную ставку. Такая ставка отмечается как повышенный риск.",
            },
            {
                "title": "Тест не остаётся без ставки",
                "text": "Если строгая проверка не нашла обычную ставку, но есть подходящие матчи для наблюдения, система может выбрать несколько лучших вариантов с небольшой виртуальной суммой.",
            },
            {
                "title": "Слишком высокая уверенность проверяется заново",
                "text": "Если программа показывает более 75% без составов или слишком большое преимущество над коэффициентом, деньги не ставятся.",
            },
        ]
        league_results = {}
        team_results = {}
        decision_results = {}
        patterns = {
            "low_confidence": 0,
            "overconfident": 0,
            "close_calls": 0,
            "missing_lineups": 0,
            "missing_injuries": 0,
        }
        for trade in settled:
            decision = str(trade.get("decision") or "UNKNOWN")
            decision_results.setdefault(decision, []).append(bool(trade.get("was_correct")))
            evidence = trade.get("evidence_at_decision") or {}
            league = evidence.get("league") or "Лига не указана"
            league_results.setdefault(league, []).append(bool(trade.get("was_correct")))
            for team in (evidence.get("home"), evidence.get("away")):
                if team:
                    team_results.setdefault(team, []).append(bool(trade.get("was_correct")))
            if float(trade.get("model_confidence") or 0) < 45:
                patterns["low_confidence"] += 1
            if float(trade.get("model_confidence") or 0) > 75:
                patterns["overconfident"] += 1
            probabilities = trade.get("probabilities") or {}
            selected = float(probabilities.get(trade.get("prediction"), 0) or 0)
            other = [float(value or 0) for name, value in probabilities.items() if name != trade.get("prediction")]
            gap = float(trade.get("selection_gap")) if trade.get("selection_gap") is not None else (selected - max(other, default=0.0)) * 100
            if gap < 5:
                patterns["close_calls"] += 1
            missing = evidence.get("missing_data") or []
            patterns["missing_lineups"] += int("lineups" in missing)
            patterns["missing_injuries"] += int("injuries" in missing)

        if len(settled) < 20:
            improvements.append({
                "title": "Пока рано делать выводы",
                "text": "Нужно хотя бы 20 завершённых матчей. Сейчас каждый отдельный матч слишком сильно влияет на результат.",
            })
        if incorrect:
            improvements.append({
                "title": "Не ставить при слабом преимуществе",
                "text": "Слабые и близкие прогнозы не подходят для обычной виртуальной ставки. В активном тесте небольшая ставка возможна, но её риск нужно показывать явно.",
            })
        if patterns["overconfident"]:
            improvements.append({
                "title": "Снижаем чрезмерную уверенность",
                "text": "В прошлых матчах были слишком смелые прогнозы. Без подтверждённых составов их уверенность нужно считать предварительной и перепроверять перед матчем.",
            })
        if not improvements:
            improvements.append({
                "title": "Продолжаем проверку",
                "text": "Серьёзных повторяющихся проблем пока не видно. Нужна более длинная серия завершённых матчей.",
            })

        if patterns["missing_lineups"]:
            applied_changes.append({
                "title": "Неподтверждённые составы отмечаются как риск",
                "text": "Для следующих матчей без составов система снижает доверие к прогнозу и не считает данные полными.",
            })
            improvements.append({
                "title": "Проверять составы ближе к матчу",
                "text": "В некоторых прошлых прогнозах не было составов. Это отмечается как риск и влияет на итоговую уверенность.",
            })

        # These are concrete controls that the rest of the system already
        # understands.  The auditor uses every finished forecast here, even a
        # no-money observation, but avoids changing model weights on a tiny
        # sample (that would merely overfit the latest losses).
        learning_actions = []
        if patterns["low_confidence"] or patterns["close_calls"]:
            learning_actions.append({
                "title": "Слабые и близкие прогнозы отмечены",
                "text": "Аудитор учитывает эти ошибки в общей статистике. Для следующих матчей они остаются только в активном тесте с небольшой суммой, а не становятся обычной ставкой.",
            })
        if patterns["missing_lineups"] or patterns["missing_injuries"]:
            learning_actions.append({
                "title": "Неполные составы отмечены",
                "text": "Следующий прогноз без составов или данных о травмах получает пониженную уверенность и требует повторной проверки до начала матча.",
            })
        if len(settled) < 20:
            learning_actions.append({
                "title": "Перенастройка модели ещё не включена",
                "text": "Нужно не менее 20 завершённых прогнозов. До этого аудитор исправляет явные причины ошибок, но не переобучает модель на слишком маленькой выборке.",
            })

        mistakes = []
        for trade in incorrect:
            probabilities = trade.get("probabilities") or {}
            predicted = float(probabilities.get(trade.get("prediction"), 0) or 0) * 100
            ordered = sorted((float(value or 0) * 100 for value in probabilities.values()), reverse=True)
            gap = round(ordered[0] - ordered[1], 1) if len(ordered) > 1 else None
            evidence = trade.get("evidence_at_decision") or {}
            missing = evidence.get("missing_data") or []
            reasons = list(trade.get("reasons") or [])
            if "lineups" in missing:
                reasons.append("Не было подтверждённых составов.")
            if "injuries" in missing:
                reasons.append("Не хватало данных о травмах.")
            if float(trade.get("selection_gap") or 100) < 5:
                reasons.append("Варианты были слишком близкими.")
            mistakes.append({
                "event": trade.get("event") or "Матч",
                "prediction": trade.get("prediction"),
                "actual_outcome": trade.get("actual_outcome"),
                "odds": trade.get("odds"),
                "confidence": round(predicted, 1),
                "gap": gap,
                "reasons": reasons or ["Матч закончился иначе, чем ожидала модель."],
            })

        results = []
        for trade in sorted(settled, key=lambda item: item.get("settled_at") or "", reverse=True):
            probabilities = trade.get("probabilities") or {}
            prediction = trade.get("prediction")
            results.append({
                "event": trade.get("event") or "Матч",
                "prediction": prediction,
                "actual_outcome": trade.get("actual_outcome"),
                "odds": trade.get("odds"),
                "confidence": round(float(probabilities.get(prediction, 0) or 0) * 100, 1),
                "was_correct": bool(trade.get("was_correct")),
            })

        accuracy = round(len(correct) / len(settled) * 100, 1) if settled else None
        def rating(items):
            return [
                {"name": name, "tested": len(results), "accuracy": round(sum(results) / len(results) * 100, 1) if results else None,
                 "status": "Данных пока мало" if len(results) < 3 else "Можно сравнивать"}
                for name, results in sorted(items.items(), key=lambda item: (-len(item[1]), item[0]))
            ]
        decision_labels = {
            "PAPER BET": "Виртуальная ставка",
            "WATCH": "Наблюдение без денег",
            "NO BET": "Не ставим",
        }
        by_decision = [
            {
                "decision": decision,
                "label": decision_labels.get(decision, decision),
                "tested": len(values),
                "correct": sum(values),
                "accuracy": round(sum(values) / len(values) * 100, 1) if values else None,
            }
            for decision, values in sorted(decision_results.items())
        ]
        summary = (
            "Пока нет завершённых матчей для проверки прогнозов."
            if not settled else
            f"Проверено матчей: {len(settled)}. Совпало: {len(correct)}, не совпало: {len(incorrect)}."
        )
        generated_at = datetime.now(timezone.utc).isoformat()
        return {
            "schema_version": 1,
            "generated_at": generated_at,
            "updated_at": generated_at,
            "agent": self.name,
            "summary": summary,
            "tested": len(settled),
            "correct": len(correct),
            "incorrect": len(incorrect),
            "accuracy": accuracy,
            "mistakes": mistakes,
            "results": results,
            "applied_changes": applied_changes,
            "improvements": improvements,
            "learning_actions": learning_actions,
            "by_decision": by_decision,
            "patterns": patterns,
            "reliability": {"leagues": rating(league_results), "teams": rating(team_results)},
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
