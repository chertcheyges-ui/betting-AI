"""Paper-trading ledger and evidence-based post-match model review."""

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TRADES_PATH = ROOT / "data" / "paper_trades.json"
DASHBOARD_PATH = ROOT / "dashboard" / "site-static" / "paper-trading.json"
AUDIT_REPORT_PATH = ROOT / "dashboard" / "site-static" / "audit-report.json"
OUTCOMES = ("HOME_WIN", "DRAW", "AWAY_WIN")
STARTING_BANKROLL = 1000.0
# Half of each realised virtual profit is locked away.  It remains visible in
# the bank, but cannot be used for later paper bets during this experiment.
PROFIT_RESERVE_PERCENT = 50.0
MIN_MODEL_CONFIDENCE = 0.55
MIN_OUTCOME_GAP = 0.10
MIN_EDGE_PERCENT = 3.0
MIN_EV_PERCENT = 2.0
MAX_EDGE_PERCENT = 12.0
MIN_DATASET_QUALITY = 85.0
PROVISIONAL_MIN_DATASET_QUALITY = 70.0
PROVISIONAL_STAKE_MULTIPLIER = 0.50
DAILY_TEST_STAKE_FRACTION = 0.10
# This is a ceiling, not a daily target. The system opens only matches that
# have a real bookmaker price and pass the available-data checks.
MAX_ACTIVE_TESTS = 20
MAX_UNVERIFIED_CONFIDENCE = 0.75
LIMIT_REVIEW_MIN_MATCHES = 20
LIMIT_REVIEW_TARGET_MATCHES = 50


def _load(path, default):
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else default
    except (OSError, ValueError):
        return default


def _save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _probabilities(value):
    raw = value if isinstance(value, dict) else {}
    values = {name: float(raw.get(name, 0.0) or 0.0) for name in OUTCOMES}
    total = sum(values.values())
    if total <= 0:
        return None
    return {name: score / total for name, score in values.items()}


def _number_from_env(name, fallback):
    try:
        value = float(os.getenv(name, fallback))
        return value if value > 0 else fallback
    except (TypeError, ValueError):
        return fallback


def _bankroll_limits():
    bankroll = _number_from_env("BANKROLL", STARTING_BANKROLL)
    max_position = bankroll * _number_from_env("MAX_POSITION_PERCENT", 10.0) / 100
    daily_limit = bankroll * _number_from_env("DAILY_RISK_LIMIT_PERCENT", 30.0) / 100
    return bankroll, max_position, daily_limit


def _profit_reserve(trades):
    """Return the protected part of profits from settled paper bets."""
    profits = sum(
        max(0.0, float(item.get("virtual_pnl") or 0.0))
        for item in trades
        if item.get("status") == "SETTLED" and item.get("decision") == "PAPER BET"
    )
    return round(profits * PROFIT_RESERVE_PERCENT / 100, 2)


def _selection_gap(probabilities, selection):
    selected = probabilities.get(selection, 0.0)
    alternatives = [value for name, value in probabilities.items() if name != selection]
    return selected - max(alternatives, default=0.0)


def _lineups_confirmed(evidence):
    """Return True only for a non-empty, provider-confirmed lineup response."""
    lineups = (evidence or {}).get("lineups")
    return isinstance(lineups, list) and bool(lineups)


