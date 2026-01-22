from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .constants import IndicatorId
from .models import Observation


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: str | Path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS observations (
              indicator_id TEXT NOT NULL,
              as_of TEXT NOT NULL,
              value REAL NOT NULL,
              unit TEXT NOT NULL,
              source TEXT NOT NULL,
              meta_json TEXT,
              inserted_at TEXT NOT NULL,
              PRIMARY KEY (indicator_id, as_of)
            )
            """
        )


def upsert_observations(db_path: str | Path, observations: Iterable[Observation]) -> int:
    init_db(db_path)
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    rows = []
    for obs in observations:
        rows.append(
            (
                obs.indicator_id.value,
                obs.as_of.isoformat(),
                float(obs.value),
                obs.unit,
                obs.source,
                json.dumps(obs.meta or {}, ensure_ascii=False),
                now,
            )
        )

    with _connect(db_path) as conn:
        cur = conn.executemany(
            """
            INSERT INTO observations (indicator_id, as_of, value, unit, source, meta_json, inserted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(indicator_id, as_of)
            DO UPDATE SET
              value=excluded.value,
              unit=excluded.unit,
              source=excluded.source,
              meta_json=excluded.meta_json,
              inserted_at=excluded.inserted_at
            """,
            rows,
        )
        return cur.rowcount


def latest_observation(db_path: str | Path, indicator_id: IndicatorId) -> Observation | None:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT indicator_id, as_of, value, unit, source, meta_json
            FROM observations
            WHERE indicator_id = ?
            ORDER BY as_of DESC
            LIMIT 1
            """,
            (indicator_id.value,),
        ).fetchone()
    if not row:
        return None
    return Observation(
        indicator_id=IndicatorId(row[0]),
        as_of=date.fromisoformat(row[1]),
        value=float(row[2]),
        unit=row[3],
        source=row[4],
        meta=json.loads(row[5]) if row[5] else {},
    )


def recent_observations(
    db_path: str | Path,
    indicator_id: IndicatorId,
    days: int,
) -> list[Observation]:
    init_db(db_path)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT indicator_id, as_of, value, unit, source, meta_json
            FROM observations
            WHERE indicator_id = ?
              AND as_of >= ?
            ORDER BY as_of ASC
            """,
            (indicator_id.value, cutoff),
        ).fetchall()

    out: list[Observation] = []
    for row in rows:
        out.append(
            Observation(
                indicator_id=IndicatorId(row[0]),
                as_of=date.fromisoformat(row[1]),
                value=float(row[2]),
                unit=row[3],
                source=row[4],
                meta=json.loads(row[5]) if row[5] else {},
            )
        )
    return out


def get_last_update_time(db_path: str | Path) -> datetime | None:
    """获取数据库中最后一次数据更新的时间戳"""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT MAX(inserted_at) AS latest_update
            FROM observations
            """
        ).fetchone()

    if row and row[0]:
        # 将ISO格式的字符串转换为datetime对象
        # 格式如: 2025-12-29T14:30:25Z
        if row[0].endswith('Z'):
            dt_str = row[0][:-1]  # 移除Z
            return datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
    return None


def list_latest(db_path: str | Path) -> dict[IndicatorId, Observation]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT o.indicator_id, o.as_of, o.value, o.unit, o.source, o.meta_json
            FROM observations o
            INNER JOIN (
              SELECT indicator_id, MAX(as_of) AS max_as_of
              FROM observations
              GROUP BY indicator_id
            ) m
            ON o.indicator_id = m.indicator_id AND o.as_of = m.max_as_of
            ORDER BY o.indicator_id ASC
            """
        ).fetchall()

    out: dict[IndicatorId, Observation] = {}
    for row in rows:
        try:
            ind = IndicatorId(row[0])
        except Exception:
            # 数据库里可能存在历史指标（已从当前版本移除），直接忽略
            continue
        out[ind] = Observation(
            indicator_id=ind,
            as_of=date.fromisoformat(row[1]),
            value=float(row[2]),
            unit=row[3],
            source=row[4],
            meta=json.loads(row[5]) if row[5] else {},
        )
    return out


