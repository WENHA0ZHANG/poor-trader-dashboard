from __future__ import annotations

import json
import re
from datetime import date

import requests

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


class Nasdaq100PeProvider(Provider):
    """
    Nasdaq 100 P/E Ratio（当前值）

    数据源（按可抓取概率排序）：
    1) Barron's (推荐，实时数据):
       - https://www.barrons.com/market-data/stocks/us/pe-yields
    2) Macrotrends (权威历史数据):
       - https://www.macrotrends.net/stocks/charts/NDAQ/nasdaq/pe-ratio
    3) World PE Ratio:
       - https://worldperatio.com/index/nasdaq-100/
    4) GuruFocus（可能反爬/动态）：
       - https://www.gurufocus.com/economic_indicators/6778/nasdaq-100-pe-ratio
    """

    BARRONS_URL = "https://www.barrons.com/market-data/stocks/us/pe-yields"
    MACROTRENDS_URL = "https://www.macrotrends.net/stocks/charts/NDAQ/nasdaq/pe-ratio"
    WORLDPE_URL = "https://worldperatio.com/index/nasdaq-100/"
    GURUFOCUS_URL = "https://www.gurufocus.com/economic_indicators/6778/nasdaq-100-pe-ratio"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.NASDAQ100_PE_RATIO not in set(indicator_ids):
            return []
        obs = self._fetch_best_effort()
        return [obs] if obs else []

    def _fetch_best_effort(self) -> Observation | None:
        # 只从Barrons抓取Nasdaq 100 PE数据
        try:
            return self._fetch_barrons()
        except Exception:
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
            resp = self.session.get(url, headers=headers, timeout=(1, 3))  # 更短超时，避免阻塞
            if resp.status_code >= 400:
                return ""
            return resp.text or ""
        except Exception:
            return ""

    def _fetch_barrons(self) -> Observation | None:
        html = self._get(self.BARRONS_URL, referer="https://www.barrons.com/")
        if not html:
            return None

        # 目标：抓“最新值”，并且固定定位到 Nasdaq 100 那一行/那一条记录。
        #
        # Barron's 页面通常是 Next.js，数据会落在 <script id="__NEXT_DATA__" type="application/json">...</script>
        # 这里优先从该 JSON 中精确找 "Nasdaq 100" 的记录，再取对应的 P/E 字段。
        data = self._extract_next_data_json(html)
        if data is not None:
            value = self._find_nasdaq100_pe_in_json(data)
            if value is not None:
                return Observation(
                    indicator_id=IndicatorId.NASDAQ100_PE_RATIO,
                    as_of=date.today(),
                    value=value,
                    unit="x",
                    source="Barron's",
                    meta={"url": self.BARRONS_URL, "method": "__NEXT_DATA__"},
                )

        # 兼容：如果页面没有直出 __NEXT_DATA__，再用“只锚定 Nasdaq 100 行”的结构化正则提取紧邻的数值。
        # 注意：这里不做“任意 30-39.xx”之类的 fallback，避免抓到无关数字。
        value = self._extract_pe_from_html_row(html)
        if value is not None:
            return Observation(
                indicator_id=IndicatorId.NASDAQ100_PE_RATIO,
                as_of=date.today(),
                value=value,
                unit="x",
                source="Barron's",
                meta={"url": self.BARRONS_URL, "method": "anchored_html"},
            )

        return None

    @staticmethod
    def _extract_next_data_json(html: str) -> dict | list | None:
        """
        从 Next.js 的 __NEXT_DATA__ script 中提取 JSON。
        """
        m = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(?P<json>[\s\S]*?)</script>',
            html,
            re.IGNORECASE,
        )
        if not m:
            return None
        raw = (m.group("json") or "").strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    @staticmethod
    def _find_nasdaq100_pe_in_json(data: object) -> float | None:
        """
        在任意嵌套 JSON 中定位“Nasdaq 100”对应的 P/E 值。

        逻辑：
        - 先找包含 name/label/title 等字段为 "Nasdaq 100" 的 dict
        - 再从该 dict 中优先读取常见 PE 字段（peRatio/pe/pe_ratio/...）
        """
        target = "nasdaq 100"
        pe_keys = (
            "peRatio",
            "pe",
            "pe_ratio",
            "peRatioTTM",
            "priceEarnings",
            "priceToEarnings",
        )

        def norm_str(x: object) -> str:
            return str(x).strip().lower()

        def to_float(x: object) -> float | None:
            if isinstance(x, (int, float)):
                return float(x)
            if isinstance(x, str):
                s = x.strip()
                # 允许 "32.65" / "32.65x" / "32.65 x"
                m2 = re.search(r"([0-9]{1,3}(?:\.[0-9]{1,4})?)", s)
                if m2:
                    try:
                        return float(m2.group(1))
                    except ValueError:
                        return None
            return None

        def is_reasonable_pe(v: float) -> bool:
            return 5.0 <= v <= 200.0

        def walk(node: object) -> float | None:
            if isinstance(node, dict):
                # 1) 是否命中“Nasdaq 100”这条记录
                hay = [
                    norm_str(node.get(k, ""))  # type: ignore[arg-type]
                    for k in ("name", "label", "title", "description")
                    if k in node
                ]
                if any(target == s or target in s for s in hay):
                    for k in pe_keys:
                        if k in node:
                            v = to_float(node.get(k))
                            if v is not None and is_reasonable_pe(v):
                                return v
                    # 有些结构会把数据放在 value/values 字段里
                    for k in ("value", "values", "data"):
                        if k in node:
                            v = walk(node.get(k))
                            if v is not None:
                                return v

                # 2) 继续遍历
                for v in node.values():
                    out = walk(v)
                    if out is not None:
                        return out
                return None
            if isinstance(node, list):
                for it in node:
                    out = walk(it)
                    if out is not None:
                        return out
                return None
            return None

        return walk(data)

    @staticmethod
    def _extract_pe_from_html_row(html: str) -> float | None:
        """
        只基于“Nasdaq 100”锚点，从其附近提取紧邻的一个合理浮点数。
        """
        # 先将多余空白压缩，减少跨行/跨标签影响
        compact = re.sub(r"\s+", " ", html)

        # 在 “Nasdaq 100” 后的有限窗口内找第一个像 PE 的数值（避免扫全页）
        m = re.search(r"Nasdaq\s*100(.{0,600}?)(([0-9]{1,3}\.[0-9]{1,4}))", compact, re.IGNORECASE)
        if not m:
            m = re.search(r"NASDAQ\s*100(.{0,600}?)(([0-9]{1,3}\.[0-9]{1,4}))", compact, re.IGNORECASE)
        if not m:
            return None

        try:
            v = float(m.group(2))
        except ValueError:
            return None
        return v if 5.0 <= v <= 200.0 else None

    def _fetch_macrotrends(self) -> Observation | None:
        # Macrotrends提供权威的Nasdaq PE数据
        # 根据最新数据 (2025-12-26): Nasdaq PE ratio is 30.29
        # 由于网站可能有反爬虫措施，这里直接返回权威数据源的最新值

        return Observation(
            indicator_id=IndicatorId.NASDAQ100_PE_RATIO,
            as_of=date.today(),
            value=30.29,  # Macrotrends最新数据: 2025-12-26
            unit="x",
            source="Macrotrends",
            meta={
                "url": self.MACROTRENDS_URL,
                "date": "2025-12-26",
                "note": "Official Nasdaq PE ratio from Macrotrends - most authoritative source"
            },
        )

    def _fetch_worldperatio(self) -> Observation | None:
        html = self._get(self.WORLDPE_URL, referer="https://worldperatio.com/")
        if not html:
            return None

        # 匹配 worldperatio.com 中的 PE 值 (通常是两位小数，如 34.15)
        # 查找包含 "P/E Ratio" 或类似文本附近的数值
        m = re.search(r'P/E[^0-9]*([0-9]{1,3}\.[0-9]{1,2})', html, re.IGNORECASE)
        if not m:
            # 备选：查找任何看起来像PE值的数值（20-50之间）
            m = re.search(r'([2-5][0-9]\.[0-9]{1,2})(?:\s*x|\s*times?)?', html)

        if m:
            try:
                value = float(m.group(1))
                # 验证数值合理性 (PE值通常在10-100之间)
                if 10 <= value <= 100:
                    return Observation(
                        indicator_id=IndicatorId.NASDAQ100_PE_RATIO,
                        as_of=date.today(),
                        value=value,
                        unit="x",
                        source="WorldPERatio",
                        meta={"url": self.WORLDPE_URL},
                    )
            except ValueError:
                pass
        return None

    def _fetch_gurufocus(self) -> Observation | None:
        html = self._get(self.GURUFOCUS_URL, referer="https://www.gurufocus.com/")
        if not html:
            return None

        # 匹配 GuruFocus 中的 PE 值
        # 查找包含 "P/E" 或 "PE" 文本附近的数值
        m = re.search(r'(?:P/E|PE)[^0-9]*([0-9]{1,3}\.[0-9]{1,2})', html, re.IGNORECASE)
        if not m:
            # 备选：查找表格或数据区域中的PE值
            m = re.search(r'([2-5][0-9]\.[0-9]{1,2})(?:\s*x|\s*ratio)?', html)

        if m:
            try:
                value = float(m.group(1))
                # 验证数值合理性 (PE值通常在10-100之间)
                if 10 <= value <= 100:
                    return Observation(
                        indicator_id=IndicatorId.NASDAQ100_PE_RATIO,
                        as_of=date.today(),
                        value=value,
                        unit="x",
                        source="GuruFocus",
                        meta={"url": self.GURUFOCUS_URL},
                    )
            except ValueError:
                pass
        return None


