from __future__ import annotations

import json
import random
import re
import string
import ssl
from datetime import date, datetime, timezone
from typing import Any

import certifi
from websocket import WebSocketTimeoutException, create_connection

from ..constants import IndicatorId
from ..models import Observation
from .base import Provider


def _rand_session(prefix: str) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return prefix + "".join(random.choice(alphabet) for _ in range(12))


def _pack(obj: dict[str, Any]) -> str:
    raw = json.dumps(obj, separators=(",", ":"))
    return f"~m~{len(raw)}~m~{raw}"


_MSG_RE = re.compile(r"~m~(\\d+)~m~")


def _iter_payloads(frame: str) -> list[dict[str, Any]]:
    """
    TradingView socket.io websocket 的文本帧会把多个 JSON message 拼在一起：
    ~m~<len>~m~<json>~m~<len>~m~<json>...
    """
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(frame):
        m = _MSG_RE.match(frame, i)
        if not m:
            break
        n = int(m.group(1))
        j = m.end()
        raw = frame[j : j + n]
        i = j + n
        try:
            out.append(json.loads(raw))
        except Exception:
            continue
    return out


class TradingViewWSProvider(Provider):
    """
    用 TradingView WebSocket 获取最新“报价”（不需要 FRED API Key）。

    目标：FRED:BAMLH0A0HYM2（ICE BofA US HY OAS）
    - 返回单位：TradingView 页面显示是 %，这里会转换成 bp（x100）以匹配项目阈值。

    参考页面：
    - https://www.tradingview.com/symbols/FRED-BAMLH0A0HYM2/
    """

    WS_URL = "wss://data.tradingview.com/socket.io/websocket"

    def fetch(self, indicator_ids: list[IndicatorId]) -> list[Observation]:
        if indicator_ids and IndicatorId.US_HIGH_YIELD_SPREAD not in set(indicator_ids):
            return []
        return [self._fetch_hy_oas()]

    def _fetch_hy_oas(self) -> Observation:
        symbol = "FRED:BAMLH0A0HYM2"
        csid = _rand_session("cs_")
        series_id = "s1"

        # websocket-client: 显式指定 CA 证书，避免部分环境 SSL 验证失败
        ws = create_connection(
            self.WS_URL,
            timeout=20,
            origin="https://www.tradingview.com",
            sslopt={"cert_reqs": ssl.CERT_REQUIRED, "ca_certs": certifi.where()},
        )
        try:
            # 先读一次，处理心跳（有些环境必须先回应 ping 才会继续下发数据）
            try:
                first = ws.recv()
                if isinstance(first, str) and "~h~" in first:
                    ws.send(first)
            except Exception:
                pass

            # 1) unauthorized token（公开会话）
            ws.send(_pack({"m": "set_auth_token", "p": ["unauthorized_user_token"]}))

            # 2) chart session（用于取时间序列）
            ws.send(_pack({"m": "chart_create_session", "p": [csid, ""]}))

            # 3) resolve symbol + create series（取最近 2 根日线）
            sym_obj = json.dumps({"symbol": symbol, "adjustment": "splits", "session": "regular"}, separators=(",", ":"))
            ws.send(_pack({"m": "resolve_symbol", "p": [csid, "sym_1", "=" + sym_obj]}))
            ws.send(_pack({"m": "create_series", "p": [csid, series_id, series_id, "sym_1", "D", 2]}))

            deadline = datetime.now(timezone.utc).timestamp() + 25
            last_close_pct: float | None = None
            last_ts: int | None = None
            meta: dict[str, Any] = {"symbol": symbol, "provider": "TradingViewWS"}

            while datetime.now(timezone.utc).timestamp() < deadline:
                try:
                    frame = ws.recv()
                except WebSocketTimeoutException:
                    continue

                # 心跳：收到 ~h~n 需要原样发回
                if isinstance(frame, str) and "~h~" in frame:
                    try:
                        ws.send(frame)
                    except Exception:
                        pass

                # 心跳
                if frame.startswith("~m~") is False:
                    continue

                for msg in _iter_payloads(frame):
                    m = msg.get("m")
                    p = msg.get("p")
                    # chart 数据：timescale_update
                    if m == "timescale_update" and isinstance(p, list) and len(p) >= 2 and isinstance(p[1], dict):
                        series_blob = p[1].get(series_id)
                        if not isinstance(series_blob, dict):
                            continue
                        bars = series_blob.get("s")
                        if not isinstance(bars, list) or not bars:
                            continue
                        last = bars[-1]
                        # bars 可能是 list[dict(i, v=[t,o,h,l,c,...])]
                        if isinstance(last, dict) and isinstance(last.get("v"), list):
                            last = last["v"]
                        if not isinstance(last, list) or len(last) < 2:
                            continue
                        try:
                            last_ts = int(last[0])
                        except Exception:
                            last_ts = None
                        # 常见格式：[t, o, h, l, c, v]
                        try:
                            if len(last) >= 5:
                                last_close_pct = float(last[4])
                            else:
                                last_close_pct = float(last[1])
                        except Exception:
                            continue

                    if last_close_pct is not None:
                        break
                if last_close_pct is not None:
                    break

            if last_close_pct is None:
                raise RuntimeError("TradingViewWS 未返回 timescale_update（无法拿到最新 close）")

            as_of = date.today()
            if last_ts:
                try:
                    as_of = datetime.fromtimestamp(last_ts, tz=timezone.utc).date()
                except Exception:
                    pass

            pct = float(last_close_pct)
            return Observation(
                indicator_id=IndicatorId.US_HIGH_YIELD_SPREAD,
                as_of=as_of,
                value=pct * 100.0,
                unit="bp",
                source="TradingView:WS(FRED:BAMLH0A0HYM2)",
                meta={**meta, "raw_percent": pct, "raw_epoch": last_ts},
            )
        finally:
            try:
                ws.close()
            except Exception:
                pass


