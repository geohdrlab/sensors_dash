from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite


logger = logging.getLogger("air_api.database")
VALID_METRICS = (
    "co2", "pm1", "pm25", "pm4", "pm10", "voc", "nox",
    "temperature", "humidity", "pressure", "rssi",
)
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS metrics_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sensor_metric_ts
ON metrics_history(sensor_id, metric, timestamp);
CREATE INDEX IF NOT EXISTS idx_sensor_ts
ON metrics_history(sensor_id, timestamp);
"""


async def _connect(path: Path) -> aiosqlite.Connection:
    connection = await aiosqlite.connect(path)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA foreign_keys=ON")
    await connection.execute("PRAGMA busy_timeout=5000")
    return connection


async def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = await _connect(path)
    try:
        await connection.execute("PRAGMA journal_mode=WAL")
        await connection.executescript(CREATE_TABLES_SQL)
        await connection.commit()
    finally:
        await connection.close()
    logger.info("Database initialized")


async def record_snapshot(
    path: Path,
    sensor_id: str,
    metrics: dict[str, Any],
    timestamp: datetime | None = None,
) -> None:
    recorded_at = timestamp or datetime.now(timezone.utc)
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    records = [
        (sensor_id, metric, float(metrics[metric]), recorded_at.astimezone(timezone.utc).isoformat())
        for metric in VALID_METRICS
        if isinstance(metrics.get(metric), (int, float)) and not isinstance(metrics.get(metric), bool)
    ]
    if not records:
        return
    connection = await _connect(path)
    try:
        await connection.executemany(
            "INSERT INTO metrics_history (sensor_id, metric, value, timestamp) VALUES (?, ?, ?, ?)",
            records,
        )
        await connection.commit()
    finally:
        await connection.close()


async def get_history(
    path: Path, sensor_id: str, metric: str, hours: float, limit: int
) -> tuple[list[dict[str, Any]], bool]:
    if metric not in VALID_METRICS:
        raise ValueError("Unsupported metric")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    connection = await _connect(path)
    try:
        cursor = await connection.execute(
            """
            SELECT timestamp, value FROM metrics_history
            WHERE sensor_id = ? AND metric = ? AND timestamp >= ?
            ORDER BY timestamp DESC LIMIT ?
            """,
            (sensor_id, metric, cutoff, limit + 1),
        )
        rows = await cursor.fetchall()
    finally:
        await connection.close()
    truncated = len(rows) > limit
    selected = list(reversed(rows[:limit]))
    return [
        {"timestamp": row["timestamp"], "value": round(row["value"], 2)}
        for row in selected
    ], truncated


async def get_readings(
    path: Path, sensor_id: str, hours: float, limit: int
) -> tuple[list[dict[str, Any]], bool]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    connection = await _connect(path)
    try:
        cursor = await connection.execute(
            """
            SELECT DISTINCT timestamp FROM metrics_history
            WHERE sensor_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC LIMIT ?
            """,
            (sensor_id, cutoff, limit + 1),
        )
        timestamp_rows = await cursor.fetchall()
        truncated = len(timestamp_rows) > limit
        timestamps = [row["timestamp"] for row in timestamp_rows[:limit]]
        if not timestamps:
            return [], False
        placeholders = ",".join("?" for _ in timestamps)
        cursor = await connection.execute(
            f"""
            SELECT timestamp, metric, value FROM metrics_history
            WHERE sensor_id = ? AND timestamp IN ({placeholders})
            ORDER BY timestamp ASC
            """,
            (sensor_id, *timestamps),
        )
        rows = await cursor.fetchall()
    finally:
        await connection.close()
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        grouped.setdefault(row["timestamp"], {"timestamp": row["timestamp"]})[
            row["metric"]
        ] = round(row["value"], 2)
    return list(grouped.values()), truncated


async def get_latest_snapshot(path: Path, sensor_id: str) -> dict[str, Any] | None:
    connection = await _connect(path)
    try:
        cursor = await connection.execute(
            """
            SELECT timestamp FROM metrics_history
            WHERE sensor_id = ? ORDER BY timestamp DESC LIMIT 1
            """,
            (sensor_id,),
        )
        latest = await cursor.fetchone()
        if latest is None:
            return None
        cursor = await connection.execute(
            """
            SELECT metric, value FROM metrics_history
            WHERE sensor_id = ? AND timestamp = ?
            """,
            (sensor_id, latest["timestamp"]),
        )
        rows = await cursor.fetchall()
    finally:
        await connection.close()
    result: dict[str, Any] = {"timestamp": latest["timestamp"]}
    result.update({row["metric"]: round(row["value"], 2) for row in rows})
    return result


async def cleanup_history(path: Path, retention_days: int) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    connection = await _connect(path)
    try:
        await connection.execute("DELETE FROM metrics_history WHERE timestamp < ?", (cutoff,))
        await connection.commit()
        await connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
    finally:
        await connection.close()
    logger.info("Database retention cleanup completed")
