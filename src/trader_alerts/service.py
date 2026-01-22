from __future__ import annotations

from pathlib import Path

from .constants import ALL_INDICATORS, IndicatorId
from .models import Alert
from .rules import RULES, RuleContext
from .storage import latest_observation, recent_observations


def compute_alerts(
    db_path: str | Path,
    indicators: list[IndicatorId] | None = None,
) -> list[Alert]:
    targets = indicators or list(ALL_INDICATORS)
    out: list[Alert] = []

    for ind in targets:
        latest = latest_observation(db_path, ind)
        h30 = recent_observations(db_path, ind, 35)
        h365 = recent_observations(db_path, ind, 370)
        rule = RULES.get(ind)
        if not latest or not rule:
            continue
        alert = rule(RuleContext(latest=latest, history_30d=h30, history_365d=h365))
        if alert:
            out.append(alert)

    return out