def _decision_for_forecast(forecast, probabilities, open_exposure, settled_pnl, profit_reserve, daily_test=False):
    """Apply clear, conservative rules before virtual money is used."""
    selection = forecast.get("prediction")
    confidence = probabilities.get(selection, 0.0)
    gap = _selection_gap(probabilities, selection)
    odds = forecast.get("odds")
    blockers = []
    watch_reasons = []
    if not isinstance(odds, (int, float)) or odds <= 1:
        blockers.append("Нет подходящего коэффициента для виртуальной проверки.")
    if confidence < MIN_MODEL_CONFIDENCE:
        watch_reasons.append("Уверенность ниже 55%, поэтому матч оставлен для наблюдения.")
    if gap < MIN_OUTCOME_GAP:
        watch_reasons.append("Шансы двух лучших исходов слишком близки, поэтому матч оставлен для наблюдения.")
    if float(forecast.get("edge") or 0) < MIN_EDGE_PERCENT:
        watch_reasons.append("Преимущество над коэффициентом слишком маленькое.")
    if float(forecast.get("ev") or 0) < MIN_EV_PERCENT:
        watch_reasons.append("Ожидаемая ценность прогноза недостаточна.")
    if float(forecast.get("edge") or 0) > MAX_EDGE_PERCENT:
        blockers.append("Преимущество над коэффициентом выглядит слишком большим: сначала нужна повторная проверка данных.")
    evidence = forecast.get("evidence") or {}
    quality = evidence.get("dataset_quality")
    if not isinstance(quality, (int, float)) or quality < PROVISIONAL_MIN_DATASET_QUALITY:
        blockers.append("Для этого матча собрано недостаточно подтверждённых данных.")
    lineups_confirmed = _lineups_confirmed(evidence)
    provisional = False
    provisional_reasons = []
    if not lineups_confirmed:
        provisional = True
        provisional_reasons.append("Составы ещё не подтверждены: виртуальная ставка уменьшена вдвое.")
    if isinstance(quality, (int, float)) and quality < MIN_DATASET_QUALITY:
        provisional = True
        provisional_reasons.append("Данные неполные: виртуальная ставка уменьшена вдвое.")
    if confidence > MAX_UNVERIFIED_CONFIDENCE and not lineups_confirmed:
        blockers.append("Очень высокая уверенность без подтверждённых составов считается ненадёжной.")
    if evidence.get("external_review_required"):
        provisional = True
        provisional_reasons.append("Есть свежая новость о составе или травме: виртуальная ставка уменьшена и будет перепроверена до начала матча.")
    if blockers:
        return False, 0.0, confidence, gap, blockers, "NO BET"
    if watch_reasons and not daily_test:
        return False, 0.0, confidence, gap, watch_reasons, "WATCH"

    bankroll, max_position, daily_limit = _bankroll_limits()
    available_daily = max(0.0, daily_limit - open_exposure)
    current_bankroll = bankroll + settled_pnl
    available_bankroll = max(0.0, current_bankroll - profit_reserve - open_exposure)
    # A previous loss never increases the next stake.  The amount depends
    # only on the current forecast and the fixed limits chosen by the user.
    strength = min(1.0, max(0.0, (confidence - MIN_MODEL_CONFIDENCE) / 0.40))
    stake = min(max_position, available_daily, available_bankroll, max_position * (0.15 + 0.85 * strength))
    if daily_test:
        stake = min(stake, max_position * DAILY_TEST_STAKE_FRACTION)
    if daily_test:
        return True, stake, confidence, gap, ["Ежедневный тест: строгая проверка не выбрала ставку, поэтому выбран лучший доступный матч с небольшой виртуальной суммой."] + watch_reasons + provisional_reasons, "BET"
    if provisional:
        stake *= PROVISIONAL_STAKE_MULTIPLIER
    stake = round(stake, 2)
    if stake <= 0:
        return False, 0.0, confidence, gap, ["Свободная часть виртуального банка уже использована или сохранена в резерве."], "WATCH"
    if provisional:
        return True, stake, confidence, gap, provisional_reasons + ["Прогноз прошёл активный режим проверки: преимущество и коэффициент выглядят достаточными."], "BET"
    return True, stake, confidence, gap, ["Прогноз прошёл строгую проверку: подтверждены составы, данные полные, а преимущество выглядит реалистично."], "BET"


def _recommendation(forecast, captured_at):
    return {
        "prediction": forecast.get("prediction"),
        "selection": forecast.get("selection"),
        "status": forecast.get("status"),
        "odds": forecast.get("odds"),
        "model_probability": forecast.get("model_probability"),
        "market_probability": forecast.get("market_probability"),
        "edge": forecast.get("edge"),
        "ev": forecast.get("ev"),
        "confidence_cap": forecast.get("confidence_cap"),
        "confidence_note": forecast.get("confidence_note"),
        "lineups_confirmed": forecast.get("lineups_confirmed"),
        "message": forecast.get("message"),
        "evidence": forecast.get("evidence") or {},
        "captured_at": captured_at,
    }


def _revision_changed(previous, current):
    """Do not create duplicate history entries during unchanged daily refreshes."""
    keys = ("prediction", "selection", "status", "odds", "model_probability",
            "market_probability", "edge", "ev", "confidence_cap", "confidence_note",
            "lineups_confirmed", "message", "evidence")
    return any(previous.get(key) != current.get(key) for key in keys)


