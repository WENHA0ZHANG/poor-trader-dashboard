from __future__ import annotations

from datetime import date
from typing import Any

import requests

from ..constants import IndicatorId
from ..models import Observation
from ..settings import Settings
from .base import Provider
from .tradingeconomics import TradingEconomicsProvider


class FredProvider(Provider):
    """
    FRED 数据源（优先用 FRED API；若没有 FRED_API_KEY，则回退到公开的 FRED 数据文件）。

    内置映射（可扩展）：
    - US High Yield Spread：FRED series_id = BAMLH0A0HYM2（ICE BofA US High Yield OAS）
    """

    BASE = "https://api.stlouisfed.org/fred"
    PUBLIC_TXT_BASE = "https://fred.stlouisfed.org/data"
    PUBLIC_GRAPH_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"

    def __init__(self, settings: Settings | None = None, session: requests.Session | None = None):
        self.settings = settings or Settings()
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        out: list[Observation] = []
        for ind in indicator_ids:
            if ind == IndicatorId.US_HIGH_YIELD_SPREAD:
                out.append(self._fetch_hy_oas())
        return out

    def _fetch_hy_oas(self) -> Observation:
        """
        注意：FRED 的 BAMLH0A0HYM2 单位是 Percent。
        本项目为了和“bp 阈值”一致，会把 percent 转成 bp（x100）。
        """
        series_id = "BAMLH0A0HYM2"

        # 你的网络环境对 stlouisfed 域名经常超时：优先用 TradingEconomics 抓取（页面可访问）
        try:
            te_obs = TradingEconomicsProvider(session=self.session).fetch([IndicatorId.US_HIGH_YIELD_SPREAD])[0]
            pct = float(te_obs.value)  # percent
            return Observation(
                indicator_id=IndicatorId.US_HIGH_YIELD_SPREAD,
                as_of=te_obs.as_of,
                value=pct * 100.0,
                unit="bp",
                source="TradingEconomics",
                meta={"url": te_obs.meta.get("url") if te_obs.meta else None, "raw_percent": pct},
            )
        except Exception:
            # 若失败再尝试 FRED（可能超时）
            pass

        api_key = self.settings.fred_api_key
        if api_key:
            # 取最新一期非空值
            params = {
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 10,
            }
            resp = self.session.get(f"{self.BASE}/series/observations", params=params, timeout=20)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            obs_list = data.get("observations") or []
            for row in obs_list:
                v = row.get("value")
                if v is None or v == ".":
                    continue
                as_of = date.fromisoformat(row["date"])
                pct = float(v)
                return Observation(
                    indicator_id=IndicatorId.US_HIGH_YIELD_SPREAD,
                    as_of=as_of,
                    value=pct * 100.0,
                    unit="bp",
                    source=f"FRED_API:{series_id}",
                    meta={"fred_series_id": series_id, "raw_percent": pct},
                )

        # 无 key：回退到公开数据文件（无鉴权）
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/plain,text/csv,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

        text: str | None = None
        # 先尝试 /data/*.txt（最接近你提到的 “View All”）
        try:
            resp = self.session.get(
                f"{self.PUBLIC_TXT_BASE}/{series_id}.txt",
                headers=headers,
                timeout=(10, 60),
            )
            resp.raise_for_status()
            # 有时会返回 HTML（例如反爬/跳转页），需要识别
            if "text/html" not in (resp.headers.get("content-type") or "").lower():
                text = resp.text
        except Exception:
            text = None

        # 再尝试 fredgraph.csv（通常体积更小/更稳定）
        if not text:
            resp = self.session.get(
                self.PUBLIC_GRAPH_CSV,
                params={"id": series_id},
                headers=headers,
                timeout=(10, 60),
            )
            resp.raise_for_status()
            text = resp.text

        # 格式类似：
        # DATE VALUE
        # 2025-12-24 2.84
        latest_date: date | None = None
        latest_value_pct: float | None = None
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line or line.startswith("DATE"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            d, v = parts[0], parts[1]
            if v == ".":
                continue
            try:
                latest_date = date.fromisoformat(d)
                latest_value_pct = float(v)
                break
            except Exception:
                continue

        if latest_date is None or latest_value_pct is None:
            raise RuntimeError(f"无法从 FRED 数据文件解析 {series_id}")

        return Observation(
            indicator_id=IndicatorId.US_HIGH_YIELD_SPREAD,
            as_of=latest_date,
            value=latest_value_pct * 100.0,
            unit="bp",
            source=f"FRED_TXT:{series_id}",
            meta={"fred_series_id": series_id, "raw_percent": latest_value_pct},
        )


