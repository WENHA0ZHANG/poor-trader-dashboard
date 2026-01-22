from __future__ import annotations

import re
from datetime import date

import requests

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


class StreetStatsProvider(Provider):
    """
    StreetStats: S&P 500 Relative Strength Index（RSI）

    页面：
    - https://streetstats.finance/markets/breadth-momentum/SP500
    """

    URL = "https://streetstats.finance/markets/breadth-momentum/SP500"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.SP500_RSI not in set(indicator_ids):
            return []
        obs = self._fetch_sp500_rsi()
        return [obs] if obs else []

    def _fetch_sp500_rsi(self) -> Observation | None:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        # 页面用于仪表盘展示，超时要短一些，避免阻塞刷新
        resp = self.session.get(self.URL, headers=headers, timeout=(5, 12))
        resp.raise_for_status()
        html = resp.text

        # 1) 尝试基于文本提示提取（最直观）
        # 例："... Relative Strength Index ... 56.78 ..."
        m = re.search(
            r"Relative\s+Strength\s+Index[^0-9]{0,80}([0-9]{1,3}(?:\.[0-9]+)?)",
            html,
            re.IGNORECASE,
        )
        if not m:
            # 2) 兜底：尝试常见 JSON 字段名
            m = re.search(r'"rsi"\s*:\s*([0-9]{1,3}(?:\.[0-9]+)?)', html, re.IGNORECASE)
        if not m:
            # 3) 再兜底：rsiXX / RSI(14)=XX 之类格式
            m = re.search(r"\bRSI\b[^0-9]{0,20}([0-9]{1,3}(?:\.[0-9]+)?)", html, re.IGNORECASE)
        if not m:
            return None

        v = float(m.group(1))
        if v < 0 or v > 1000:
            return None

        return Observation(
            indicator_id=IndicatorId.SP500_RSI,
            as_of=date.today(),
            value=v,
            unit="0-100",
            source="StreetStats",
            meta={"url": self.URL},
        )


