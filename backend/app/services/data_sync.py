"""Orchestrates rebuilding the in-memory data from the Excel workbook.

Used on application startup, by ``POST /api/data/refresh`` and by the
background watcher when the file is changed by someone else. The sequence is
always: read the workbook once into RAM -> reset tables -> load from the
snapshot -> apply overlay.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.database import SessionLocal, reset_db
from app.services import workbook_cache
from app.services.excel_reader import ExcelDataLoader
from app.services.overlay_manager import OverlayManager

WATCH_INTERVAL_SECONDS = 10


async def reload_data(data_folder: Path | str | None = None) -> dict:
    """Rebuild the database from the Excel workbook in ``data_folder``.

    Falls back to ``settings.data_folder`` when no folder is given. Returns a
    result dict with per-entity ``counts``, ``overlay_applied`` and ``last_sync``.
    Raises ``FileNotFoundError`` / ``ValueError`` if the source is invalid.
    """
    async with workbook_cache.data_lock:
        return await _reload_locked(data_folder)


async def _reload_locked(data_folder: Path | str | None) -> dict:
    folder = Path(data_folder) if data_folder else settings.data_folder
    if folder is None:
        raise ValueError("No data folder configured")

    loader = ExcelDataLoader()
    wb_path = loader.resolve_workbook(folder)
    if wb_path is None:
        raise FileNotFoundError(f"Nessun file Excel trovato: {folder}")
    try:
        # The only disk read: every sheet, off the event loop.
        snap = await asyncio.to_thread(workbook_cache.read_workbook, wb_path)
    except Exception as exc:  # noqa: BLE001 - locked/being synced/corrupt
        raise FileNotFoundError(f"Impossibile aprire {wb_path}: {exc}") from exc
    if not loader.looks_like_workbook(snap.sheetnames):
        raise FileNotFoundError(
            f"{wb_path.name} non sembra un workbook PM Control Center "
            "(mancano i fogli Contracts / Opp. / Forecast)."
        )

    await reset_db()
    async with SessionLocal() as session:
        counts = await loader.load_all(folder, session, snap)
        overlay_applied = await OverlayManager(folder).apply(session)
    workbook_cache.set_snapshot(snap)

    now = datetime.now()
    settings.update(data_folder=folder, last_sync=now)
    return {
        "counts": counts,
        "overlay_applied": overlay_applied,
        "last_sync": now.isoformat(),
        "data_folder": str(folder),
    }


async def watch_workbook(interval: float = WATCH_INTERVAL_SECONDS) -> None:
    """Reload when the workbook is changed by someone else (Excel, OneDrive sync).

    Only the file's mtime/size is checked each tick. A change must be stable
    for two consecutive ticks before reloading, so a file still being written
    or synced is not read half-way. The app's own writes update the recorded
    signature and never trigger a reload.
    """
    pending: tuple[float, int] | None = None
    while True:
        await asyncio.sleep(interval)
        snap = workbook_cache.snapshot()
        if snap is None or workbook_cache.data_lock.locked() or not workbook_cache.changed_on_disk():
            pending = None
            continue
        try:
            sig = workbook_cache.file_signature(snap.path)
        except OSError:
            continue
        if sig != pending:
            pending = sig  # first sighting: wait one more tick
            continue
        pending = None
        try:
            result = await reload_data()
            print(f"[watcher] workbook changed on disk, reloaded: {result['counts']}")
        except (FileNotFoundError, ValueError) as exc:
            print(f"[watcher] reload postponed: {exc}")
