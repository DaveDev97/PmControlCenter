"""AI chat backed by the user's locally-installed Claude Code CLI.

Upgrades over the original:
* Rich financial context (contracts P&L, resource costs, WBS space, booking/OdA)
  built from the in-RAM workbook cache — no extra disk reads.
* Full analyst reasoning rules in the system prompt (CCI calculation, cost space
  per month, forecast hours, recovery plans).
* Persistent chat history in chat_history.json (data folder); rolling 200-turn
  window, archived to chat_history_archive.json.
* GET /api/chat/history  — restore previous session.
* DELETE /api/chat/history — clear history.
* GET /api/chat/briefing  — generate the startup financial briefing (Markdown).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.services.chat_context import build_briefing, build_context_text
from app.services.chat_history import append as history_append
from app.services.chat_history import clear as history_clear
from app.services.chat_history import load as history_load
from app.services.claude_cli import ask_claude, find_claude

router = APIRouter(prefix="/api/chat", tags=["chat"])

_MAX_HISTORY = 12  # turns sent to Claude as conversation context

_SYSTEM = """\
Sei un analista finanziario senior integrato nella dashboard PM Control Center \
di un team di consulenza Accenture. Hai accesso ai dati finanziari aggiornati \
inclusi nel blocco DATI qui sotto.

REGOLE DI CALCOLO — applica sempre:
• Spazio costi disponibile mese M = Revenue_M × 0,65  (CCI target 35%)
• La regola si applica PER MESE e PER WBS: non usare spazio di mesi futuri per coprire mese corrente.
• CCI% = (Revenue - Costi) / Revenue;  target 35%
• Residuo = Revenue × 0,65 − Costi;  se negativo = costi da tagliare o revenue aggiuntive ÷ 0,65 necessarie.
• Importi in formato italiano: 12.345 € (punto migliaia, niente decimali se non necessari).
• Percentuali: 34,8% (virgola decimale).

QUANDO TI CHIEDONO UN FORECAST ORE (per una o più risorse, un mese M):
1. Leggi revenue e spazio costi per WBS per il mese M dal blocco DATI.
2. Calcola spazio totale: WBS già allocato + booking in corso del mese M + OdA confermati del mese M.
3. Per ogni risorsa proposta: Ore × LC€/h ≤ spazio WBS disponibile.
4. Presenta il forecast come tabella: Risorsa | WBS | Ore | Costo imputato.
5. Mostra CCI risultante per scenario A (solo allocato) / B (+booking) / C (+booking+OdA).

QUANDO IL CCI È SOTTO TARGET (< 35%):
1. Calcola il gap in punti percentuali e in euro.
2. Identifica la leva principale: riduzione costi o aumento revenue.
3. Proponi un piano di recovery specifico con ore e WBS concrete.
4. Mostra CCI risultante dopo il piano.
5. Avvisa se il recovery non è raggiungibile nel mese corrente.

FORMATO RISPOSTE:
• Prima riga delle risposte numeriche: "Dati aggiornati al: GG/MM/AAAA"
• Usa tabelle Markdown (| col | col |) per dati numerici.
• Usa • per gli elenchi (non trattini).
• Distingui dati certi (actual) da stimati (forecast/booking/OdA).
• Non inventare numeri. Se un dato manca, dillo esplicitamente.
• Rispondi nella lingua dell'utente (italiano se non diversamente indicato).
"""


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurn] = []


@router.get("/status")
async def chat_status():
    exe = find_claude()
    return {
        "available": exe is not None,
        "path": str(exe) if exe else None,
        "model": settings.chat_model or "default",
    }


@router.get("/history")
async def get_history():
    turns = history_load(settings.data_folder)
    from datetime import date
    return {"turns": turns, "data_as_of": date.today().isoformat()}


@router.delete("/history")
async def delete_history():
    history_clear(settings.data_folder)
    return {"ok": True}


@router.get("/briefing")
async def get_briefing():
    from datetime import date
    briefing = build_briefing()
    return {"briefing": briefing, "data_as_of": date.today().isoformat()}


@router.post("")
async def chat(req: ChatRequest, session: AsyncSession = Depends(get_session)):
    if not req.message.strip():
        return {"reply": "Scrivi una domanda.", "available": find_claude() is not None}

    # Build full system prompt with live financial data
    context = build_context_text()
    system = _SYSTEM + "\n\n" + context

    # Conversation history (persisted + in-request)
    saved = history_load(settings.data_folder)
    all_history = saved + [{"role": t.role, "content": t.content} for t in req.history]
    recent = all_history[-_MAX_HISTORY:]
    history_block = "".join(
        f"{'UTENTE' if t['role'] == 'user' else 'ASSISTENTE'}: {t['content']}\n"
        for t in recent
    )

    prompt = "\n".join(filter(None, [
        system,
        f"CONVERSAZIONE PRECEDENTE:\n{history_block}" if history_block else "",
        f"DOMANDA UTENTE:\n{req.message}",
    ]))

    result = await ask_claude(prompt, settings.chat_model or None, timeout=180)
    if not result.ok:
        return {"reply": f"⚠️ {result.error}", "available": find_claude() is not None,
                "error": True}

    # Persist both turns
    history_append(settings.data_folder, "user", req.message)
    history_append(settings.data_folder, "assistant", result.text)

    return {"reply": result.text, "available": True, "model": settings.chat_model or "default"}
