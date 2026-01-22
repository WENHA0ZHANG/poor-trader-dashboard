from __future__ import annotations

import re
from datetime import date

import requests

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


class Sp500RsiProvider(Provider):
    """
    S&P 500 RSI 数据源（按“可解析到 RSI(14) Value”的顺序尝试）：

    1) Investing.com（目标：抓取 Name/Value/Action 表格中 RSI(14) 的 Value）：
       - https://www.investing.com/indices/us-spx-500-technical

    2) Investtech（有时仅有文字描述，不一定能拿到“RSI 数值”；作为兜底）：
       - https://www.investtech.com/main/market.php?CompanyID=10400521&product=211

    3) TradingView（通常动态渲染/反爬更强）：
       - https://www.tradingview.com/symbols/SPX/technicals/
    """

    INVESTTECH_URL = "https://www.investtech.com/main/market.php?CompanyID=10400521&product=211"
    INVESTING_URL = "https://www.investing.com/indices/us-spx-500-technical"
    TRADINGVIEW_URL = "https://www.tradingview.com/symbols/SPX/technicals/"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.SP500_RSI not in set(indicator_ids):
            return []
        obs = self._fetch_best_effort()
        return [obs] if obs else []

    def _fetch_best_effort(self) -> Observation | None:
        for fn in (self._fetch_investing, self._fetch_investtech, self._fetch_tradingview):
            try:
                o = fn()
                if o:
                    return o
            except Exception:
                continue
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
        resp = self.session.get(url, headers=headers, timeout=(5, 12))
        if resp.status_code >= 400:
            return ""
        return resp.text or ""

    def _parse_rsi_from_html(self, html: str) -> float | None:
        if not html:
            return None

        # 常见形式（不同站点可能会出现的 RSI(14) / Relative Strength Index (14) / RSI - Relative Strength Index）
        patterns = [
            r"Relative\s+Strength\s+Index\s*\(14\)[^0-9]{0,80}([0-9]{1,3}(?:\.[0-9]+)?)",
            r"RSI\s*\(14\)[^0-9]{0,80}([0-9]{1,3}(?:\.[0-9]+)?)",
            r"RSI\s*-\s*Relative\s+Strength\s+Index[^0-9]{0,120}([0-9]{1,3}(?:\.[0-9]+)?)",
            r"\bRSI\b[^0-9]{0,40}([0-9]{1,3}(?:\.[0-9]+)?)",
        ]
        for p in patterns:
            m = re.search(p, html, re.IGNORECASE)
            if m:
                v = float(m.group(1))
                if 0 <= v <= 100:
                    return v
        return None

    def _parse_investing_rsi14_value(self, html: str) -> float | None:
        """
        解析 Investing.com 技术面 “Name / Value / Action” 表格里的 RSI(14) → Value。

        目标形态（示例）：
        Name        Value     Action
        RSI(14)     69.858    Buy
        """
        if not html:
            return None

        # 优先：严格匹配整行，避免误抓 RSI(14) 附近其它数字
        # 典型结构（表格行）：
        # <td>RSI(14)</td><td>69.858</td><td>Buy</td>
        m = re.search(
            r"RSI\s*\(\s*14\s*\)\s*"
            r"</td>\s*"
            r"<td[^>]*>\s*"
            r"([0-9]{1,3}(?:\.[0-9]+)?)\s*"
            r"</td>\s*"
            r"<td[^>]*>\s*"
            r"(Buy|Sell|Neutral)\s*"
            r"</td>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            v = float(m.group(1))
            if 0 <= v <= 100:
                return v

        # 兜底：有些情况下 td 里会包一层 span/div
        m = re.search(
            r"RSI\s*\(\s*14\s*\)\s*"
            r"</td>\s*"
            r"<td[^>]*>.*?"
            r"([0-9]{1,3}(?:\.[0-9]+)?)"
            r".*?</td>\s*"
            r"<td[^>]*>.*?"
            r"(Buy|Sell|Neutral)"
            r".*?</td>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            v = float(m.group(1))
            if 0 <= v <= 100:
                return v

        # 再兜底：如果页面把表格数据塞在脚本 JSON 里（key/value/action）
        m = re.search(
            r"RSI\s*\(\s*14\s*\).*?"
            r"(?:\"value\"|value|data-value)\s*[:=]\s*\"?([0-9]{1,3}(?:\.[0-9]+)?)\"?.*?"
            r"(?:\"action\"|action)\s*[:=]\s*\"?(Buy|Sell|Neutral)\"?",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            v = float(m.group(1))
            if 0 <= v <= 100:
                return v

        # 兜底：抓取 RSI(14) 后 0~200 字符内出现的第一个数值
        m = re.search(r"RSI\s*\(\s*14\s*\)(.{0,200})", html, re.IGNORECASE | re.DOTALL)
        if m:
            mm = re.search(r"([0-9]{1,3}(?:\.[0-9]+)?)", m.group(1))
            if mm:
                v = float(mm.group(1))
                if 0 <= v <= 100:
                    return v

        return None

    def _fetch_investtech(self) -> Observation | None:
        html = self._get(self.INVESTTECH_URL, referer="https://www.investtech.com/")
        v = self._parse_rsi_from_html(html)
        if v is None:
            return None
        return Observation(
            indicator_id=IndicatorId.SP500_RSI,
            as_of=date.today(),
            value=v,
            unit="0-100",
            source="Investtech",
            meta={"url": self.INVESTTECH_URL},
        )

    def _fetch_investing(self) -> Observation | None:
        html = self._get(self.INVESTING_URL, referer="https://www.investing.com/")
        # 你要的是 “RSI(14) ... Buy” 这一行里的 Value（例如 69.858）
        v = self._parse_investing_rsi14_value(html)
        if v is None:
            # 如果表格结构变了，再做一次通用 RSI 兜底
            v = self._parse_rsi_from_html(html)
        if v is None:
            return None
        return Observation(
            indicator_id=IndicatorId.SP500_RSI,
            as_of=date.today(),
            value=v,
            unit="0-100",
            source="Investing.com",
            meta={"url": self.INVESTING_URL},
        )

    def _fetch_tradingview(self) -> Observation | None:
        html = self._get(self.TRADINGVIEW_URL, referer="https://www.tradingview.com/")
        v = self._parse_rsi_from_html(html)
        if v is None:
            return None
        return Observation(
            indicator_id=IndicatorId.SP500_RSI,
            as_of=date.today(),
            value=v,
            unit="0-100",
            source="TradingView",
            meta={"url": self.TRADINGVIEW_URL},
        )


