from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _path_env(name: str, default: Path) -> Path:
    path = Path(os.getenv(name, str(default))).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database_path: Path
    sensor_config_path: Path
    snapshot_interval_seconds: int
    history_retention_days: int
    stale_after_seconds: int
    require_api_key: bool
    api_key: str
    cors_origins: tuple[str, ...]
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        origins = tuple(
            origin.strip()
            for origin in os.getenv("AIR_CORS_ORIGINS", "").split(",")
            if origin.strip()
        )
        settings = cls(
            host=os.getenv("AIR_HOST", "127.0.0.1"),
            port=int(os.getenv("AIR_PORT", "8000")),
            database_path=_path_env("AIR_DATABASE_PATH", BASE_DIR / "air_sensors.db"),
            sensor_config_path=_path_env(
                "AIR_SENSOR_CONFIG_PATH", PROJECT_DIR / "config" / "sensors.json"
            ),
            snapshot_interval_seconds=int(
                os.getenv("AIR_SNAPSHOT_INTERVAL_SECONDS", "30")
            ),
            history_retention_days=int(os.getenv("AIR_HISTORY_RETENTION_DAYS", "30")),
            stale_after_seconds=int(os.getenv("AIR_STALE_AFTER_SECONDS", "180")),
            require_api_key=_bool_env("AIR_REQUIRE_API_KEY"),
            api_key=os.getenv("AIR_API_KEY", ""),
            cors_origins=origins,
            log_level=os.getenv("AIR_LOG_LEVEL", "INFO").upper(),
        )
        if settings.require_api_key and not settings.api_key:
            raise ValueError("AIR_API_KEY must be set when AIR_REQUIRE_API_KEY is true")
        if settings.snapshot_interval_seconds < 1:
            raise ValueError("AIR_SNAPSHOT_INTERVAL_SECONDS must be at least 1")
        if settings.history_retention_days < 1:
            raise ValueError("AIR_HISTORY_RETENTION_DAYS must be at least 1")
        if settings.stale_after_seconds < 1:
            raise ValueError("AIR_STALE_AFTER_SECONDS must be at least 1")
        return settings