def record_forecasts(snapshot):
    """Record ready model forecasts once, before fixtures are completed."""
    ledger = _load(TRADES_PATH, {"schema_version": 1, "trades": []})
    known = {str(item.get("fixture_id")): item for item in ledger["trades"]}
    open_exposure = sum(float(item.get("stake") or 0) for item in ledger["trades"] if item.get("status") == "OPEN")
    settled_pnl = sum(
        float(item.get("virtual_pnl") or 0.0)
        for item in ledger["trades"] if item.get("status") == "SETTLED"
    )
    profit_reserve = _profit_reserve(ledger["trades"])
    forecasts = (snapshot.get("analysis") or {}).get("forecasts", [])
    added = 0
    fallback_candidates = []
    for forecast in forecasts:
        if not isinstance(forecast, dict) or forecast.get("status") != "READY":
            continue
        fixture_id = forecast.get("fixture_id")
        prediction = forecast.get("prediction")
        probabilities = _probabilities(forecast.get("model_probabilities"))
        if fixture_id is None or prediction not in OUTCOMES or not probabilities:
            continue
        is_virtual_bet, stake, confidence, gap, decision_reasons, decision_level = _decision_for_forecast(
            forecast, probabilities, open_exposure, settled_pnl, profit_reserve
        )
        if decision_level == "WATCH":
            fallback_candidates.append((forecast, probabilities, confidence, fixture_id))
        odds = forecast.get("odds")
        existing = known.get(str(fixture_id))
        if existing is not None:
            # Upgrade records made by an earlier version of the experiment.
            existing["odds"] = forecast.get("odds", existing.get("odds"))
            existing["bookmaker"] = forecast.get("bookmaker", existing.get("bookmaker"))
            existing["edge"] = forecast.get("edge", existing.get("edge"))
            existing["ev"] = forecast.get("ev", existing.get("ev"))
            if not existing.get("decision") or (existing.get("status") == "OPEN" and existing.get("decision") != "PAPER BET"):
                existing["stake"] = stake
                existing["decision"] = "PAPER BET" if is_virtual_bet else decision_level
                existing["decision_level"] = decision_level
                existing["decision_reasons"] = decision_reasons
                existing["selection_gap"] = round(gap * 100, 2)
            current = _recommendation(forecast, snapshot.get("generated_at"))
            existing.setdefault("evidence_at_decision", current["evidence"])
            previous = existing.get("latest_recommendation")
            if not isinstance(previous, dict) or _revision_changed(previous, current):
                existing.setdefault("recommendation_history", []).append(current)
                existing["latest_recommendation"] = current
            continue
        current = _recommendation(forecast, snapshot.get("generated_at"))
        ledger["trades"].append({
            "fixture_id": fixture_id, "event": forecast.get("event"),
            "kickoff": forecast.get("kickoff"), "prediction": prediction,
            "probabilities": probabilities, "edge": forecast.get("edge"),
            "ev": forecast.get("ev"), "market_probability": forecast.get("market_probability"),
            "odds": odds, "stake": stake,
            "bookmaker": forecast.get("bookmaker"),
            "decision": "PAPER BET" if is_virtual_bet else decision_level,
            "decision_level": decision_level,
            "decision_reasons": decision_reasons,
            "selection_gap": round(gap * 100, 2),
            "created_at": snapshot.get("generated_at"), "status": "OPEN",
            "evidence_at_decision": current["evidence"],
            "latest_recommendation": current,
            "recommendation_history": [current],
        })
        known[str(fixture_id)] = ledger["trades"][-1]; added += 1
        if is_virtual_bet:
            open_exposure += stake

    # The practical test should not go quiet merely because every otherwise
    # valid match narrowly missed the strict threshold.  Keep several small,
    # independent virtual tests open when real odds exist, but never override
    # hard data blockers or the user's exposure limits.
    # A refresh can fail after a match was already analysed.  Its existing
    # WATCH record still contains the same captured evidence and real odds,
    # so it remains eligible for a small active test instead of disappearing.
    fallback_ids = {str(item[3]) for item in fallback_candidates}
    for item in ledger["trades"]:
        fixture_id = item.get("fixture_id")
        prediction = item.get("prediction")
        probabilities = item.get("probabilities")
        if (
            item.get("status") != "OPEN"
            or item.get("decision") != "WATCH"
            or str(fixture_id) in fallback_ids
            or prediction not in OUTCOMES
            or not isinstance(probabilities, dict)
        ):
            continue
        forecast = {
            "event": item.get("event"), "prediction": prediction,
            "odds": item.get("odds"), "edge": item.get("edge"),
            "ev": item.get("ev"), "evidence": item.get("evidence_at_decision") or {},
            "bookmaker": ((item.get("evidence_at_decision") or {}).get("odds") or {}).get("bookmaker"),
        }
        fallback_candidates.append((forecast, probabilities, probabilities.get(prediction, 0.0), fixture_id))

    active_tests = [
        item for item in ledger["trades"]
        if item.get("status") == "OPEN" and item.get("decision") == "PAPER BET"
    ]
    remaining_test_slots = max(0, MAX_ACTIVE_TESTS - len(active_tests))
    for forecast, probabilities, _, fixture_id in sorted(
        fallback_candidates, key=lambda item: item[2], reverse=True
    )[:remaining_test_slots]:
        forced, stake, confidence, gap, reasons, level = _decision_for_forecast(
            forecast, probabilities, open_exposure, settled_pnl, profit_reserve, daily_test=True
        )
        existing = known.get(str(fixture_id))
        if forced and existing is not None:
            existing["stake"] = stake
            existing["decision"] = "PAPER BET"
            existing["decision_level"] = level
            existing["decision_reasons"] = reasons
            existing["selection_gap"] = round(gap * 100, 2)
            if not existing.get("bookmaker"):
                existing["bookmaker"] = forecast.get("bookmaker")
            open_exposure += stake
    _save(TRADES_PATH, ledger)
    return added


