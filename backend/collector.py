from __future__ import annotations

import asyncio
import json
import logging
import math
import random
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import aiohttp


logger = logging.getLogger("air_api.collector")
UpdateCallback = Callable[[str, dict[str, Any]], Awaitable[None]]
INTERNAL_METRICS = (
    "co2", "pm1", "pm25", "pm4", "pm10", "voc", "nox",
    "temperature", "humidity", "pressure", "rssi",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower().replace("µ", "u").replace("μ", "u"))


ENTITY_ALIASES = {
    "co2": "co2",
    "carbondioxide": "co2",
    "pm10": "pm1",
    "pm1": "pm1",
    "pm1umweightconcentration": "pm1",
    "pm1umweightconc": "pm1",
    "pm25": "pm25",
    "pm25umweightconcentration": "pm25",
    "pm25umweightconc": "pm25",
    "pm40": "pm4",
    "pm4": "pm4",
    "pm4umweightconcentration": "pm4",
    "pm4umweightconc": "pm4",
    "pm100": "pm10",
    "pm10umweightconcentration": "pm10",
    "pm10umweightconc": "pm10",
    "sen55voc": "voc",
    "voc": "voc",
    "sen55nox": "nox",
    "nox": "nox",
    "sen55temperature": "temperature",
    "temperature": "temperature",
    "sen55humidity": "humidity",
    "humidity": "humidity",
    "dps310pressure": "pressure",
    "pressure": "pressure",
    "wifisignaldb": "rssi",
    "wifisignal": "rssi",
    "rssi": "rssi",
}


def metric_from_identifier(payload: dict[str, Any]) -> str | None:
    identifier = payload.get("name_id") or payload.get("id")
    if not isinstance(identifier, str):
        return None
    if "/" in identifier:
        parts = identifier.split("/")
        if not parts or parts[0] != "sensor":
            return None
        entity = parts[-1]
    elif identifier.startswith("sensor-"):
        entity = identifier.removeprefix("sensor-")
    else:
        return None
    normalized = _normalized(entity)
    if "offset" in normalized or normalized == "dps310temperature":
        return None
    return ENTITY_ALIASES.get(normalized)


def metric_value(payload: dict[str, Any], metric: str) -> float | None:
    value = payload.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    if metric == "temperature":
        numeric = numeric * 1.8 + 32
    return round(numeric, 2)


class SSEParser:
    """Small line-oriented SSE parser for ESPHome's /events stream."""

    def __init__(self) -> None:
        self.event = "message"
        self.data: list[str] = []

    def feed_line(self, line: str) -> tuple[str, str] | None:
        line = line.rstrip("\r\n")
        if not line:
            if not self.data:
                self.event = "message"
                return None
            event = (self.event, "\n".join(self.data))
            self.event = "message"
            self.data = []
            return event
        if line.startswith(":"):
            return None
        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "event":
            self.event = value
        elif field == "data":
            self.data.append(value)
        return None


@dataclass
class SensorState:
    id: str
    name: str
    hostname: str
    mac: str | None
    model: str
    firmware_version: str | None
    stale_after_seconds: int
    connected: bool = False
    last_seen: datetime | None = None
    ip_address: str | None = None
    esphome_version: str | None = None
    metrics: dict[str, float | None] = field(
        default_factory=lambda: {name: None for name in INTERNAL_METRICS}
    )

    @property
    def stale(self) -> bool:
        if self.last_seen is None:
            return True
        return (utc_now() - self.last_seen).total_seconds() >= self.stale_after_seconds

    @property
    def online(self) -> bool:
        return self.connected and not self.stale

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "hostname": self.hostname,
            "online": self.online,
            "stale": self.stale,
            "last_seen": self.last_seen,
            "ip_address": self.ip_address,
            "mac": self.mac,
            "model": self.model,
            "firmware_version": self.firmware_version,
            "esphome_version": self.esphome_version,
            "metrics": dict(self.metrics),
        }


def load_sensor_config(path: Path, stale_after_seconds: int) -> list[SensorState]:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    sensors = raw.get("sensors") if isinstance(raw, dict) else None
    if not isinstance(sensors, list) or not sensors:
        raise ValueError("Sensor configuration must contain a nonempty sensors list")
    states: list[SensorState] = []
    seen: set[str] = set()
    for item in sensors:
        sensor_id = item["id"]
        if sensor_id in seen:
            raise ValueError(f"Duplicate sensor ID: {sensor_id}")
        seen.add(sensor_id)
        states.append(
            SensorState(
                id=sensor_id,
                name=item["name"],
                hostname=item["hostname"],
                mac=item.get("mac"),
                model=item.get("model", "Apollo AIR-1"),
                firmware_version=item.get("firmware_version"),
                stale_after_seconds=stale_after_seconds,
                esphome_version=item.get("esphome_version"),
            )
        )
    return states


