"""AI chat backed by the user's locally-installed Claude Code CLI.

Instead of calling a hosted API (which would need keys/network), we shell out to
the ``claude`` command already installed and authenticated on the user's PC:

    claude -p --model <model>            # prompt is fed on stdin

A compact snapshot of the currently-loaded data (contracts, resources,
opportunities) is prepended as context so the assistant can answer questions
about the Control Center, not just generic ones.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.config import settings
from app.core.database import get_session
from app.models import Allocation, Contract, Opportunity, Resource

router = APIRouter(prefix="/api/chat", tags=["chat"])

_SYSTEM = (
    "Sei l'assistente AI di 'PM Control Center', un'app di gestione contratti, "
    "risorse e opportunità. Rispondi in modo conciso e professionale, nella lingua "
    "dell'utente. Usa i DATI forniti qui sotto per rispondere a domande su margini, "
    "chargeability, risorse disponibili, pipeline e opportunità. Se un dato non è "
    "presente, dillo. Non inventare numeri.\n\n"
)


class ChatRequest(BaseModel):
    message: str


def _claude_cmd(model: str) -> list[str] | None:
    exe = shutil.which("claude")
    if not exe:
        return None
    args = [exe, "-p"]
    if model:
        args += ["--model", model]
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        args = ["cmd", "/c", *args]
    return args


async def _data_context(session: AsyncSession) -> str:
    contracts = (await session.scalars(select(Contract))).all()
    resources = (await session.scalars(select(Resource))).all()
    opps = (await session.scalars(select(Opportunity))).all()
    allocs = (await session.scalars(select(Allocation))).all()
    util_by_res: dict[int, float] = {}
    for a in allocs:
        util_by_res[a.resource_id] = util_by_res.get(a.resource_id, 0.0) + (a.utilization or 0.0)
    snapshot = {
        "contracts": [{"id": c.id, "name": c.name, "status": c.status} for c in contracts],
        "resources": [
            {"name": r.name, "chargeability": r.chargeability,
             "allocated": round(util_by_res.get(r.id, 0.0), 2)}
            for r in resources
        ],
        "opportunities": [
            {"name": o.name, "stage": o.stage, "value": o.estimated_value}
            for o in opps[:60]
        ],
    }
    return "DATI (JSON):\n" + json.dumps(snapshot, ensure_ascii=False)


@router.get("/status")
async def chat_status():
    exe = shutil.which("claude")
    return {
        "available": exe is not None,
        "path": exe,
        "model": settings.chat_model or "default",
    }


@router.post("")
async def chat(req: ChatRequest, session: AsyncSession = Depends(get_session)):
    cmd = _claude_cmd(settings.chat_model)
    if cmd is None:
        return {
            "reply": "⚠️ Claude Code non è installato (o non è nel PATH) su questo PC. "
            "Installa Claude Code e riavvia l'app per usare la chat.",
            "available": False,
        }
    prompt = _SYSTEM + await _data_context(session) + "\n\nDOMANDA:\n" + req.message
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=180,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        return {"reply": "⏱️ La richiesta a Claude Code è andata in timeout. Riprova.", "available": True}
    except OSError as exc:
        return {"reply": f"Errore nell'avvio di Claude Code: {exc}", "available": True}

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:500]
        return {"reply": f"Claude Code ha restituito un errore:\n{detail}", "available": True}
    return {"reply": proc.stdout.strip() or "(nessuna risposta)", "available": True,
            "model": settings.chat_model or "default"}
