"""Read/write the shared ``pm_overlay.json`` sidecar.

The Excel workbooks are treated as a read-only source of truth. User edits made
inside the app (Due Diligence status changes, custom notes, per-user
preferences) are layered on top and stored in ``pm_overlay.json`` alongside the
Excel files, so they survive a data refresh and are shared across users via
OneDrive/SharePoint sync (last-write-wins).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

OVERLAY_FILENAME = "pm_overlay.json"
OVERLAY_VERSION = "1.0"

# Fields on a DueDiligence row that the overlay is allowed to override.
_DD_FIELDS = (
    "status",
    "completed_date",
    "due_date",
    "assigned_to",
    "approver",
    "approval_date",
    "notes",
)


def _empty_overlay() -> dict:
    return {
        "version": OVERLAY_VERSION,
        "last_modified": None,
        "due_diligence_updates": {},
        "custom_notes": {},
        "user_preferences": {},
    }


class OverlayManager:
    """Manages the ``pm_overlay.json`` file inside the data folder."""

    def __init__(self, data_folder: Path | str):
        self.data_folder = Path(data_folder)
        self.path = self.data_folder / OVERLAY_FILENAME

    # ---------- raw IO ----------
    def load(self) -> dict:
        if not self.path.exists():
            return _empty_overlay()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return _empty_overlay()
        # Merge onto defaults so missing keys are always present.
        overlay = _empty_overlay()
        overlay.update({k: v for k, v in data.items() if v is not None})
        return overlay

    def save(self, overlay: dict) -> dict:
        overlay["version"] = OVERLAY_VERSION
        overlay["last_modified"] = datetime.now(timezone.utc).isoformat()
        self.data_folder.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(overlay, indent=2, default=str), encoding="utf-8")
        return overlay

    # ---------- mutations ----------
    def record_dd_update(self, dd_id: int | str, updates: dict) -> dict:
        overlay = self.load()
        entry = overlay["due_diligence_updates"].get(str(dd_id), {})
        for field in _DD_FIELDS:
            if field in updates and updates[field] is not None:
                value = updates[field]
                entry[field] = value.isoformat() if hasattr(value, "isoformat") else value
        overlay["due_diligence_updates"][str(dd_id)] = entry
        return self.save(overlay)

    def record_note(self, key: str, note: str) -> dict:
        overlay = self.load()
        overlay["custom_notes"][key] = note
        return self.save(overlay)

    def set_preference(self, user: str, prefs: dict) -> dict:
        overlay = self.load()
        overlay["user_preferences"].setdefault(user, {}).update(prefs)
        return self.save(overlay)

    # ---------- apply to DB ----------
    async def apply(self, session: AsyncSession) -> int:
        """Apply overlay DD updates onto the DueDiligence rows in ``session``.

        Returns the number of rows updated. Imported lazily to avoid a hard
        dependency when the DueDiligence model is not in use.
        """
        from datetime import date

        from app.models import DueDiligence

        overlay = self.load()
        dd_updates = overlay.get("due_diligence_updates", {})
        if not dd_updates:
            return 0

        updated = 0
        rows = (await session.scalars(select(DueDiligence))).all()
        by_id = {str(r.id): r for r in rows}
        for dd_id, changes in dd_updates.items():
            row = by_id.get(str(dd_id))
            if row is None:
                continue
            for field in _DD_FIELDS:
                if field not in changes or changes[field] is None:
                    continue
                value = changes[field]
                if field.endswith("_date") and isinstance(value, str):
                    try:
                        value = date.fromisoformat(value)
                    except ValueError:
                        continue
                setattr(row, field, value)
            updated += 1
        if updated:
            await session.commit()
        return updated
