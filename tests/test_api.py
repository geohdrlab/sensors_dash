from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from database import record_snapshot
from main import create_app, snapshot_loop


def test_public_descriptor_health_and_openapi(settings_factory):
    app = create_app(settings_factory(), start_background=False)
    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert root.json()["health"] == "/api/v1/health"
        assert client.get("/api/v1/health").json() == {"status": "ok", "version": "2.0.0"}
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()
        assert schema["info"]["title"] == "GeoHDR Lab AIR-1 Sensor API"
        assert "/api/v1/sensors" in schema["paths"]
        assert "/api/sensors" not in schema["paths"]


def test_sensor_routes_history_limits_and_metadata_redaction(settings_factory):
    settings = settings_factory(api_key="secret")
    app = create_app(settings, start_background=False)
    with TestClient(app) as client:
        sensor = app.state.pool.get("air-sensor-01")
        sensor.connected = True
        sensor.last_seen = datetime.now(timezone.utc)
        sensor.ip_address = "10.0.0.10"
        sensor.metrics["co2"] = 450.0

        response = client.get("/api/v1/sensors")
        assert response.status_code == 200
        assert response.json()["count"] == 9
        assert response.json()["sensors"][0]["ip_address"] is None

        authenticated = client.get("/api/v1/sensors", headers={"X-API-Key": "secret"})
        assert authenticated.json()["sensors"][0]["ip_address"] == "10.0.0.10"
        assert authenticated.json()["sensors"][0]["mac"] == "3c:dc:75:2b:88:44"

        detail = client.get("/api/v1/sensors/air-sensor-01")
        assert detail.status_code == 200
        assert detail.json()["latest"]["co2"] == 450.0
        assert client.get("/api/v1/metrics").json()["metrics"][0]["key"] == "co2"

        latest = client.get("/api/v1/sensors/air-sensor-01/latest")
        assert latest.status_code == 200
        assert latest.json()["co2"] == 450.0
        assert client.get("/api/v1/sensors/missing").status_code == 404
        assert client.get("/api/v1/sensors/air-sensor-02/latest").status_code == 404
        assert client.get("/api/v1/sensors/air-sensor-01/history?metric=bad").status_code == 422
        assert client.get("/api/v1/sensors/air-sensor-01/history?hours=721").status_code == 422
        assert client.get("/api/v1/sensors/air-sensor-01/history?hours=NaN").status_code == 422
        assert client.get("/api/v1/sensors/air-sensor-01/history?hours=inf").status_code == 422
        assert client.get("/api/v1/sensors/air-sensor-01/readings?hours=NaN").status_code == 422
        assert client.get("/api/v1/sensors/air-sensor-01/readings?limit=5001").status_code == 422


def test_stored_history_and_readings(settings_factory):
    settings = settings_factory()
    app = create_app(settings, start_background=False)
    with TestClient(app) as client:
        now = datetime.now(timezone.utc)
        asyncio.run(record_snapshot(settings.database_path, "air-sensor-07", {"co2": 501, "pm25": 8}, now))
        history = client.get("/api/v1/sensors/air-sensor-07/history?metric=co2")
        assert history.status_code == 200
        assert history.json()["data"][0]["value"] == 501.0
        readings = client.get("/api/v1/sensors/air-sensor-07/readings")
        assert readings.status_code == 200
        assert readings.json()["data"][0]["pm2_5"] == 8.0
        latest = client.get("/api/v1/sensors/air-sensor-07/latest")
        assert latest.json()["co2"] == 501.0


def test_required_api_key_and_websocket_auth(settings_factory):
    settings = settings_factory(require_api_key=True, api_key="secret")
    app = create_app(settings, start_background=False)
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/sensors").status_code == 401
        assert client.get("/api/v1/sensors", headers={"X-API-Key": "wrong"}).status_code == 401
        assert client.get("/api/v1/sensors", headers={"X-API-Key": "secret"}).status_code == 200

        with client.websocket_connect("/api/v1/ws") as websocket:
            websocket.send_json({"type": "authenticate", "api_key": "secret"})
            assert websocket.receive_json()["type"] == "initial_state"
            websocket.send_text("ping")
            assert websocket.receive_json()["type"] == "pong"

        with pytest.raises(WebSocketDisconnect) as disconnect:
            with client.websocket_connect("/api/v1/ws") as websocket:
                websocket.send_json({"type": "authenticate", "api_key": "wrong"})
                websocket.receive_json()
        assert disconnect.value.code == 1008


def test_cors_is_restrictive(settings_factory):
    app = create_app(settings_factory(cors_origins=("https://research.example",)), start_background=False)
    with TestClient(app) as client:
        allowed = client.options(
            "/api/v1/sensors",
            headers={
                "Origin": "https://research.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "https://research.example"
        denied = client.options(
            "/api/v1/sensors",
            headers={"Origin": "https://other.example", "Access-Control-Request-Method": "GET"},
        )
        assert denied.status_code == 400


def test_dashboard_assets_are_not_mounted(settings_factory):
    app = create_app(settings_factory(), start_background=False)
    paths = {route.path for route in app.routes}
    assert "/api/sensors" not in paths
    assert "/air/ws" not in paths
    assert not any("static" in path for path in paths)


def test_internal_errors_do_not_expose_exception_text(settings_factory, monkeypatch):
    async def explode(*_args, **_kwargs):
        raise RuntimeError("secret path /tmp/private.db")

    monkeypatch.setattr("main.get_latest_snapshot", explode)
    app = create_app(settings_factory(), start_background=False)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/sensors/air-sensor-01/latest")
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error", "code": "internal_error"}
        assert "private" not in response.text


@pytest.mark.asyncio
async def test_snapshot_loop_uses_snapshot_time(settings_factory, monkeypatch):
    sensor = SimpleNamespace(
        online=True,
        id="air-sensor-01",
        metrics={"co2": 450.0},
    )
    application = SimpleNamespace(
        state=SimpleNamespace(
            settings=settings_factory(),
            pool=SimpleNamespace(all=lambda: [sensor]),
        )
    )
    timestamps = []
    sleep_calls = 0

    async def one_iteration(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise asyncio.CancelledError

    async def capture_snapshot(_path, _sensor_id, _metrics, timestamp=None):
        timestamps.append(timestamp)

    monkeypatch.setattr("main.asyncio.sleep", one_iteration)
    monkeypatch.setattr("main.record_snapshot", capture_snapshot)
    with pytest.raises(asyncio.CancelledError):
        await snapshot_loop(application)
    assert timestamps == [None]
