from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth import AuthContext, authenticate_request
from collector import SensorPool, SensorState, load_sensor_config, utc_now
from config import Settings
from database import cleanup_history, get_history, get_latest_snapshot, get_readings, init_db, record_snapshot
from models import (
    ErrorResponse, HealthResponse, HistoryResponse, INTERNAL_TO_PUBLIC,
    MetricDefinition, MetricName, MetricsResponse, PUBLIC_TO_INTERNAL,
    ReadingsResponse, SensorDetail, SensorListResponse, SensorSummary,
    ServiceDescriptor, Telemetry,
)


VERSION = "2.0.0"
logger = logging.getLogger("air_api.main")
METRIC_DEFINITIONS = [
    MetricDefinition(key=MetricName.co2, label="Carbon dioxide", unit="ppm"),
    MetricDefinition(key=MetricName.pm1_0, label="PM1.0", unit="µg/m³"),
    MetricDefinition(key=MetricName.pm2_5, label="PM2.5", unit="µg/m³"),
    MetricDefinition(key=MetricName.pm4_0, label="PM4.0", unit="µg/m³"),
    MetricDefinition(key=MetricName.pm10, label="PM10", unit="µg/m³"),
    MetricDefinition(key=MetricName.voc, label="VOC index", unit="index"),
    MetricDefinition(key=MetricName.nox, label="NOx index", unit="index"),
    MetricDefinition(key=MetricName.temperature, label="Temperature", unit="°F"),
    MetricDefinition(key=MetricName.humidity, label="Relative humidity", unit="%"),
    MetricDefinition(key=MetricName.pressure, label="Barometric pressure", unit="hPa"),
    MetricDefinition(key=MetricName.rssi, label="Wi-Fi signal", unit="dBm"),
]


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: list[tuple[WebSocket, bool]] = []

    async def connect(self, websocket: WebSocket, authenticated: bool) -> None:
        self.connections.append((websocket, authenticated))

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections = [item for item in self.connections if item[0] is not websocket]

    async def broadcast(self, sensor: SensorState) -> None:
        dead: list[WebSocket] = []
        for websocket, authenticated in self.connections:
            try:
                await websocket.send_json(jsonable_encoder({
                    "type": "sensor_update",
                    "timestamp": utc_now().isoformat(),
                    "data": sensor_payload(sensor, authenticated, include_latest=True),
                }))
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)


def public_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {INTERNAL_TO_PUBLIC[key]: value for key, value in metrics.items() if key in INTERNAL_TO_PUBLIC}


def telemetry_payload(sensor: SensorState, timestamp: datetime, metrics: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "sensor_id": sensor.id,
        "online": sensor.online,
        "stale": sensor.stale,
        "last_seen": sensor.last_seen,
        "timestamp": timestamp,
    }
    payload.update(public_metrics(metrics))
    return payload


def sensor_payload(sensor: SensorState, authenticated: bool, include_latest: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": sensor.id,
        "name": sensor.name,
        "hostname": sensor.hostname,
        "online": sensor.online,
        "stale": sensor.stale,
        "last_seen": sensor.last_seen,
        "timestamp": utc_now(),
        "ip_address": sensor.ip_address if authenticated else None,
        "mac": sensor.mac if authenticated else None,
        "model": sensor.model,
        "firmware_version": sensor.firmware_version,
        "esphome_version": sensor.esphome_version,
    }
    if include_latest:
        payload["latest"] = telemetry_payload(sensor, sensor.last_seen, sensor.metrics) if sensor.last_seen else None
    return payload


def error(status_code: int, detail: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"detail": detail, "code": code})


