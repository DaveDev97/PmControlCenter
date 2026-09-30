"""Run prompts through the user's locally-installed Claude Code CLI.

No API keys: the ``claude`` binary already installed and logged in on the PC is
used in print mode (``claude -p``, prompt on stdin). It is found, in order:

1. the path set in Settings (``claude_path``);
2. ``claude`` on PATH;
3. standard install locations (native installer, npm global);
4. the binary bundled with the Claude Code extension for VS Code / Cursor,
   which is often the only copy on corporate PCs.

Calls run in a worker thread so a slow answer never blocks the backend, with
UTF-8 I/O (the Windows default code page mangles accents and symbols).
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings

_EXE = "claude.exe" if os.name == "nt" else "claude"


def _extension_binaries() -> list[Path]:
    home = Path.home()
    found: list[Path] = []
    for editor in (".vscode", ".vscode-insiders", ".cursor", ".windsurf"):
        ext_dir = home / editor / "extensions"
        if not ext_dir.is_dir():
            continue
        for ext in sorted(ext_dir.glob("anthropic.claude-code-*"), reverse=True):  # newest first
            cand = ext / "resources" / "native-binary" / _EXE
            if cand.is_file():
                found.append(cand)
    return found


def find_claude() -> Path | None:
    """Locate the Claude Code executable (see module docstring for the order)."""
    configured = (getattr(settings, "claude_path", "") or "").strip()
    if configured and Path(configured).is_file():
        return Path(configured)
    on_path = shutil.which("claude")
    if on_path:
        return Path(on_path)
    home = Path.home()
    candidates = [
        home / ".local" / "bin" / _EXE,
        home / ".claude" / "local" / _EXE,
        Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")) / "npm" / "claude.cmd",
        Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "Programs" / "claude" / _EXE,
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    ext = _extension_binaries()
    return ext[0] if ext else None


@dataclass
class ClaudeResult:
    ok: bool
    text: str = ""
    error: str = ""


def _command(exe: Path, model: str | None) -> list[str]:
    args = [str(exe), "-p"]
    if model:
        args += ["--model", model]
    if os.name == "nt" and exe.suffix.lower() in (".cmd", ".bat"):
        args = ["cmd", "/c", *args]
    return args


def _run(prompt: str, model: str | None, timeout: int) -> ClaudeResult:
    exe = find_claude()
    if exe is None:
        return ClaudeResult(False, error=(
            "Claude Code non trovato su questo PC. Installa Claude Code (o l'estensione per "
            "VS Code) ed effettua il login, oppure indica il percorso di claude.exe nelle Impostazioni."
        ))
    try:
        proc = subprocess.run(
            _command(exe, model),
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        return ClaudeResult(False, error=f"Claude non ha risposto entro {timeout} secondi. Riprova.")
    except OSError as exc:
        return ClaudeResult(False, error=f"Impossibile avviare Claude Code ({exe}): {exc}")
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        detail = ((proc.stderr or "") + "\n" + out).strip()[:600]
        if "login" in detail.lower() or "auth" in detail.lower():
            detail += "\n\nApri Claude Code ed effettua il login, poi riprova."
        return ClaudeResult(False, error=f"Claude Code ha restituito un errore:\n{detail}")
    if not out:
        return ClaudeResult(False, error="Claude Code non ha restituito alcuna risposta.")
    return ClaudeResult(True, text=out)


async def ask_claude(prompt: str, model: str | None = None, timeout: int = 180) -> ClaudeResult:
    """Send ``prompt`` to Claude Code without blocking the event loop."""
    return await asyncio.to_thread(_run, prompt, model, timeout)
