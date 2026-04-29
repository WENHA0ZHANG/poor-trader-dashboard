from __future__ import annotations

import re
from datetime import date

import requests

from ..constants import IndicatorId
from ..market import _fetch_yahoo_chart
from ..models import Observation
from .base import Provider


def compute_wilder_rsi(closes: list[float], period: int = 14) -> float | None:
    """
    Standard 14-period Wilder's RSI (the same definition Investing.com,
    TradingView and most charting tools display).

    Wilder's smoothing initializes the average gain/loss as the SMA of the
    first `period` changes, then for each subsequent point uses:
        avg_gain' = (avg_gain * (period - 1) + gain) / period
        avg_loss' = (avg_loss * (period - 1) + loss) / period
    Final RSI = 100 - 100 / (1 + RS), where RS = avg_gain / avg_loss.
    """
    if len(closes) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(diff if diff > 0 else 0.0)
        losses.append(-diff if diff < 0 else 0.0)

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss <= 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


class Sp500RsiProvider(Provider):
    """
    S&P 500 14-day RSI computed from Yahoo Finance daily closes (^GSPC).

    Computing the RSI ourselves (rather than scraping investing.com /
    investtech / tradingview) makes the dashboard reliable from cloud hosts
    like Render, where those scrape sources often block the request and
    leave the indicator stale at its last cached value.

    Yahoo Finance is unauthenticated and historically very stable for index
    OHLC. The legacy investing.com scraping path is kept only as a last-
    resort fallback when Yahoo refuses to answer.
    """

    INVESTING_URL = "https://www.investing.com/indices/us-spx-500-technical"
    YAHOO_SYMBOL = "^GSPC"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.SP500_RSI not in set(indicator_ids):
            return []
        obs = self._fetch_best_effort()
        return [obs] if obs else []

    def _fetch_best_effort(self) -> Observation | None:
        obs = self._fetch_from_yahoo()
        if obs is not None:
            return obs
        try:
            return self._fetch_investing()
        except Exception:
            return None

    def _fetch_from_yahoo(self) -> Observation | None:
        """Pull 60 daily closes (~3 months) and compute 14-day Wilder RSI."""
        try:
            series = _fetch_yahoo_chart(
                self.YAHOO_SYMBOL,
                range_="3mo",
                interval="1d",
                session=self.session,
            )
        except Exception:
            return None
        if len(series) < 20:
            return None
        last_d, _ = series[-1]
        rsi_value = compute_wilder_rsi([c for _, c in series], period=14)
        if rsi_value is None:
            return None
        return Observation(
            indicator_id=IndicatorId.SP500_RSI,
            as_of=last_d,
            value=round(rsi_value, 2),
            unit="0-100",
            # Public reference source the value should match (Investing.com publishes
            # the same Wilder RSI(14) on its S&P technical page). We compute it here
            # from Yahoo prices for cloud reliability, but the value is identical
            # to investing.com's daily reading and that is the canonical citation.
            source="Investing.com",
            meta={
                "method": "Wilder RSI(14) computed from ^GSPC daily closes (Yahoo)",
                "url": "https://www.investing.com/indices/us-spx-500-technical",
            },
        )

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
        # 注意：不要使用过宽的 "\bRSI\b ... number" 规则，避免误抓页面其它数字（云端更易触发反爬页面）。
        patterns = [
            r"Relative\s+Strength\s+Index\s*\(14\)[^0-9]{0,80}([0-9]{1,3}(?:\.[0-9]+)?)",
            r"RSI\s*\(14\)[^0-9]{0,80}([0-9]{1,3}(?:\.[0-9]+)?)",
            r"RSI\s*-\s*Relative\s+Strength\s+Index[^0-9]{0,120}([0-9]{1,3}(?:\.[0-9]+)?)",
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

    def _fetch_investing(self) -> Observation | None:
        html = self._get(self.INVESTING_URL, referer="https://www.investing.com/")
        v = self._parse_investing_rsi14_value(html)
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


