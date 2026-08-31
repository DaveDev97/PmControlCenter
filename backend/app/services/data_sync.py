"""Orchestrates rebuilding the in-memory database from the Excel source files.

Used both on application startup and by the ``POST /api/data/refresh`` endpoint.
The sequence is always: reset tables -> load Excel -> apply overlay.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.database import SessionLocal, reset_db
from app.services.excel_reader import ExcelDataLoader
from app.services.overlay_manager import OverlayManager


async def reload_data(data_folder: Path | str | None = None) -> dict:
    """Rebuild the database from the Excel files in ``data_folder``.

    Falls back to ``settings.data_folder`` when no folder is given. Returns a
    result dict with per-entity ``counts``, ``overlay_applied`` and ``last_sync``.
    Raises ``FileNotFoundError`` / ``ValueError`` if the folder is invalid.
    """
    folder = Path(data_folder) if data_folder else settings.data_folder
    if folder is None:
        raise ValueError("No data folder configured")

    loader = ExcelDataLoader()
    validation = loader.validate_folder(folder)
    if not validation["valid"]:
        raise FileNotFoundError(
            f"Missing required files in {folder}: {', '.join(validation['missing'])}"
        )

    await reset_db()
    async with SessionLocal() as session:
        counts = await loader.load_all(folder, session)
        overlay_applied = await OverlayManager(folder).apply(session)

    now = datetime.now()
    settings.update(data_folder=folder, last_sync=now)
    return {
        "counts": counts,
        "overlay_applied": overlay_applied,
        "last_sync": now.isoformat(),
        "data_folder": str(folder),
    }