def _outcome(match):
    home, away = match.get("goals_home"), match.get("goals_away")
    if not isinstance(home, int) or not isinstance(away, int):
        return None
    return "HOME_WIN" if home > away else "AWAY_WIN" if away > home else "DRAW"


def _postmortem(trade, actual):
    probabilities = trade["probabilities"]
    reasons = []
    confidence = probabilities.get(trade["prediction"], 0)
    if confidence < 0.55:
        reasons.append("Низкая уверенность модели: прогноз был слабее 55%.")
    if confidence > 0.75:
        reasons.append("Модель была слишком уверена в этом исходе. Будущие матчи с такой уверенностью без составов больше не получают виртуальную ставку.")
    evidence = trade.get("evidence_at_decision") or {}
    if not _lineups_confirmed(evidence):
        reasons.append("На момент выбора не было подтверждённых стартовых составов.")
    if float(trade.get("edge") or 0) > MAX_EDGE_PERCENT:
        reasons.append("Оценка преимущества над коэффициентом была слишком большой и требует дополнительной проверки.")
    if trade.get("market_probability") and confidence * 100 < float(trade["market_probability"]):
        reasons.append("Рынок оценивал выбранный исход выше модели; требуется сверка калибровки.")
    if not reasons:
        reasons.append("Неожиданный исход при доступных данных; нужно накопить больше матчей перед изменением модели.")
    return {"actual_outcome": actual, "was_correct": trade["prediction"] == actual, "model_confidence": round(confidence * 100, 2), "reasons": reasons, "requires_review": trade["prediction"] != actual}


def _operations(trades):
    """Build an automatic virtual-money journal from the saved decisions."""
    rows = [{
        "id": "start",
        "type": "income",
        "amount": STARTING_BANKROLL,
        "date": None,
        "title": "Стартовый виртуальный банк",
        "note": "Начало 7-дневной проверки.",
    }]
    for trade in trades:
        if trade.get("decision") != "PAPER BET":
            continue
        stake = float(trade.get("stake") or 0)
        if stake <= 0:
            continue
        event = trade.get("event") or "Матч"
        rows.append({
            "id": f"stake-{trade.get('fixture_id')}",
            "type": "expense",
            "amount": stake,
            "date": trade.get("created_at"),
            "title": "Виртуальная ставка",
            "note": f"{event} · сумма в игре до окончания матча.",
        })
        if trade.get("status") != "SETTLED":
            continue
        if trade.get("was_correct"):
            returned = round(stake + float(trade.get("virtual_pnl") or 0), 2)
            rows.append({
                "id": f"return-{trade.get('fixture_id')}",
                "type": "income",
                "amount": returned,
                "date": trade.get("settled_at"),
                "title": "Виртуальный результат",
                "note": f"{event} · прогноз сыграл.",
            })
        else:
            rows.append({
                "id": f"loss-{trade.get('fixture_id')}",
                "type": "loss",
                "amount": stake,
                "date": trade.get("settled_at"),
                "title": "Итог виртуальной ставки",
                "note": f"{event} · прогноз не сыграл, потеря: ${stake:.2f}. Сумма уже учтена в балансе.",
            })
    return sorted(rows, key=lambda row: row.get("date") or "", reverse=True)