class SensorPool:
    def __init__(self, sensors: list[SensorState], on_update: UpdateCallback | None = None):
        self.sensors = {sensor.id: sensor for sensor in sensors}
        self.on_update = on_update
        self._session: aiohttp.ClientSession | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._reported_stale = {sensor.id: sensor.stale for sensor in sensors}

    async def start(self) -> None:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=45)
        self._session = aiohttp.ClientSession(timeout=timeout)
        self._tasks = [
            asyncio.create_task(self._run_sensor(sensor), name=f"collector:{sensor.id}")
            for sensor in self.sensors.values()
        ]
        self._tasks.append(
            asyncio.create_task(self._monitor_freshness(), name="collector:freshness")
        )

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._session:
            await self._session.close()
            self._session = None

    def get(self, sensor_id: str) -> SensorState | None:
        return self.sensors.get(sensor_id)

    def all(self) -> list[SensorState]:
        return sorted(self.sensors.values(), key=lambda sensor: sensor.id)

    async def _notify(self, sensor: SensorState) -> None:
        self._reported_stale[sensor.id] = sensor.stale
        if self.on_update:
            await self.on_update(sensor.id, sensor.as_dict())

    async def _monitor_freshness(self) -> None:
        """Publish a transition when an open but silent stream becomes stale."""
        interval = max(
            1.0,
            min(
                5.0,
                min(
                    (sensor.stale_after_seconds for sensor in self.sensors.values()),
                    default=5,
                ) / 2,
            ),
        )
        while True:
            await asyncio.sleep(interval)
            for sensor in self.sensors.values():
                stale = sensor.stale
                if sensor.connected and stale != self._reported_stale[sensor.id]:
                    await self._notify(sensor)

    async def _resolve(self, sensor: SensorState) -> None:
        loop = asyncio.get_running_loop()
        records = await loop.getaddrinfo(
            sensor.hostname, 80, family=socket.AF_INET, type=socket.SOCK_STREAM
        )
        if records:
            sensor.ip_address = records[0][4][0]

    async def _run_sensor(self, sensor: SensorState) -> None:
        backoff = 1.0
        while True:
            stream_started: float | None = None
            try:
                await self._resolve(sensor)
                assert self._session is not None
                url = f"http://{sensor.hostname}/events"
                async with self._session.get(
                    url, headers={"Accept": "text/event-stream"}, allow_redirects=False
                ) as response:
                    response.raise_for_status()
                    if "text/event-stream" not in response.headers.get("Content-Type", ""):
                        raise RuntimeError("sensor did not return an event stream")
                    sensor.connected = True
                    stream_started = asyncio.get_running_loop().time()
                    logger.info("Sensor connected: %s", sensor.id)
                    await self._notify(sensor)
                    parser = SSEParser()
                    async for raw_line in response.content:
                        event = parser.feed_line(raw_line.decode("utf-8", "replace"))
                        if event:
                            await self._handle_event(sensor, *event)
                    raise ConnectionError("sensor event stream ended")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                was_connected = sensor.connected
                if was_connected:
                    logger.warning("Sensor disconnected: %s", sensor.id)
                else:
                    logger.debug("Sensor connection failed for %s: %s", sensor.id, type(exc).__name__)
                sensor.connected = False
                if was_connected:
                    await self._notify(sensor)
                if (
                    stream_started is not None
                    and asyncio.get_running_loop().time() - stream_started >= 10.0
                ):
                    backoff = 1.0
                delay = min(backoff, 60.0) + random.uniform(0, min(backoff * 0.2, 5.0))
                await asyncio.sleep(delay)
                backoff = min(backoff * 2, 60.0)

    async def _handle_event(self, sensor: SensorState, event: str, data: str) -> None:
        if event != "state":
            return
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return
        metric = metric_from_identifier(payload)
        if not metric:
            return
        value = metric_value(payload, metric)
        if value is None:
            return
        sensor.metrics[metric] = value
        sensor.last_seen = utc_now()
        await self._notify(sensor)
