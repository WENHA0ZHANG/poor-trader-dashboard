from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import requests

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


class YChartsProvider(Provider):
    """
    YCharts：US Investor Sentiment, % Bull-Bear Spread

    页面：
    - https://ycharts.com/indicators/us_investor_sentiment_bull_bear_spread

    说明：
    - 这是 AAII 情绪指标（Bull% - Bear%），不是 BofA Bull & Bear（0-10）。
    - 用户要求“用它替换美银牛熊指标”，所以写入到 IndicatorId.BOFA_BULL_BEAR 这个槽位。
    """

    URL = "https://ycharts.com/indicators/us_investor_sentiment_bull_bear_spread"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.BOFA_BULL_BEAR not in set(indicator_ids):
            return []
        return [self._fetch_aaii_spread()]

    def _fetch_aaii_spread(self) -> Observation:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = self.session.get(self.URL, headers=headers, timeout=25)
        resp.raise_for_status()
        html = resp.text

        # 页面通常会包含类似： "10.94% for Wk of Dec 18 2025"
        m = re.search(
            r"([+-]?\d+(?:\.\d+)?)%\s*for\s*Wk\s*of\s*([A-Za-z]{3,9}\s+\d{1,2}\s+\d{4})",
            html,
            re.IGNORECASE,
        )
        if not m:
            # 备用：尝试从 “Last Value” 表格附近抽取一个百分比
            m = re.search(r"Last Value\s*</[^>]+>\s*<[^>]+>\s*([+-]?\d+(?:\.\d+)?)%", html, re.IGNORECASE)
        if not m:
            raise RuntimeError("无法从 ycharts 页面解析 AAII Bull-Bear Spread（可能需要登录或页面结构变化）")

        value = float(m.group(1))
        as_of = date.today()
        period = None
        if m.lastindex and m.lastindex >= 2:
            try:
                as_of = datetime.strptime(m.group(2), "%b %d %Y").date()
                period = m.group(2)
            except Exception:
                period = m.group(2)

        return Observation(
            indicator_id=IndicatorId.BOFA_BULL_BEAR,
            as_of=as_of,
            value=value,
            unit="%",
            source="YCharts:AAII",
            meta={"url": self.URL, "definition": "AAII Bull% - Bear%", "period": period},
        )


