"""Settings & data-management API.

Powers the Setup Wizard and the Settings page:

* ``POST /api/settings/configure`` — validate a data folder, persist it, load data
* ``GET  /api/settings``           — current settings + sync status
* ``PUT  /api/settings``           — update language/theme/auto-refresh/data folder
* ``POST /api/data/refresh``       — re-read the Excel files + overlay
* ``GET  /api/data/status``        — whether data is configured/loaded
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Contract
from app.services.data_sync import reload_data
from app.services.excel_reader import ExcelDataLoader

router = APIRouter(prefix="/api", tags=["settings"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class ConfigureRequest(BaseModel):
    data_folder: str


class SettingsUpdate(BaseModel):
    data_folder: str | None = None
    language: str | None = None
    theme: str | None = None
    auto_refresh_minutes: int | None = None


class SettingsOut(BaseModel):
    app_name: str
    data_folder: str | None
    last_sync: datetime | None
    language: str
    theme: str
    auto_refresh_minutes: int
    configured: bool


def _settings_out() -> SettingsOut:
    return SettingsOut(
        app_name=settings.app_name,
        data_folder=str(settings.data_folder) if settings.data_folder else None,
        last_sync=settings.last_sync,
        language=settings.language,
        theme=settings.theme,
        auto_refresh_minutes=settings.auto_refresh_minutes,
        configured=settings.data_folder is not None,
    )


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.post("/settings/configure")
async def configure_data_folder(request: ConfigureRequest):
    """Setup Wizard: validate the folder, save it, and load the data."""
    folder = Path(request.data_folder).expanduser()
    validation = ExcelDataLoader().validate_folder(folder)
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Required Excel files not found in the selected folder.",
                **validation,
            },
        )
    try:
        result = await reload_data(folder)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, **result, "settings": _settings_out()}


@router.get("/settings/validate")
async def validate_folder(path: str):
    """Check a candidate folder without loading (used live in the wizard)."""
    return ExcelDataLoader().validate_folder(Path(path).expanduser())


@router.get("/settings", response_model=SettingsOut)
async def get_settings():
    return _settings_out()


@router.put("/settings", response_model=SettingsOut)
async def update_settings(updates: SettingsUpdate):
    """Update settings. Changing the data folder triggers a reload."""
    payload = updates.model_dump(exclude_unset=True)
    folder_changed = "data_folder" in payload and payload["data_folder"]

    if folder_changed:
        folder = Path(payload["data_folder"]).expanduser()
        validation = ExcelDataLoader().validate_folder(folder)
        if not validation["valid"]:
            raise HTTPException(status_code=400, detail={"message": "Invalid folder", **validation})
        try:
            await reload_data(folder)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload.pop("data_folder")  # already persisted by reload_data

    if payload:
        settings.update(**payload)
    return _settings_out()


@router.post("/data/refresh")
async def refresh_data():
    """Reload the Excel files and re-apply the overlay."""
    if settings.data_folder is None:
        raise HTTPException(status_code=400, detail="No data folder configured")
    try:
        result = await reload_data()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, **result}


@router.get("/data/status")
async def data_status():
    """Report whether the data folder is configured and how many rows are loaded."""
    configured = settings.data_folder is not None
    contract_count = 0
    if configured:
        async with SessionLocal() as session:
            contract_count = await session.scalar(select(func.count()).select_from(Contract)) or 0
    return {
        "configured": configured,
        "loaded": contract_count > 0,
        "contracts": contract_count,
        "last_sync": settings.last_sync.isoformat() if settings.last_sync else None,
        "data_folder": str(settings.data_folder) if settings.data_folder else None,
    }
