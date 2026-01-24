from __future__ import annotations

import re
from datetime import date, datetime

import requests

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


class TradingEconomicsProvider(Provider):
    """
    TradingEconomics：ICE BofA US High Yield Index Option-Adjusted Spread

    页面（用户指定）：
    - https://tradingeconomics.com/united-states/bofa-merrill-lynch-us-high-yield-option-adjusted-spread-fed-data.html

    说明：
    - 该页面声称数据来自 FRED，但对你当前网络环境而言它更可访问（FRED 域名会超时）。
    - 页面数值单位通常是 Percent；本项目会在上层转成 bp。
    """

    URL = (
        "https://tradingeconomics.com/united-states/"
        "bofa-merrill-lynch-us-high-yield-option-adjusted-spread-fed-data.html"
    )

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.US_HIGH_YIELD_SPREAD not in set(indicator_ids):
            return []
        return [self._fetch_hy_oas_percent()]

    def _fetch_hy_oas_percent(self) -> Observation:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = self.session.get(self.URL, headers=headers, timeout=(10, 35))
        resp.raise_for_status()
        html = resp.text

        # 优先从 metaDesc（description）中提取当前值（最稳定）
        # 示例：
        # <meta id="metaDesc" name="description" content="... Spread was 2.83% in December of 2025 ...">
        meta_desc = None
        mm = re.search(r'<meta[^>]+id="metaDesc"[^>]+content="([^"]+)"', html, re.IGNORECASE)
        if mm:
            meta_desc = mm.group(1)

        value: float | None = None
        if meta_desc:
            m = re.search(r"\bwas\s*([0-9]+(?:\.[0-9]+)?)\s*%", meta_desc, re.IGNORECASE)
            if not m:
                m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", meta_desc)
            if m:
                value = float(m.group(1))

        # 兜底：从正文里找一个 “x.xx%” 值（尽量避开 100% 等布局相关数值）
        if value is None:
            candidates = [float(x) for x in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*%", html)]
            # 经验：OAS% 通常 < 30；100% 之类大概率是无关值
            candidates = [x for x in candidates if x < 30]
            if candidates:
                value = candidates[0]

        if value is None:
            raise RuntimeError("无法从 TradingEconomics 页面解析当前 OAS 数值（%）")

        # 尝试从页面里的 TELastUpdate=YYYYMMDD... 推导日期
        # 页面里可能有多个 TELastUpdate，取最新的一条
        as_of = date.today()
        update_dates: list[date] = []
        for ymd in re.findall(r"TELastUpdate\s*=\s*'(\d{8})\d{0,6}'", html):
            try:
                update_dates.append(datetime.strptime(ymd, "%Y%m%d").date())
            except Exception:
                continue
        if not update_dates:
            for ymd in re.findall(r"\bLastUpdate\s*=\s*'(\d{8})\d{0,6}'", html):
                try:
                    update_dates.append(datetime.strptime(ymd, "%Y%m%d").date())
                except Exception:
                    continue
        if update_dates:
            as_of = max(update_dates)

        return Observation(
            indicator_id=IndicatorId.US_HIGH_YIELD_SPREAD,
            as_of=as_of,
            value=value,
            unit="percent",
            source="TradingEconomics",
            meta={"url": self.URL, "raw_unit": "%"},
        )


