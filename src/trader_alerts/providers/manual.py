from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ..constants import ALL_INDICATORS, IndicatorId
from ..models import Observation
from .base import Provider


def _as_date(v: Any) -> date:
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        return date.fromisoformat(v)
    raise ValueError(f"无法解析日期: {v!r}（期望 ISO 格式，如 2025-03-18）")


class ManualProvider(Provider):
    """
    从 YAML 文件读取专有指标（你从研报/数据源抄出来的数值）。

    支持两种格式：

    1) 顶层 dict（推荐）：
       bofa_fms_cash_level:
         value: 4.8
         unit: "%"
         as_of: "2025-03-18"
         source: "BofA FMS"

    2) 顶层 list：
       - indicator_id: bofa_fms_cash_level
         value: 4.8
         unit: "%"
         as_of: "2025-03-18"
         source: "BofA FMS"
    """

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        raw = yaml.safe_load(self.file_path.read_text(encoding="utf-8"))
        if raw is None:
            return []

        wanted = set(indicator_ids) if indicator_ids else set(ALL_INDICATORS)
        out: list[Observation] = []

        if isinstance(raw, dict):
            for key, payload in raw.items():
                ind = IndicatorId(key)
                if ind not in wanted:
                    continue
                if not isinstance(payload, dict):
                    raise ValueError(f"{key} 的值必须是 dict")
                out.append(self._parse_one(ind, payload))
            return out

        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    raise ValueError("list 格式的每个元素必须是 dict")
                ind = IndicatorId(item["indicator_id"])
                if ind not in wanted:
                    continue
                out.append(self._parse_one(ind, item))
            return out

        raise ValueError("manual_input.yaml 只能是 dict 或 list")

    def _parse_one(self, indicator_id: IndicatorId, payload: dict[str, Any]) -> Observation:
        value = float(payload["value"])
        unit = str(payload.get("unit") or "")
        if not unit:
            unit = "%"
        as_of = _as_date(payload.get("as_of") or date.today().isoformat())
        source = str(payload.get("source") or "manual")
        meta = payload.get("meta") or {}
        if meta is not None and not isinstance(meta, dict):
            raise ValueError(f"{indicator_id.value}.meta 必须是 dict")

        return Observation(
            indicator_id=indicator_id,
            as_of=as_of,
            value=value,
            unit=unit,
            source=source,
            meta=meta,
        )


