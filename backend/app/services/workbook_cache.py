"""In-memory snapshot of the workbook: read once, served from RAM.

The workbook is read from disk exactly once per load (startup, manual refresh,
or an external change detected by the watcher): every sheet's cell values are
kept here and are the single source for the database loader, the CCI view,
the "Costi vs Forecast" views and for locating rows during write-back.

The app's own writes patch the snapshot in place and record the new file
signature (mtime + size), so they never trigger a re-read. Only a change made
by someone else (Excel, OneDrive sync) makes the file differ from the recorded
signature; the watcher then reloads everything.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

from app.core.config import settings

# Serialises reloads and write-backs so they never interleave.
data_lock = asyncio.Lock()


@dataclass
class WorkbookSnapshot:
    path: Path
    signature: tuple[float, int]  # (mtime, size) of the file that was read
    sheets: dict[str, list[list]] = field(default_factory=dict)  # title -> rows (row/col 1 = index 0)
    # Formulas of the sheets listed in FORMULA_SHEETS (same shape as ``sheets``).
    formulas: dict[str, list[list]] = field(default_factory=dict)

    @property
    def sheetnames(self) -> list[str]:
        return list(self.sheets)

    def __getitem__(self, title: str) -> "_SheetView":
        return _SheetView(self.sheets[title])

    def close(self) -> None:  # openpyxl-compatible no-op
        pass


class _SheetView:
    """Minimal openpyxl-like view so the loader can iterate cached rows."""

    def __init__(self, rows: list[list]):
        self._rows = rows

    def iter_rows(self, min_row: int = 1, min_col: int = 1, values_only: bool = True, **_):
        for row in self._rows[min_row - 1:]:
            yield tuple(row[min_col - 1:])


_snapshot: WorkbookSnapshot | None = None

# Sheets whose formulas are also kept: the hours formulas of "Costi vs Forecast"
# tell the share of time on the account ("*0.5") apart from absences ("-32").
FORMULA_SHEETS = ("costi vs forecast",)


def file_signature(path: Path) -> tuple[float, int]:
    st = path.stat()
    return (st.st_mtime, st.st_size)


def read_workbook(path: Path) -> WorkbookSnapshot:
    """Read every sheet of ``path`` from disk (the only place that does)."""
    sig = file_signature(path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheets = {
            ws.title: [list(r) for r in ws.iter_rows(min_row=1, min_col=1, values_only=True)]
            for ws in wb.worksheets
        }
    finally:
        wb.close()  # read_only keeps the file handle open until closed
    formulas: dict[str, list[list]] = {}
    wanted = [t for t in sheets if t.lower().strip() in FORMULA_SHEETS]
    if wanted:
        wf = openpyxl.load_workbook(path, read_only=True, data_only=False)
        try:
            for title in wanted:
                formulas[title] = [list(r) for r in wf[title].iter_rows(min_row=1, min_col=1, values_only=True)]
        finally:
            wf.close()
    return WorkbookSnapshot(path=path, signature=sig, sheets=sheets, formulas=formulas)


def set_snapshot(snap: WorkbookSnapshot | None) -> None:
    global _snapshot
    _snapshot = snap


def snapshot() -> WorkbookSnapshot | None:
    return _snapshot


def cached_formulas() -> dict[str, list[list]]:
    return _snapshot.formulas if _snapshot else {}


def cached_sheets() -> dict[str, list[list]]:
    """Sheets of the loaded workbook ({} when nothing is loaded). Never touches the disk."""
    return _snapshot.sheets if _snapshot else {}


def current_workbook() -> Path | None:
    """Path of the loaded workbook (falls back to the configured one)."""
    if _snapshot is not None:
        return _snapshot.path
    if settings.data_folder is None:
        return None
    from app.services.excel_reader import ExcelDataLoader

    return ExcelDataLoader.resolve_workbook(settings.data_folder)


def changed_on_disk() -> bool:
    """True when the file differs from what is in memory (someone else changed it)."""
    if _snapshot is None:
        return False
    try:
        return file_signature(_snapshot.path) != _snapshot.signature
    except OSError:
        return False  # temporarily unavailable (e.g. OneDrive replacing it)


def apply_own_write(sheet: str, cells: dict[tuple[int, int], object]) -> None:
    """Patch the snapshot after the app wrote ``cells`` ({(row, col): value}, 1-based)."""
    if _snapshot is None:
        return
    rows = _snapshot.sheets.get(sheet)
    if rows is not None:
        for (r, c), value in cells.items():
            while len(rows) < r:
                rows.append([])
            row = rows[r - 1]
            if len(row) < c:
                row.extend([None] * (c - len(row)))
            row[c - 1] = value
    _snapshot.signature = file_signature(_snapshot.path)


def find_sheet(sheets: dict[str, list[list]], *predicates) -> list[list] | None:
    """First sheet whose lower-cased title satisfies a predicate (in priority order)."""
    for pred in predicates:
        for title, rows in sheets.items():
            if pred(title.lower().strip()):
                return rows
    return None
