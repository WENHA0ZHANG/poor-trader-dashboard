from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import requests
import yaml

from ..constants import ALL_INDICATORS, IndicatorId
from ..models import Observation
from .base import Provider


def _dig(obj: Any, path: str) -> Any:
    """
    简单的 dot-path 取值：a.b.0.c
    """
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


class HttpJsonProvider(Provider):
    """
    通用 HTTP JSON Provider：让你把“实时 API”接进来，而不用改业务逻辑/规则引擎。

    配置文件示例（YAML）：

    indicators:
      us_high_yield_spread:
        url: "https://example.com/hy"
        method: "GET"
        headers:
          Authorization: "Bearer xxx"
        params:
          symbol: "HY_OAS"
        value_path: "data.value"
        as_of_path: "data.date"   # 可选，ISO 日期
        unit: "bp"
        source: "my_api"
    """

    def __init__(self, config_file: str | Path, session: requests.Session | None = None):
        self.config_file = Path(config_file)
        self.session = session or requests.Session()
        self.config = yaml.safe_load(self.config_file.read_text(encoding="utf-8")) or {}

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        wanted = set(indicator_ids) if indicator_ids else set(ALL_INDICATORS)
        cfg = self.config.get("indicators") or {}

        out: list[Observation] = []
        for ind in wanted:
            item = cfg.get(ind.value)
            if not item:
                continue
            out.append(self._fetch_one(ind, item))
        return out

    def _fetch_one(self, indicator_id: IndicatorId, item: dict[str, Any]) -> Observation:
        url = item["url"]
        method = str(item.get("method") or "GET").upper()
        headers = item.get("headers") or {}
        params = item.get("params") or {}
        timeout = float(item.get("timeout") or 20)

        resp = self.session.request(method, url, headers=headers, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        value = float(_dig(data, item["value_path"]))
        unit = str(item.get("unit") or "")
        source = str(item.get("source") or "http_json")

        as_of_path = item.get("as_of_path")
        if as_of_path:
            as_of_raw = _dig(data, as_of_path)
            as_of = date.fromisoformat(str(as_of_raw))
        else:
            as_of = date.today()

        meta = {"url": url, "value_path": item.get("value_path"), "as_of_path": as_of_path}
        return Observation(
            indicator_id=indicator_id,
            as_of=as_of,
            value=value,
            unit=unit or "%",
            source=source,
            meta=meta,
        )


