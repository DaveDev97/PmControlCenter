"""Persistent chat history stored in the configured data folder.

Rolling window of MAX_ACTIVE turns kept in ``chat_history.json``; older
turns are appended to ``chat_history_archive.json`` so they are never lost.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

MAX_ACTIVE = 200


def _path(data_folder: str) -> Path:
    return Path(data_folder) / "chat_history.json"


def _archive_path(data_folder: str) -> Path:
    return Path(data_folder) / "chat_history_archive.json"


def load(data_folder: str | None) -> list[dict]:
    if not data_folder:
        return []
    try:
        return json.loads(_path(data_folder).read_text("utf-8"))
    except Exception:
        return []


def save(data_folder: str | None, turns: list[dict]) -> None:
    if not data_folder:
        return
    if len(turns) > MAX_ACTIVE:
        excess = turns[:-MAX_ACTIVE]
        ap = _archive_path(data_folder)
        try:
            old: list = json.loads(ap.read_text("utf-8")) if ap.exists() else []
        except Exception:
            old = []
        ap.write_text(json.dumps(old + excess, ensure_ascii=False, indent=2), "utf-8")
        turns = turns[-MAX_ACTIVE:]
    _path(data_folder).write_text(json.dumps(turns, ensure_ascii=False, indent=2), "utf-8")


def clear(data_folder: str | None) -> None:
    if not data_folder:
        return
    p = _path(data_folder)
    if p.exists():
        p.unlink()


def append(data_folder: str | None, role: str, content: str) -> list[dict]:
    turns = load(data_folder)
    turns.append({"role": role, "content": content,
                  "timestamp": datetime.now(timezone.utc).isoformat()})
    save(data_folder, turns)
    return turns
