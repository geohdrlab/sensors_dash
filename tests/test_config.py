from __future__ import annotations

import pytest

from config import PROJECT_DIR, Settings


def test_required_key_fails_closed(monkeypatch):
    monkeypatch.setenv("AIR_REQUIRE_API_KEY", "true")
    monkeypatch.delenv("AIR_API_KEY", raising=False)
    with pytest.raises(ValueError, match="AIR_API_KEY"):
        Settings.from_env()


def test_relative_paths_resolve_from_project_root(monkeypatch):
    monkeypatch.setenv("AIR_DATABASE_PATH", "data/readings.db")
    monkeypatch.setenv("AIR_SENSOR_CONFIG_PATH", "config/sensors.json")
    monkeypatch.setenv("AIR_REQUIRE_API_KEY", "false")
    settings = Settings.from_env()
    assert settings.database_path == PROJECT_DIR / "data/readings.db"
    assert settings.sensor_config_path == PROJECT_DIR / "config/sensors.json"
