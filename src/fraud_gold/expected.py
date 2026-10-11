"""Local reference for Gold: expected alerts and cases from the PaySim CSV, no Spark (spec §5-6, §12)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations  # modern type hints on 3.11

from collections import Counter     # payments per hour
from typing import Any, Iterable, Mapping, Sequence  # type hints

from fraud_model.windows import ALERT_BUDGET_DEFAULT, LABEL_DELAY_DAYS_DEFAULT, SCORE_FROM_STEP_DEFAULT  # shared rules
from fraud_silver.expected import BronzeScenario  # Bronze state description

# ── Constants ─────────────────────────────────────────────────
STEPS_PER_DAY = 24  # one step is one simulated hour
CLOSE_DELAY_STEPS = STEPS_PER_DAY * LABEL_DELAY_DAYS_DEFAULT  # 72: verdicts arrive 3 simulated days after the alert
GOLD_SCENARIO = BronzeScenario(  # Bronze as of 2026-10-11: replay done, drift 409-418 released (413 late, all arrived)
    last_step=418, held_steps=frozenset(), duplicate_steps=frozenset({340}),  # step 340 delivered twice
    malformed_step=350, malformed_rows=5,  # five broken amounts at step 350
)  # end GOLD_SCENARIO


# ── Counts ────────────────────────────────────────────────────
def silver_payments_per_step(judged: Iterable[tuple[str, dict[str, Any]]],  # (verdict, record) pairs from judge()
                             first_step: int = SCORE_FROM_STEP_DEFAULT) -> Counter[int]:  # first scored hour
    """Clean (Silver) payments per hour from `first_step` on: exactly the rows the score task scores."""  # docstring
    return Counter(r["step"] for verdict, r in judged if verdict == "ok" and r["step"] >= first_step)  # ok rows only


def alerts_per_step(payments: Mapping[int, int], budget: int = ALERT_BUDGET_DEFAULT) -> dict[int, int]:  # hour -> alerts
    """min(budget, payments) for every hour that has payments, in hour order."""  # docstring
    if budget < 1:  # a zero or negative budget alerts nothing
        raise ValueError(f"budget must be at least 1, got {budget}")  # refuse
    return {step: min(budget, n) for step, n in sorted(payments.items()) if n > 0}  # capped per hour


def closing_cutoff(newest_scored_step: int, delay_steps: int = CLOSE_DELAY_STEPS) -> int:  # last hour whose cases close
    return newest_scored_step - delay_steps  # the data's own clock, so reruns agree


def closed_cases(alerts: Mapping[int, int], cutoff: int) -> int:  # cases closed at this cutoff
    return sum(n for step, n in alerts.items() if step <= cutoff)  # every alert in a closed hour


# ── Late-alert rule (mirrors gold.sql) ────────────────────────
def is_late_alert(issued_scores: Sequence[float], late_score: float,  # an alerted hour, and a payment that arrived later
                  budget: int = ALERT_BUDGET_DEFAULT) -> bool:  # the hourly budget
    """True when a late payment earns an extra alert: the hour had room, or it beats the hour's lowest alert."""  # docstring
    if not issued_scores:  # the hour was never alerted
        raise ValueError("this hour has no alerts yet: rank it as a new hour, not as late")  # wrong rule
    return len(issued_scores) < budget or late_score > min(issued_scores)  # room left, or strictly better


def late_alerts_earned(issued_scores: Sequence[float], late_scores: Sequence[float],  # an alerted hour, and payments that arrived later together
                       budget: int = ALERT_BUDGET_DEFAULT) -> int:  # the hourly budget
    """How many of a batch of late payments earn an alert: the best fill the room left, the rest only if they beat the lowest alert."""  # docstring
    if not issued_scores:  # the hour was never alerted
        raise ValueError("this hour has no alerts yet: rank it as a new hour, not as late")  # wrong rule
    room = max(budget - len(issued_scores), 0)  # places still free in the hour
    bar = min(issued_scores)  # the lowest alert already issued
    ranked = sorted(late_scores, reverse=True)  # best late payment first, like late_rank in gold.sql
    return sum(1 for rank, score in enumerate(ranked, start=1) if rank <= room or score > bar)  # room first, then the bar
