from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


class VixProvider(Provider):
    """
    VIX (S&P 500 Volatility Index) data source.

    优先：Yahoo Finance chart JSON（更接近实时 quote）
    备用：CNN Fear & Greed graphdata（经常只按交易日/收盘后更新）

    Yahoo Finance chart JSON:
    - https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX

    CNN Graph JSON (used by the page):
    - https://production.dataviz.cnn.io/index/fearandgreed/graphdata

    Page:
    - https://edition.cnn.com/markets/fear-and-greed
    """

    GRAPH_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    PAGE_URL = "https://edition.cnn.com/markets/fear-and-greed"
    YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.VIX not in set(indicator_ids):
            return []

        # Prefer Yahoo (more real-time). Fallback to CNN (may be delayed).
        parsed = self._fetch_yahoo_vix_value()
        if not parsed:
            parsed = self._fetch_vix_value()
        if not parsed:
            return []
        vix_value, as_of, rating, ts_ms = parsed

        return [
            Observation(
                indicator_id=IndicatorId.VIX,
                as_of=as_of,
                value=vix_value,
                unit="index",
                source="Yahoo Finance" if ts_ms == -1 else "CNN:dataviz",
                meta={
                    "url": self.YAHOO_URL if ts_ms == -1 else self.GRAPH_URL,
                    "page": self.PAGE_URL,
                    "component": "market_volatility_vix" if ts_ms != -1 else "chart_%5EVIX",
                    "rating": rating,
                    "timestamp_ms": None if ts_ms == -1 else ts_ms,
                },
            )
        ]

    def _fetch_yahoo_vix_value(self) -> tuple[float, datetime.date, str, float] | None:
        """
        Parse VIX from Yahoo Finance chart endpoint.

        - meta.regularMarketPrice: latest quote
        - meta.regularMarketTime: epoch seconds
        """
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
        }
        try:
            resp = self.session.get(self.YAHOO_URL, headers=headers, timeout=(3, 8))
            if resp.status_code >= 400:
                return None
            data = resp.json()
            chart = data.get("chart") if isinstance(data, dict) else None
            result = (chart or {}).get("result") if isinstance(chart, dict) else None
            if not isinstance(result, list) or not result:
                return None
            meta = result[0].get("meta") if isinstance(result[0], dict) else None
            if not isinstance(meta, dict) or not meta:
                return None

            vix = float(meta.get("regularMarketPrice"))
            if not (5 <= vix <= 100):
                return None

            ts = meta.get("regularMarketTime")
            as_of = datetime.now(timezone.utc).date()
            if ts:
                try:
                    # 用美东日期更符合“交易日”直觉（避免 UTC 跨日造成日期看起来滞后/超前）
                    as_of = datetime.fromtimestamp(float(ts), tz=ZoneInfo("America/New_York")).date()
                except Exception:
                    pass

            # Yahoo 不提供 CNN 的 rating，这里留空
            rating = ""
            # 用 ts_ms=-1 标识来源为 Yahoo（避免与 CNN 的 timestamp_ms 混淆）
            return (vix, as_of, rating, -1)
        except Exception:
            return None

    def _fetch_graphdata(self) -> dict[str, Any] | None:
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Referer": self.PAGE_URL,
            "Origin": "https://edition.cnn.com",
            "Connection": "keep-alive",
            "DNT": "1",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }
        try:
            resp = self.session.get(self.GRAPH_URL, headers=headers, timeout=(5, 20))
            if resp.status_code == 418:
                # Bot protection
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Warning: Failed to fetch VIX graphdata from CNN: {e}")

        return None

    def _fetch_vix_value(self) -> tuple[float, datetime.date, str, float] | None:
        """Parse the latest VIX value from CNN graphdata market_volatility_vix component."""
        try:
            data = self._fetch_graphdata()
            if not isinstance(data, dict) or not data:
                return None

            # This matches the \"market volatility\" indicator on the page.
            comp = data.get("market_volatility_vix")
            if not isinstance(comp, dict) or not comp:
                return None

            series = comp.get("data")
            if not isinstance(series, list) or not series:
                return None

            last = series[-1]
            if not isinstance(last, dict):
                return None

            if "y" not in last:
                return None

            vix = float(last["y"])
            if not (5 <= vix <= 100):
                return None

            ts_ms = float(last.get("x") or comp.get("timestamp") or 0.0)
            # Dashboard 里“Last Updated”已经按 UTC+8 展示；这里也用 UTC+8 把日期对齐用户直觉，
            # 避免 UTC 跨日导致看起来“还停留在昨天”。
            as_of = datetime.now(timezone(timedelta(hours=8))).date()
            if ts_ms:
                try:
                    as_of = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone(timedelta(hours=8))).date()
                except Exception:
                    pass

            rating = str(comp.get("rating") or "")
            return (vix, as_of, rating, ts_ms)
        except Exception as e:
            print(f"Warning: Failed to parse VIX from CNN graphdata: {e}")
            return None
