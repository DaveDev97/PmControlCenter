"""Application configuration + persistent user settings manager.

Two concerns live here:

1. Static application constants (KPI thresholds, working days) consumed by the
   calculation services. These never change at runtime.
2. User-configurable runtime settings (data folder, language, theme,
   auto-refresh) persisted as JSON in the per-user application data directory
   (``%APPDATA%/PMControlCenter/settings.json`` on Windows).

The module exposes a single mutable ``settings`` singleton. API handlers mutate
its attributes and call ``settings.save()``; every other module imports the same
object, so reads always observe the latest values.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def app_data_dir() -> Path:
    """Return the per-user application data directory, creating it if needed."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    directory = Path(base) / "PMControlCenter"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


APP_DATA_DIR = app_data_dir()
SETTINGS_FILE = APP_DATA_DIR / "settings.json"
LOG_DIR = APP_DATA_DIR / "logs"

# Fields persisted to (and reloaded from) settings.json.
_PERSISTED_FIELDS = ("data_folder", "last_sync", "language", "theme", "auto_refresh_minutes")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PMAPP_", env_file=".env", extra="ignore")

    app_name: str = "PM Control Center"

    # --- Runtime data layer ---
    # Shared in-memory SQLite: data is rebuilt from Excel on every launch/refresh.
    database_url: str = "sqlite+aiosqlite://"

    # --- User-configurable settings (persisted to settings.json) ---
    data_folder: Path | None = None
    last_sync: datetime | None = None
    language: str = "it"  # it | en
    theme: str = "light"  # light | dark | auto
    auto_refresh_minutes: int = 0  # 0 = disabled

    # --- Static application constants (KPI logic) ---
    working_days_per_month: float = 20.0
    # CI% (CCI) thresholds per documento operativo: target 35%
    # Verde >=35%, Giallo 30-35%, Rosso <30%
    cci_target_threshold: float = 0.35  # Target CCI
    cci_warning_threshold: float = 0.30  # below this = red
    ci_warning_threshold: float = 0.30  # legacy compatibility
    util_bench_threshold: float = 0.50
    util_full_threshold: float = 0.80

    # CORS origins (Vite dev server + Electron file://).
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "*"]

    # ---------- persistence ----------
    def save(self) -> None:
        """Persist the user-configurable subset to settings.json."""
        payload: dict = {}
        for field in _PERSISTED_FIELDS:
            value = getattr(self, field)
            if isinstance(value, Path):
                value = str(value)
            elif isinstance(value, datetime):
                value = value.isoformat()
            payload[field] = value
        SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        """Build a Settings instance, overlaying values saved in settings.json."""
        instance = cls()
        if SETTINGS_FILE.exists():
            try:
                saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                saved = {}
            for field in _PERSISTED_FIELDS:
                if field not in saved or saved[field] is None:
                    continue
                raw = saved[field]
                if field == "data_folder":
                    setattr(instance, field, Path(raw))
                elif field == "last_sync":
                    try:
                        setattr(instance, field, datetime.fromisoformat(raw))
                    except (TypeError, ValueError):
                        pass
                else:
                    setattr(instance, field, raw)
        return instance

    def update(self, **changes) -> "Settings":
        """Apply and persist a set of field changes (ignoring None values)."""
        for key, value in changes.items():
            if value is None:
                continue
            if key == "data_folder":
                value = Path(value)
            setattr(self, key, value)
        self.save()
        return self


settings = Settings.load()
