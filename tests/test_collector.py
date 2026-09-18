from __future__ import annotations

from datetime import timedelta

import asyncio
import socket

import pytest

from collector import SSEParser, SensorPool, SensorState, metric_from_identifier, metric_value, utc_now


def test_sse_parser_collects_state_frame():
    parser = SSEParser()
    assert parser.feed_line("event: state\n") is None
    assert parser.feed_line('data: {"id":"sensor-co2","value":412}\n') is None
    assert parser.feed_line("\n") == ("state", '{"id":"sensor-co2","value":412}')


def test_name_id_is_preferred_for_2026_3_firmware():
    payload = {"name_id": "sensor/PM <2.5um Weight conc.", "id": "sensor-wrong"}
    assert metric_from_identifier(payload) == "pm25"


def test_legacy_identifiers_and_unknown_entities():
    assert metric_from_identifier({"id": "sensor-pm_1_0"}) == "pm1"
    assert metric_from_identifier({"id": "sensor-sen55_voc"}) == "voc"
    assert metric_from_identifier({"id": "switch-led"}) is None
    assert metric_from_identifier({"id": "sensor-sen55_temperature_offset"}) is None


def test_temperature_conversion_and_invalid_values():
    assert metric_value({"value": 20.0}, "temperature") == 68.0
    assert metric_value({"value": "20"}, "temperature") is None
    assert metric_value({"value": float("nan")}, "co2") is None


def test_online_and_stale_state_transitions():
    sensor = SensorState(
        id="air-sensor-01", name="Sensor 1", hostname="sensor.example",
        mac=None, model="AIR-1", firmware_version=None, stale_after_seconds=180,
    )
    assert sensor.stale is True
    assert sensor.online is False
    sensor.connected = True
    sensor.last_seen = utc_now()
    assert sensor.online is True
    sensor.last_seen = utc_now() - timedelta(seconds=181)
    assert sensor.stale is True
    assert sensor.online is False


def test_malformed_sse_lines_are_ignored():
    parser = SSEParser()
    assert parser.feed_line(": keepalive\n") is None
    assert parser.feed_line("event: log\n") is None
    assert parser.feed_line("\n") is None


@pytest.mark.asyncio
async def test_dns_failure_retries_without_marking_sensor_online(monkeypatch):
    sensor = SensorState(
        id="air-sensor-01", name="Sensor 1", hostname="missing.example",
        mac=None, model="AIR-1", firmware_version=None, stale_after_seconds=180,
    )
    pool = SensorPool([sensor])
    attempts = 0

    async def fail_resolution(_sensor):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise socket.gaierror("not found")
        raise asyncio.CancelledError

    async def no_delay(_seconds):
        return None

    monkeypatch.setattr(pool, "_resolve", fail_resolution)
    monkeypatch.setattr("collector.asyncio.sleep", no_delay)
    with pytest.raises(asyncio.CancelledError):
        await pool._run_sensor(sensor)
    assert attempts == 2
    assert sensor.online is False


@pytest.mark.asyncio
async def test_clean_sse_eof_marks_offline_and_increases_backoff(monkeypatch):
    sensor = SensorState(
        id="air-sensor-01", name="Sensor 1", hostname="sensor.example",
        mac=None, model="AIR-1", firmware_version=None, stale_after_seconds=180,
        last_seen=utc_now(),
    )
    updates = []

    async def on_update(_sensor_id, state):
        updates.append(state["online"])

    class EmptyContent:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    class Response:
        headers = {"Content-Type": "text/event-stream"}
        content = EmptyContent()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def raise_for_status(self):
            return None

    class Session:
        def get(self, *_args, **_kwargs):
            return Response()

    pool = SensorPool([sensor], on_update=on_update)
    pool._session = Session()
    delays = []

    async def resolve(_sensor):
        return None

    async def record_delay(seconds):
        delays.append(seconds)
        if len(delays) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(pool, "_resolve", resolve)
    monkeypatch.setattr("collector.asyncio.sleep", record_delay)
    monkeypatch.setattr("collector.random.uniform", lambda *_args: 0)
    with pytest.raises(asyncio.CancelledError):
        await pool._run_sensor(sensor)
    assert sensor.connected is False
    assert delays == [1.0, 2.0]
    assert updates == [True, False, True, False]


@pytest.mark.asyncio
async def test_freshness_monitor_broadcasts_stale_transition(monkeypatch):
    sensor = SensorState(
        id="air-sensor-01", name="Sensor 1", hostname="sensor.example",
        mac=None, model="AIR-1", firmware_version=None, stale_after_seconds=180,
        connected=True, last_seen=utc_now(),
    )
    updates = []

    async def on_update(_sensor_id, state):
        updates.append((state["stale"], state["online"]))

    pool = SensorPool([sensor], on_update=on_update)
    sensor.last_seen = utc_now() - timedelta(seconds=181)
    sleep_calls = 0

    async def one_iteration(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise asyncio.CancelledError

    monkeypatch.setattr("collector.asyncio.sleep", one_iteration)
    with pytest.raises(asyncio.CancelledError):
        await pool._monitor_freshness()
    assert updates == [(True, False)]
