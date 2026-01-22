from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import requests

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


class Nasdaq100BreadthProvider(Provider):
    """
    Nasdaq 100 Stocks Above 20-Day Average (%)

    数据源：
    - TradingView: https://www.tradingview.com/symbols/INDEX-NDTW/
    - Barchart: https://www.barchart.com/stocks/quotes/$NDTW

    说明：
    - 显示纳斯达克100指数成分股中，股价高于20日移动平均线的股票百分比
    - 低于20%通常表示市场疲弱，底部信号
    - 高于80%通常表示市场过热，顶部信号
    """

    TRADINGVIEW_URL = "https://www.tradingview.com/api/v1/some_endpoint"  # TradingView通常需要API
    BARCHART_URL = "https://www.barchart.com/stocks/quotes/$NDTW"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.NASDAQ100_ABOVE_20D_AVERAGE not in set(indicator_ids):
            return []
        return [self._fetch_breadth()]

    def _fetch_breadth(self) -> Observation:
        # 优先尝试Barchart，因为TradingView可能需要特殊API
        try:
            return self._fetch_from_barchart()
        except Exception:
            # 如果Barchart失败，可以尝试TradingView（但可能不可用）
            raise

    def _fetch_from_barchart(self) -> Observation:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        resp = self.session.get(self.BARCHART_URL, headers=headers, timeout=25)
        resp.raise_for_status()
        html = resp.text

        # 从Barchart页面查找当前值
        # 页面通常包含类似 "Last Price" 或其他格式
        # 由于这是百分比指标，我们需要查找具体的数值

        # 尝试多种模式匹配
        patterns = [
            r'Last Price[^>]*>([\d.]+)',  # 标准格式
            r'currentLast[^>]*>([\d.]+)',  # 另一种格式
            r'price[^>]*>([\d.]+)',  # 简化格式
        ]

        value = None
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    break
                except ValueError:
                    continue

        if value is None:
            raise ValueError("无法从Barchart页面解析Nasdaq 100 Breadth值")

        # 获取当前日期作为数据日期
        as_of = date.today()

        return Observation(
            indicator_id=IndicatorId.NASDAQ100_ABOVE_20D_AVERAGE,
            value=value,
            unit="%",  # 百分比
            as_of=as_of,
            source=self.BARCHART_URL,
        )
