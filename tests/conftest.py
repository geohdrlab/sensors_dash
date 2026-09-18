from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config import Settings


@pytest.fixture
def sensor_config_path() -> Path:
    return ROOT / "config" / "sensors.json"


@pytest.fixture
def settings_factory(tmp_path: Path, sensor_config_path: Path):
    def make(**overrides):
        values = {
            "host": "127.0.0.1",
            "port": 8000,
            "database_path": tmp_path / "test.db",
            "sensor_config_path": sensor_config_path,
            "snapshot_interval_seconds": 30,
            "history_retention_days": 30,
            "stale_after_seconds": 180,
            "require_api_key": False,
            "api_key": "",
            "cors_origins": (),
            "log_level": "WARNING",
        }
        values.update(overrides)
        return Settings(**values)
    return make
