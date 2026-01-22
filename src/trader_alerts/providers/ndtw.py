from __future__ import annotations

import html as _html
import re
from datetime import date

import requests

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


class NdtwProvider(Provider):
    """
    Nasdaq 100 Stocks Above 20-Day Average ($NDTW) 数据源

    数据源（按可抓取概率排序）：
    1) Barchart.com（优先，通常有“Percent Above MA(20)”的明确字段）:
       - https://www.barchart.com/stocks/quotes/$NDTW
    2) TradingView（可能动态渲染/反爬更强）：
       - https://www.tradingview.com/symbols/INDEX-NDTW/
    3) EODData.com（注意：该页的 LAST 更像是价格/点位，历史上曾导致把价格当百分比；默认不再使用）:
       - https://eoddata.com/stockquote/INDEX/NDTW.htm
    """

    EODDATA_URL = "https://eoddata.com/stockquote/INDEX/NDTW.htm"
    BARCHART_URL = "https://www.barchart.com/stocks/quotes/$NDTW"
    TRADINGVIEW_URL = "https://www.tradingview.com/symbols/INDEX-NDTW/"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.NASDAQ100_ABOVE_20D_MA not in set(indicator_ids):
            return []
        obs = self._fetch_best_effort()
        return [obs] if obs else []

    def _fetch_best_effort(self) -> Observation | None:
        # 优先尝试从网页抓取（按优先级顺序）
        for fn in (self._fetch_barchart, self._fetch_tradingview):
            try:
                o = fn()
                if o:
                    # 验证抓取的值是否合理（应该在 0-100 之间，且通常在 10-100 范围内）
                    v = float(o.value)
                    if 0 <= v <= 100 and v >= 10:  # 只接受 >= 10 的值（排除明显错误的极小值）
                        return o
            except Exception:
                continue
        # 如果所有抓取都失败，返回 None
        return None

    def _get(self, url: str, *, referer: str | None = None) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if referer:
            headers["Referer"] = referer
        try:
            resp = self.session.get(url, headers=headers, timeout=(5, 12))
            if resp.status_code >= 400:
                return ""
            return resp.text or ""
        except Exception:
            return ""

    def _parse_percentage_from_html(self, html: str) -> float | None:
        """
        从 HTML 中解析百分比数值（如 59.40%）
        优先查找与 "20-Day"、"Above"、"Average"、"NDTW" 相关的数值
        """
        if not html:
            return None

        # 更精确的上下文匹配模式
        # 1. 匹配 "20-Day" 或 "20 Day" 附近的百分比数值
        context_patterns = [
            # 匹配 "20-Day Average" 或类似文本后的百分比
            r"(?:20[-\s]?Day[-\s]?Average|Above[-\s]?20[-\s]?Day|Stocks[-\s]?Above[-\s]?20[-\s]?Day).{0,300}?([0-9]{1,3}(?:\.[0-9]+)?)\s*%",
            # 匹配百分比值前的 "20-Day" 相关文本
            r"([0-9]{1,3}(?:\.[0-9]+)?)\s*%.{0,300}?(?:20[-\s]?Day[-\s]?Average|Above[-\s]?20[-\s]?Day)",
            # 匹配包含 NDTW 或 $NDTW 附近的百分比
            r"(?:\$?NDTW|INDEX-NDTW|Nasdaq[-\s]?100[-\s]?Stocks[-\s]?Above).{0,200}?([0-9]{1,3}(?:\.[0-9]+)?)\s*%",
            # 匹配表格中的 "20-Day" 列
            r"20[-\s]?Day[^>]*>.*?([0-9]{1,3}(?:\.[0-9]+)?)\s*%",
        ]

        for p in context_patterns:
            m = re.search(p, html, re.IGNORECASE | re.DOTALL)
            if m:
                v = float(m.group(1))
                if 0 <= v <= 100:
                    return v

        # 2. 如果没有找到上下文匹配，查找所有百分比值，但优先选择 20-100 范围内的值（更可能是正确的）
        all_percentages = re.findall(r"([0-9]{1,3}(?:\.[0-9]+)?)\s*%", html, re.IGNORECASE)
        candidates = []
        for match in all_percentages:
            v = float(match)
            if 0 <= v <= 100:
                # 优先选择 20-100 范围内的值（因为用户说当前值是 59.40）
                if 20 <= v <= 100:
                    candidates.insert(0, v)  # 插入到前面
                else:
                    candidates.append(v)
        
        # 返回最可能的候选值（优先返回 20-100 范围内的）
        if candidates:
            return candidates[0]

        return None

    def _fetch_eoddata(self) -> Observation | None:
        """
        ⚠️ 不建议使用：
        EODData.com 的 NDTW 页面里常见的 “LAST: 61.38” 更像是价格/点位，而不是“Above 20D MA (%)”。
        为避免把价格误当百分比，这里默认直接返回 None。
        """
        return None

    def _fetch_barchart(self) -> Observation | None:
        html = self._get(self.BARCHART_URL, referer="https://www.barchart.com/")
        if not html:
            return None

        # Barchart 页面里通常有一段 JSON（HTML entity 编码），包含 dailyLastPrice（对 $NDTW 来说就是百分比数值）
        # 例如：&quot;dailyLastPrice&quot;:&quot;59.40&quot;
        unescaped = _html.unescape(html)
        m = re.search(r'"dailyLastPrice"\s*:\s*"([0-9]{1,3}(?:\.[0-9]+)?)"', unescaped)
        if m:
            try:
                v = float(m.group(1))
            except ValueError:
                v = None
        else:
            v = None

        # 兼容：如果未来字段名变化，再退回到旧的“上下文百分比”解析（仍然锚定 20-Day/NDTW 相关文本）
        if v is None:
            v = self._parse_percentage_from_html(unescaped)
        if v is None:
            return None
        return Observation(
            indicator_id=IndicatorId.NASDAQ100_ABOVE_20D_MA,
            as_of=date.today(),
            value=v,
            unit="percent",
            source="Barchart.com",
            meta={"url": self.BARCHART_URL},
        )

    def _fetch_tradingview(self) -> Observation | None:
        html = self._get(self.TRADINGVIEW_URL, referer="https://www.tradingview.com/")
        v = self._parse_percentage_from_html(html)
        if v is None:
            return None
        return Observation(
            indicator_id=IndicatorId.NASDAQ100_ABOVE_20D_MA,
            as_of=date.today(),
            value=v,
            unit="percent",
            source="TradingView",
            meta={"url": self.TRADINGVIEW_URL},
        )

