from __future__ import annotations

import re
from datetime import date
from html import unescape

import requests

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


class MacroMicroProvider(Provider):
    """
    MacroMicro: S&P 500 Breadth

    页面：
    - https://en.macromicro.me/charts/81081/S-P-500-Breadth

    说明：
    - MacroMicro 页面较多为动态渲染/反爬，可能在部分网络环境不可用。
    - 本 Provider **尽力解析**，解析失败则返回空（由上层“跳过获取不了的数据”）。
    """

    URL = "https://en.macromicro.me/charts/81081/S-P-500-Breadth"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.SP500_BREADTH not in set(indicator_ids):
            return []
        obs = self._fetch_breadth_best_effort()
        return [obs] if obs else []

    def _fetch_breadth_best_effort(self) -> Observation | None:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            }
            # 页面可能较慢/反爬：用短超时，避免阻塞仪表盘刷新
            resp = self.session.get(self.URL, headers=headers, timeout=(5, 12))
            if resp.status_code >= 400:
                return None
            html = resp.text

            # 1) 尝试 meta description / og:description 中的数值（页面常会把最新值写进去）
            mm = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html, re.IGNORECASE)
            desc = unescape(mm.group(1)) if mm else ""
            if not desc:
                mm = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', html, re.IGNORECASE)
                desc = unescape(mm.group(1)) if mm else ""

            if desc:
                # 取 description 中出现的第一个合理数值
                m = re.search(r"([0-9]+(?:\.[0-9]+)?)", desc)
                if m:
                    v = float(m.group(1))
                    return Observation(
                        indicator_id=IndicatorId.SP500_BREADTH,
                        as_of=date.today(),
                        value=v,
                        unit="index",
                        source="MacroMicro",
                        meta={"url": self.URL, "parse": "meta_description", "raw": desc[:240]},
                    )

            # 2) 兜底：从页面脚本中找 “Breadth” 附近的数值
            m = re.search(r"Breadth[^0-9]{0,120}([0-9]+(?:\.[0-9]+)?)", html, re.IGNORECASE)
            if m:
                v = float(m.group(1))
                return Observation(
                    indicator_id=IndicatorId.SP500_BREADTH,
                    as_of=date.today(),
                    value=v,
                    unit="index",
                    source="MacroMicro",
                    meta={"url": self.URL, "parse": "html_regex"},
                )

            return None
        except Exception:
            return None


