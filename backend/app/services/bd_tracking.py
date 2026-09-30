"""BD Tracking: BD budget lines joined to their opportunity.

Join key: ``BD.OppID`` <-> ``Opp ID MMS`` of the three Opp sheets (normalised,
so '0012158442' and 12158442 match). The BD state is derived from the MMS Status
of the linked opportunity:

=================  ============================
MMS Status         Stato BD
=================  ============================
CloseWon           Chiuso (budget no longer usable)
0 / 1              Attivo
3B                 Attivo, da monitorare
blank / other      Sconosciuto
not found          Sconosciuto
=================  ============================

When the OppID does not match, an opportunity with the identical name is used
as a fallback and the row is flagged (``linked_by = "nome"``).

``Delta`` is taken from the sheet as the residual budget; it is never recomputed.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BDItem, Opportunity
from app.services.excel_reader import fy_label, norm_opp_id


def bd_state(opp: Opportunity | None) -> tuple[str, str]:
    """Return (stato, motivo) for a BD line given its linked opportunity."""
    if opp is None:
        return "Sconosciuto", "Opportunità non trovata nei fogli Opp."
    mms = (opp.mms_status or "").strip()
    low = mms.lower()
    if low == "closewon":
        return "Chiuso", "Opportunità CloseWon"
    if low == "3b":
        return "Attivo", "Stage 3B: da monitorare"
    if low in ("0", "1"):
        return "Attivo", f"Stage {mms}"
    if not mms:
        return "Sconosciuto", "MMS Status vuoto"
    return "Sconosciuto", f"MMS Status '{mms}' non gestito"


async def bd_overview(session: AsyncSession) -> dict:
    items = (await session.scalars(select(BDItem).order_by(BDItem.source_row))).all()
    opps = (await session.scalars(select(Opportunity))).all()
    # If the same opp appears in more than one FY sheet, the most recent FY wins.
    index: dict[str, Opportunity] = {}
    by_name: dict[str, Opportunity] = {}
    for o in sorted(opps, key=lambda o: o.fiscal_year or ""):
        key = norm_opp_id(o.opp_id_mms)
        if key:
            index[key] = o
        if o.name:
            by_name[o.name.strip().lower()] = o

    rows = []
    summary = {s: {"count": 0, "totale": 0.0, "consumato": 0.0, "residuo": 0.0}
               for s in ("Attivo", "Chiuso", "Sconosciuto")}
    for b in items:
        opp = index.get(b.opp_id) if b.opp_id else None
        linked_by = "oppid" if opp else None
        if opp is None and b.opp_name:
            # Fallback: identical opportunity name (OppID missing or mistyped in BD).
            opp = by_name.get(b.opp_name.strip().lower())
            linked_by = "nome" if opp else None
        stato, motivo = bd_state(opp)
        if linked_by == "nome":
            motivo += " (collegata per nome: OppID non corrispondente)"
        wbs_lines = [ln.strip() for ln in (b.wbs_bd or "").splitlines() if ln.strip()]
        stop = any("stop" in ln.lower() for ln in wbs_lines[1:])
        perc = b.perc_utilizzo
        if perc is None and b.totale:
            perc = b.consumato / b.totale
        rows.append({
            "id": b.id,
            "cliente": b.cliente,
            "bd_opp": b.opp_name,
            "opp_id": b.opp_id,
            "wbs_bd": wbs_lines[0] if wbs_lines else None,
            "stop_utilizzo": stop,
            "totale": round(b.totale, 2),
            "consumato": round(b.consumato, 2),
            "residuo": round(b.delta, 2),
            "perc_utilizzo": round(perc, 4) if perc is not None else None,
            "note": b.note,
            "note_extra": b.note_extra,
            "opportunity_id": opp.id if opp else None,
            "linked_by": linked_by,
            "opp_name": opp.name if opp else "N/D",
            "opp_fy": fy_label(opp.fiscal_year) if opp else None,
            "mms_status": opp.mms_status if opp else None,
            "stato": stato,
            "stato_motivo": motivo,
            "monitor": bool(opp and (opp.mms_status or "").strip().lower() == "3b"),
        })
        agg = summary[stato]
        agg["count"] += 1
        agg["totale"] += b.totale
        agg["consumato"] += b.consumato
        agg["residuo"] += b.delta
    for agg in summary.values():
        for k in ("totale", "consumato", "residuo"):
            agg[k] = round(agg[k], 2)
    return {"rows": rows, "summary": summary}
