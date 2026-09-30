"""On-demand, cached access to the raw cell values of selected workbook sheets.

Some views (CCI from ``Contracts`` / ``Sheet1``, WBS cost-space rows from
``Costi vs Forecast``) read the formula-computed sheets as they are, instead of
the normalised database. Reading the workbook costs about a second, so values
are cached per (path, modification time) and re-read only when the file changes.
"""
from __future__ import annotations

from pathlib import Path
from threading import Lock

import openpyxl

from app.core.config import settings
from app.services.excel_reader import ExcelDataLoader

_cache: dict[tuple[str, float], dict[str, list[list]]] = {}
_lock = Lock()


def current_workbook() -> Path | None:
    """Path of the configured workbook, or None when not configured."""
    if settings.data_folder is None:
        return None
    return ExcelDataLoader.resolve_workbook(settings.data_folder)


def sheet_values(path: Path) -> dict[str, list[list]]:
    """Return {sheet title: rows of values} for ``path`` (row/col 1 = index 0)."""
    key = (str(path), path.stat().st_mtime)
    with _lock:
        if key in _cache:
            return _cache[key]
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            data = {
                ws.title: [list(r) for r in ws.iter_rows(min_row=1, min_col=1, values_only=True)]
                for ws in wb.worksheets
            }
        finally:
            wb.close()
        _cache.clear()
        _cache[key] = data
        return data


def find_sheet(sheets: dict[str, list[list]], *predicates) -> list[list] | None:
    """First sheet whose lower-cased title satisfies a predicate (in priority order)."""
    for pred in predicates:
        for title, rows in sheets.items():
            if pred(title.lower().strip()):
                return rows
    return None
