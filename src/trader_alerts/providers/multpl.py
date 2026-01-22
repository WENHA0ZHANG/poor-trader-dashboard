from __future__ import annotations

import re
from datetime import date

import requests

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


class MultplProvider(Provider):
    """
    从 multpl.com 的网页抓取最新 S&P 500 PE Ratio（非官方 API）。

    页面示例：`https://www.multpl.com/s-p-500-pe-ratio`
    """

    URL = "https://www.multpl.com/s-p-500-pe-ratio"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.SP500_PE_RATIO not in set(indicator_ids):
            return []
        return [self._fetch_sp500_pe_ratio()]

    def _fetch_sp500_pe_ratio(self) -> Observation:
        headers = {
            "User-Agent": "trader-alerts/0.1.0 (+https://local)",
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = self.session.get(self.URL, headers=headers, timeout=20)
        resp.raise_for_status()
        html = resp.text

        # Multpl 页面主体有时依赖 JS 渲染，但 <meta name="description"> 通常会带 “Current ... is 31.28”
        m = re.search(
            r'content="[^"]*Current\s*S&P\s*500\s*PE\s*Ratio\s*is\s*([0-9]+(?:\.[0-9]+)?)',
            html,
            re.IGNORECASE,
        )
        if not m:
            # 兼容另一种文本格式（如果未来页面直出）
            m = re.search(r"Current\s*S&P\s*500\s*PE\s*Ratio.*?([0-9]+(?:\.[0-9]+)?)", html, re.IGNORECASE)
        if not m:
            raise RuntimeError("无法从 multpl 页面解析 S&P 500 PE Ratio（meta/文本均未命中，页面结构可能变更）")

        value = float(m.group(1))

        # 尝试提取页面上的时间信息（仅作为 meta，解析失败也没关系）
        tm = re.search(r"(\d{1,2}:\d{2}\s*[AP]M\s*EST,\s*[^<\n]+)", html, re.IGNORECASE)
        reported = tm.group(1).strip() if tm else None

        return Observation(
            indicator_id=IndicatorId.SP500_PE_RATIO,
            as_of=date.today(),
            value=value,
            unit="x",
            source="multpl.com",
            meta={"url": self.URL, "reported": reported},
        )


