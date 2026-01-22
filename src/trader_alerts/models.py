from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from .constants import IndicatorId


@dataclass(frozen=True)
class Observation:
    indicator_id: IndicatorId
    as_of: date
    value: float
    unit: str
    source: str
    meta: dict[str, Any] | None = None


class AlertLevel(str, Enum):
    BULL = "牛市预警"
    BEAR = "熊市预警"
    NEUTRAL = "中性"


@dataclass(frozen=True)
class Alert:
    indicator_id: IndicatorId
    level: AlertLevel
    title: str
    message: str
    evidence: dict[str, Any] | None = None


