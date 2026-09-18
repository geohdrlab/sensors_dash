from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest

from database import get_history, get_latest_snapshot, get_readings, init_db, record_snapshot


@pytest.mark.asyncio
async def test_database_is_idempotent_and_uses_wal(tmp_path):
    path = tmp_path / "history.db"
    await init_db(path)
    await init_db(path)
    async with aiosqlite.connect(path) as connection:
        cursor = await connection.execute("PRAGMA journal_mode")
        assert (await cursor.fetchone())[0].lower() == "wal"


@pytest.mark.asyncio
async def test_history_latest_and_snapshot_queries_are_bounded(tmp_path):
    path = tmp_path / "history.db"
    await init_db(path)
    base = datetime.now(timezone.utc) - timedelta(minutes=3)
    for offset in range(3):
        await record_snapshot(
            path,
            "air-sensor-01",
            {"co2": 400 + offset, "pm25": 5 + offset},
            base + timedelta(minutes=offset),
        )

    history, truncated = await get_history(path, "air-sensor-01", "co2", 24, 2)
    assert truncated is True
    assert [point["value"] for point in history] == [401.0, 402.0]

    readings, truncated = await get_readings(path, "air-sensor-01", 24, 2)
    assert truncated is True
    assert len(readings) == 2
    assert readings[-1]["pm25"] == 7.0

    latest = await get_latest_snapshot(path, "air-sensor-01")
    assert latest is not None
    assert latest["co2"] == 402.0
    assert datetime.fromisoformat(latest["timestamp"]).tzinfo is not None


@pytest.mark.asyncio
async def test_invalid_internal_metric_is_rejected(tmp_path):
    path = tmp_path / "history.db"
    await init_db(path)
    with pytest.raises(ValueError):
        await get_history(path, "air-sensor-01", "not-a-metric", 24, 10)
