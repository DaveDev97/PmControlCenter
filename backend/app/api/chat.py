"""AI chat backed by the user's locally-installed Claude Code CLI.

Instead of calling a hosted API (which would need keys/network), prompts go to
the ``claude`` executable already installed and authenticated on the user's PC
(see :mod:`app.services.claude_cli` for how it is located and run).

A compact snapshot of the currently-loaded data (contracts, resources,
opportunities, BD, CCI) is prepended as context so the assistant can answer
questions about the Control Center, not just generic ones. The last turns of
the conversation are included so follow-up questions work.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_session
from app.models import Contract, Opportunity, Resource
from app.services.claude_cli import ask_claude, find_claude
from app.services.excel_reader import fy_label

router = APIRouter(prefix="/api/chat", tags=["chat"])

_SYSTEM = (
    "Sei l'assistente AI di 'PM Control Center', un'app di gestione contratti, "
    "risorse e opportunità. Rispondi in modo conciso e professionale, nella lingua "
    "dell'utente. Usa i DATI forniti qui sotto per rispondere a domande su margini (CCI, "
    "target 35%), chargeability (%Charg), risorse, pipeline, opportunità e BD. Se un dato "
    "non è presente, dillo. Non inventare numeri. Non usare strumenti: rispondi solo con testo "
    "semplice, senza Markdown (niente **, #, tabelle); per gli elenchi usa righe che iniziano con '• '.\n\n"
)
_MAX_HISTORY = 8


class ChatTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = []


async def _data_context(session: AsyncSession) -> str:
    contracts = (await session.scalars(select(Contract).options(selectinload(Contract.client)))).all()
    resources = (await session.scalars(select(Resource))).all()
    opps = (await session.scalars(select(Opportunity))).all()
    snapshot = {
        "contracts": [{"id": c.id, "name": c.name, "client": c.client.name if c.client else None,
                       "wbs": c.wbs_l1} for c in contracts],
        "resources": [{"name": r.name, "perc_charg": r.perc_charg, "lc_hourly": r.loaded_cost_hourly}
                      for r in resources],
        "opportunities": [
            {"name": o.name, "fy": fy_label(o.fiscal_year), "mms_status": o.mms_status,
             "acn_tool": o.acn_tool_status, "quarter": o.quarter, "value": o.estimated_value,
             "billed": o.total_invoiced, "to_be_billed": o.total_to_invoice}
            for o in opps
        ],
    }
    return "DATI (JSON):\n" + json.dumps(snapshot, ensure_ascii=False, default=str)


@router.get("/status")
async def chat_status():
    exe = find_claude()
    return {
        "available": exe is not None,
        "path": str(exe) if exe else None,
        "model": settings.chat_model or "default",
    }


@router.post("")
async def chat(req: ChatRequest, session: AsyncSession = Depends(get_session)):
    if not req.message.strip():
        return {"reply": "Scrivi una domanda.", "available": find_claude() is not None}
    history = "".join(
        f"{'UTENTE' if t.role == 'user' else 'ASSISTENTE'}: {t.content}\n"
        for t in req.history[-_MAX_HISTORY:]
    )
    prompt = (
        _SYSTEM + await _data_context(session)
        + (f"\n\nCONVERSAZIONE PRECEDENTE:\n{history}" if history else "")
        + "\n\nDOMANDA:\n" + req.message
    )
    result = await ask_claude(prompt, settings.chat_model or None, timeout=180)
    if not result.ok:
        return {"reply": f"⚠️ {result.error}", "available": find_claude() is not None, "error": True}
    return {"reply": result.text, "available": True, "model": settings.chat_model or "default"}
