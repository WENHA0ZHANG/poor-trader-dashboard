from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


class CnnFearGreedProvider(Provider):
    """
    CNN Fear & Greed Index 数据源（JSON）。

    数据接口（网页内部调用）：
    - https://production.dataviz.cnn.io/index/fearandgreed/graphdata

    页面：
    - https://edition.cnn.com/markets/fear-and-greed
    """

    URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    REFERER = "https://edition.cnn.com/markets/fear-and-greed"
    ORIGIN = "https://edition.cnn.com"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        want = set(indicator_ids) if indicator_ids else {IndicatorId.CNN_FEAR_GREED_INDEX, IndicatorId.CNN_PUT_CALL_OPTIONS}
        if IndicatorId.CNN_FEAR_GREED_INDEX not in want and IndicatorId.CNN_PUT_CALL_OPTIONS not in want:
            return []

        data = self._fetch_graphdata()
        out: list[Observation] = []
        if IndicatorId.CNN_FEAR_GREED_INDEX in want:
            o = self._parse_fng(data)
            if o:
                out.append(o)
        if IndicatorId.CNN_PUT_CALL_OPTIONS in want:
            o = self._parse_put_call(data)
            if o:
                out.append(o)
        return out

    def _fetch_graphdata(self) -> dict[str, Any]:
        headers = {
            # 关键：需要像浏览器一样带 Referer/Origin/UA，否则可能返回 418
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.REFERER,
            "Origin": self.ORIGIN,
            "Connection": "keep-alive",
        }
        resp = self.session.get(self.URL, headers=headers, timeout=20)
        if resp.status_code == 418:
            raise RuntimeError("CNN graphdata 返回 418（被识别为 bot）。请稍后重试或更换网络。")
        resp.raise_for_status()
        return resp.json()

    def _parse_fng(self, data: dict[str, Any]) -> Observation | None:
        fg = data.get("fear_and_greed") or {}
        if not fg:
            return None
        score = float(fg["score"])
        rating = str(fg.get("rating") or "")
        ts = str(fg.get("timestamp") or "")

        as_of = date.today()
        if ts:
            try:
                as_of = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
            except Exception:
                pass

        return Observation(
            indicator_id=IndicatorId.CNN_FEAR_GREED_INDEX,
            as_of=as_of,
            value=score,
            unit="0-100",
            source="CNN:dataviz",
            meta={"url": self.URL, "rating": rating, "timestamp": ts},
        )

    def _find_component(self, data: dict[str, Any], *, keywords: list[str]) -> dict[str, Any] | None:
        # 1) 常见：顶层 key 就是 component
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            lk = k.lower()
            if all(kw in lk for kw in keywords):
                return v
        # 2) 兜底：any keyword match
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            lk = k.lower()
            if any(kw in lk for kw in keywords):
                return v
        return None

    def _parse_put_call(self, data: dict[str, Any]) -> Observation | None:
        # Put/Call component（CNN 页面名：put and call options / 5-day avg put/call ratio）
        comp = (
            data.get("put_call_options")
            or data.get("putCallOptions")
            or data.get("put_call")
            or self._find_component(data, keywords=["put", "call"])
        )
        if not isinstance(comp, dict) or not comp:
            return None

        rating = str(comp.get("rating") or "")
        ts = str(comp.get("timestamp") or "")
        as_of = date.today()
        if ts:
            try:
                as_of = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
            except Exception:
                pass

        # 优先从 data 序列取最后一个 y（更可能是“ratio”）
        value: float | None = None
        unit = "ratio"
        series = comp.get("data")
        if isinstance(series, list) and series:
            last = series[-1]
            if isinstance(last, dict):
                for key in ("y", "value", "close"):
                    if key in last:
                        try:
                            value = float(last[key])
                            break
                        except Exception:
                            pass

        # 兜底：如果只给 score（0-100），那就跳过（用户要的是 put/call ratio）
        if value is None:
            return None

        return Observation(
            indicator_id=IndicatorId.CNN_PUT_CALL_OPTIONS,
            as_of=as_of,
            value=value,
            unit=unit,
            source="CNN:dataviz",
            meta={"url": self.URL, "rating": rating, "timestamp": ts},
        )


