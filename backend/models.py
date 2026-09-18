from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class MetricName(str, Enum):
    co2 = "co2"
    pm1_0 = "pm1_0"
    pm2_5 = "pm2_5"
    pm4_0 = "pm4_0"
    pm10 = "pm10"
    voc = "voc"
    nox = "nox"
    temperature = "temperature"
    humidity = "humidity"
    pressure = "pressure"
    rssi = "rssi"


PUBLIC_TO_INTERNAL = {
    "co2": "co2",
    "pm1_0": "pm1",
    "pm2_5": "pm25",
    "pm4_0": "pm4",
    "pm10": "pm10",
    "voc": "voc",
    "nox": "nox",
    "temperature": "temperature",
    "humidity": "humidity",
    "pressure": "pressure",
    "rssi": "rssi",
}
INTERNAL_TO_PUBLIC = {value: key for key, value in PUBLIC_TO_INTERNAL.items()}


class ServiceDescriptor(BaseModel):
    service: str = "GeoHDR Lab AIR-1 Sensor API"
    status: str = "online"
    version: str = "2.0.0"
    documentation: str = "/docs"
    health: str = "/api/v1/health"


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "2.0.0"


class SensorSummary(BaseModel):
    id: str
    name: str
    hostname: str
    online: bool
    stale: bool
    last_seen: datetime | None
    timestamp: datetime
    ip_address: str | None = None
    mac: str | None = None
    model: str
    firmware_version: str | None = None
    esphome_version: str | None = None


class Telemetry(BaseModel):
    sensor_id: str
    online: bool
    stale: bool
    last_seen: datetime | None
    timestamp: datetime
    co2: float | None = None
    pm1_0: float | None = None
    pm2_5: float | None = None
    pm4_0: float | None = None
    pm10: float | None = None
    voc: float | None = None
    nox: float | None = None
    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    rssi: float | None = None


class SensorDetail(SensorSummary):
    latest: Telemetry | None = None


class SensorListResponse(BaseModel):
    count: int
    sensors: list[SensorSummary]


class HistoryPoint(BaseModel):
    timestamp: datetime
    value: float


class HistoryResponse(BaseModel):
    sensor_id: str
    metric: MetricName
    hours: float
    count: int
    truncated: bool
    data: list[HistoryPoint]


class ReadingsResponse(BaseModel):
    sensor_id: str
    hours: float
    count: int
    truncated: bool
    data: list[Telemetry]


class MetricDefinition(BaseModel):
    key: MetricName
    label: str
    unit: str


class MetricsResponse(BaseModel):
    metrics: list[MetricDefinition]


class ErrorResponse(BaseModel):
    detail: str
    code: str