def create_app(settings: Settings | None = None, start_background: bool = True) -> FastAPI:
    active_settings = settings or Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, active_settings.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    manager = ConnectionManager()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        logger.info("Starting AIR-1 API service")
        await init_db(active_settings.database_path)

        async def on_update(sensor_id: str, _: dict[str, Any]) -> None:
            sensor = application.state.pool.get(sensor_id)
            if sensor:
                await manager.broadcast(sensor)

        sensors = load_sensor_config(active_settings.sensor_config_path, active_settings.stale_after_seconds)
        application.state.pool = SensorPool(sensors, on_update=on_update)
        tasks: list[asyncio.Task[None]] = []
        if start_background:
            await application.state.pool.start()
            tasks = [
                asyncio.create_task(snapshot_loop(application), name="snapshot-loop"),
                asyncio.create_task(cleanup_loop(application), name="cleanup-loop"),
            ]
        application.state.background_tasks = tasks
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await application.state.pool.stop()
            logger.info("AIR-1 API service stopped")

    application = FastAPI(
        title="GeoHDR Lab AIR-1 Sensor API",
        description="Read-only API for current and historical Apollo AIR-1 measurements.",
        version=VERSION,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "health", "description": "Service availability."},
            {"name": "sensors", "description": "Sensor inventory and current state."},
            {"name": "history", "description": "Bounded SQLite telemetry queries."},
            {"name": "stream", "description": "Live collector updates."},
        ],
    )
    application.state.settings = active_settings
    application.state.pool = SensorPool([])
    application.state.manager = manager

    if active_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(active_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "OPTIONS"],
            allow_headers=["X-API-Key"],
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled API error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error", "code": "internal_error"})

    @application.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and {"detail", "code"} <= exc.detail.keys():
            return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail), "code": "http_error"}, headers=exc.headers)

    @application.get("/", response_model=ServiceDescriptor, include_in_schema=False)
    async def root() -> ServiceDescriptor:
        return ServiceDescriptor()

    @application.get("/api/v1/health", response_model=HealthResponse, tags=["health"], summary="Check API availability")
    async def health() -> HealthResponse:
        return HealthResponse()

    @application.get("/api/v1/sensors", response_model=SensorListResponse, tags=["sensors"], summary="List the AIR-1 sensor fleet")
    async def list_sensors(auth: AuthContext = Depends(authenticate_request)) -> SensorListResponse:
        sensors = [SensorSummary(**sensor_payload(item, auth.authenticated)) for item in application.state.pool.all()]
        return SensorListResponse(count=len(sensors), sensors=sensors)

    def require_sensor(sensor_id: str) -> SensorState:
        sensor = application.state.pool.get(sensor_id)
        if sensor is None:
            raise error(404, "Sensor not found", "sensor_not_found")
        return sensor

    async def latest_for(sensor: SensorState) -> Telemetry | None:
        if sensor.last_seen is not None and any(value is not None for value in sensor.metrics.values()):
            return Telemetry(**telemetry_payload(sensor, sensor.last_seen, sensor.metrics))
        stored = await get_latest_snapshot(active_settings.database_path, sensor.id)
        if stored is None:
            return None
        timestamp = datetime.fromisoformat(stored.pop("timestamp"))
        return Telemetry(**telemetry_payload(sensor, timestamp, stored))

    @application.get("/api/v1/sensors/{sensor_id}", response_model=SensorDetail, responses={404: {"model": ErrorResponse}}, tags=["sensors"], summary="Get one sensor and its latest reading")
    async def get_sensor(sensor_id: str, auth: AuthContext = Depends(authenticate_request)) -> SensorDetail:
        sensor = require_sensor(sensor_id)
        payload = sensor_payload(sensor, auth.authenticated)
        payload["latest"] = await latest_for(sensor)
        return SensorDetail(**payload)

    @application.get("/api/v1/sensors/{sensor_id}/latest", response_model=Telemetry, responses={404: {"model": ErrorResponse}}, tags=["sensors"], summary="Get the most recent actual reading")
    async def get_latest(sensor_id: str, _: AuthContext = Depends(authenticate_request)) -> Telemetry:
        latest = await latest_for(require_sensor(sensor_id))
        if latest is None:
            raise error(404, "No reading has been recorded", "reading_not_found")
        return latest

    @application.get("/api/v1/sensors/{sensor_id}/history", response_model=HistoryResponse, tags=["history"], summary="Query one historical metric")
    async def sensor_history(
        sensor_id: str,
        metric: MetricName = Query(MetricName.co2, description="Metric to retrieve"),
        hours: float = Query(24, ge=1, le=720, description="Lookback window in hours"),
        limit: int = Query(1000, ge=1, le=5000, description="Maximum points returned"),
        _: AuthContext = Depends(authenticate_request),
    ) -> HistoryResponse:
        require_sensor(sensor_id)
        data, truncated = await get_history(active_settings.database_path, sensor_id, PUBLIC_TO_INTERNAL[metric.value], hours, limit)
        return HistoryResponse(sensor_id=sensor_id, metric=metric, hours=hours, count=len(data), truncated=truncated, data=data)

    @application.get("/api/v1/sensors/{sensor_id}/readings", response_model=ReadingsResponse, tags=["history"], summary="Query multi-metric historical snapshots")
    async def sensor_readings(
        sensor_id: str,
        hours: float = Query(24, ge=1, le=720, description="Lookback window in hours"),
        limit: int = Query(1000, ge=1, le=5000, description="Maximum snapshots returned"),
        _: AuthContext = Depends(authenticate_request),
    ) -> ReadingsResponse:
        sensor = require_sensor(sensor_id)
        rows, truncated = await get_readings(active_settings.database_path, sensor_id, hours, limit)
        data = [Telemetry(**telemetry_payload(
            sensor, datetime.fromisoformat(row["timestamp"]),
            {key: value for key, value in row.items() if key != "timestamp"},
        )) for row in rows]
        return ReadingsResponse(sensor_id=sensor_id, hours=hours, count=len(data), truncated=truncated, data=data)

    @application.get("/api/v1/metrics", response_model=MetricsResponse, tags=["sensors"], summary="List supported telemetry metrics and units")
    async def metrics(_: AuthContext = Depends(authenticate_request)) -> MetricsResponse:
        return MetricsResponse(metrics=METRIC_DEFINITIONS)

    @application.websocket("/api/v1/ws", name="Live sensor stream")
    async def websocket_stream(websocket: WebSocket) -> None:
        settings_for_ws = application.state.settings
        supplied = websocket.headers.get("x-api-key", "")
        authenticated = bool(settings_for_ws.api_key and supplied and secrets.compare_digest(supplied, settings_for_ws.api_key))
        await websocket.accept()
        if settings_for_ws.require_api_key and not authenticated:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
                candidate = (
                    message.get("api_key", "")
                    if isinstance(message, dict) and message.get("type") == "authenticate"
                    else ""
                )
                authenticated = bool(candidate and secrets.compare_digest(candidate, settings_for_ws.api_key))
            except Exception:
                authenticated = False
            if not authenticated:
                await websocket.close(code=1008, reason="Authentication required")
                return
        await manager.connect(websocket, authenticated)
        await websocket.send_json(jsonable_encoder({
            "type": "initial_state", "timestamp": utc_now().isoformat(),
            "data": [sensor_payload(sensor, authenticated, True) for sensor in application.state.pool.all()],
        }))
        try:
            while True:
                message = await websocket.receive_text()
                if message == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": utc_now().isoformat()})
        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect(websocket)

    return application


async def snapshot_loop(application: FastAPI) -> None:
    settings = application.state.settings
    while True:
        try:
            await asyncio.sleep(settings.snapshot_interval_seconds)
            for sensor in application.state.pool.all():
                if sensor.online and any(value is not None for value in sensor.metrics.values()):
                    await record_snapshot(settings.database_path, sensor.id, sensor.metrics, sensor.last_seen)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Snapshot loop failed")


async def cleanup_loop(application: FastAPI) -> None:
    settings = application.state.settings
    while True:
        try:
            await asyncio.sleep(86400)
            await cleanup_history(settings.database_path, settings.history_retention_days)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Database cleanup loop failed")


app = create_app()


if __name__ == "__main__":
    import uvicorn
    configured = app.state.settings
    uvicorn.run(app, host=configured.host, port=configured.port)