def evaluate(history_path):
    """Reconcile finished fixtures and publish transparent evaluation metrics."""
    ledger = _load(TRADES_PATH, {"schema_version": 1, "trades": []})
    history = _load(Path(history_path), {"matches": []})
    completed = {str(match.get("fixture_id")): match for match in history.get("matches", []) if isinstance(match, dict)}
    for trade in ledger["trades"]:
        match = completed.get(str(trade.get("fixture_id")))
        actual = _outcome(match or {})
        if trade.get("status") == "OPEN" and actual:
            trade.update(_postmortem(trade, actual)); trade["status"] = "SETTLED"
            if match and match.get("score_source"):
                trade["score_source"] = match["score_source"]
            if trade.get("decision") == "PAPER BET":
                stake = float(trade.get("stake") or 0)
                odds = float(trade.get("odds") or 0)
                trade["virtual_pnl"] = round(
                    stake * (odds - 1) if trade["was_correct"] else -stake, 2
                )
            else:
                trade["virtual_pnl"] = 0.0
            trade["settled_at"] = datetime.now(timezone.utc).isoformat()

    settled = [trade for trade in ledger["trades"] if trade.get("status") == "SETTLED"]
    accuracy = sum(bool(item.get("was_correct")) for item in settled) / len(settled) if settled else None
    brier = None if not settled else sum(sum((item["probabilities"][name] - (name == item["actual_outcome"])) ** 2 for name in OUTCOMES) for item in settled) / len(settled)
    log_loss = None if not settled else sum(-math.log(max(item["probabilities"].get(item["actual_outcome"], 0), 1e-12)) for item in settled) / len(settled)
    _save(TRADES_PATH, ledger)
    open_trades = [item for item in ledger["trades"] if item.get("status") == "OPEN"]
    exposure = sum(float(item.get("stake") or 0) for item in open_trades)
    pnl = sum(float(item.get("virtual_pnl") or 0) for item in settled)
    profit_reserve = _profit_reserve(ledger["trades"])
    current_bankroll = STARTING_BANKROLL + pnl
    operations = _operations(ledger["trades"])
    latest_result = max(settled, key=lambda item: item.get("settled_at") or "", default=None)
    dashboard = {"schema_version": 1, "updated_at": datetime.now(timezone.utc).isoformat(), "experiment": "Paper trading only — no real bets.", "bankroll": round(current_bankroll, 2), "starting_bankroll": STARTING_BANKROLL, "open_exposure": round(exposure, 2), "profit_reserve_percent": PROFIT_RESERVE_PERCENT, "profit_reserve": profit_reserve, "available_bankroll": round(max(0.0, current_bankroll - profit_reserve - exposure), 2), "virtual_pnl": round(pnl, 2), "open_count": len(open_trades), "settled_count": len(settled), "accuracy": accuracy, "brier_score": brier, "log_loss": log_loss, "financial_policy": {"profit_reserve_percent": PROFIT_RESERVE_PERCENT, "increase_after_loss": False, "max_active_virtual_bets": MAX_ACTIVE_TESTS, "limit_review_min_matches": LIMIT_REVIEW_MIN_MATCHES, "limit_review_target_matches": LIMIT_REVIEW_TARGET_MATCHES}, "latest_result": latest_result, "trades": ledger["trades"], "operations": operations}
    _save(DASHBOARD_PATH, dashboard)
    from agents.auditor_agent import AuditorAgent
    _save(AUDIT_REPORT_PATH, AuditorAgent().review_prediction_quality(ledger["trades"]))
    return dashboard
