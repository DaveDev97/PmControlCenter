"""Financial context builder for the AI chat assistant.

Reads directly from the in-RAM workbook cache (no disk access, no DB) and
produces:
* a structured TEXT block that goes into the Claude system prompt as "DATI",
* a Markdown briefing string shown automatically at the start of each session.

The context includes:
  - Per-contract monthly P&L (revenue / costs / CCI %) for the current FY
  - Resource costs per month (people + other cost lines + SUM costi)
  - Cost space already allocated by WBS
  - Booking in corso / Opp in attesa OdA (additional space if deals close)
  - Three CCI scenarios: A=only allocated, B=+booking, C=+booking+OdA
"""
from __future__ import annotations

import re
from datetime import date

from app.services.cci import _parse_contracts, fiscal_year_of
from app.services.cost_space import _MONTHS_IT, _num, excel_monthly_costs
from app.services.workbook_cache import cached_sheets, find_sheet

CCI_TARGET = 0.35
COST_RATIO = 0.65  # 1 - CCI_TARGET


# ---------------------------------------------------------------------------
# Sheet parsers
# ---------------------------------------------------------------------------

def _cost_cols_from_sheet(rows: list[list]) -> list[tuple[int, str]]:
    """Return (cost_col_index, 'YYYY-MM') pairs from the Costi vs Forecast layout."""
    fy_cols: list[tuple[int, int]] = []
    month_row = None
    hdr = next((i for i, r in enumerate(rows)
                if "Resource" in [str(v).strip() if isinstance(v, str) else "" for v in r]), None)
    if hdr is None:
        return []
    for row in rows[:hdr]:
        for ci, v in enumerate(row):
            if isinstance(v, str) and v.strip().upper().startswith("FY") and v.strip()[2:].isdigit():
                fy_cols.append((ci, 2000 + int(v.strip()[2:])))
        if sum(1 for v in row if isinstance(v, str) and v.strip().lower() in _MONTHS_IT) >= 6:
            month_row = row
    if not month_row or not fy_cols:
        return []
    labels = [(v.strip().lower() if isinstance(v, str) else "") for v in rows[hdr]]
    cost_cols: list[tuple[int, str]] = []
    for ci, v in enumerate(month_row):
        m = _MONTHS_IT.get(v.strip().lower()) if isinstance(v, str) else None
        fy = next((y for c, y in reversed(fy_cols) if c <= ci), None)
        if m is None or fy is None:
            continue
        year = fy - 1 if m >= 9 else fy
        col = ci + 1 if ci + 1 < len(labels) and labels[ci + 1].startswith("costo") else ci
        cost_cols.append((col, f"{year:04d}-{m:02d}"))
    return cost_cols


def _parse_space_sections(rows: list[list], cost_cols: list[tuple[int, str]]) -> dict:
    """Parse three sections below SUM costi: WBS space, Booking, OdA.

    Returns {"wbs": [...], "booking": [...], "oda": [...]} where each item has
    {"name", "total_revenue", "monthly": {"YYYY-MM": amount}}.
    """
    res_col = next(
        (i for i, r in enumerate(rows)
         for ci, v in enumerate(r) if isinstance(v, str) and v.strip() == "Resource"),
        None,
    )
    if res_col is None:
        # find column index of "Resource" in the header row
        for row in rows:
            for ci, v in enumerate(row):
                if isinstance(v, str) and v.strip() == "Resource":
                    res_col = ci
                    break
            if res_col is not None:
                break
    if res_col is None:
        res_col = 1

    lc_col = res_col + 1

    wbs: list[dict] = []
    booking: list[dict] = []
    oda: list[dict] = []

    in_section = False  # True after first "SUM costi"
    current_list = None
    sum_count = 0

    for row in rows:
        name = row[res_col] if res_col < len(row) else None
        if not isinstance(name, str) or not name.strip():
            continue
        nm = name.strip()
        nm_low = nm.lower()

        if nm_low.startswith("sum costi"):
            in_section = True
            continue
        if not in_section:
            continue

        if "sum spazio costi" in nm_low:
            sum_count += 1
            if sum_count >= 2:
                break
            continue

        if "booking in corso" in nm_low:
            current_list = booking
            continue
        if "opp in attesa" in nm_low or "attesa di conferma" in nm_low:
            current_list = oda
            continue

        # WBS space rows (before any "booking" label) or booking/oda rows
        lc_val = _num(row[lc_col]) if lc_col < len(row) else None
        monthly = {}
        for col, key in cost_cols:
            v = _num(row[col]) if col < len(row) else None
            if v:
                monthly[key] = round(v, 2)
        if not monthly and lc_val is None:
            continue

        entry = {"name": nm, "total_revenue": lc_val, "monthly": monthly}
        if current_list is None:
            wbs.append(entry)
        else:
            current_list.append(entry)

    return {"wbs": wbs, "booking": booking, "oda": oda}


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _fmt_eur(v: float) -> str:
    return f"{v:,.0f} €".replace(",", ".")


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "n/d"
    return f"{v * 100:.1f}%"


def build_context_text(today: date | None = None) -> str:
    """Full financial context as plain text for the AI system prompt."""
    today = today or date.today()
    cur = today.strftime("%Y-%m")
    fy = fiscal_year_of(today)
    fy_label = f"FY{str(fy)[-2:]}"

    lines: list[str] = [
        f"DATI AGGIORNATI AL: {today.strftime('%d/%m/%Y')}",
        f"MESE CORRENTE: {cur}  |  FY: {fy_label}  |  CCI TARGET: 35%  |  SPAZIO COSTI = REVENUE × 65%",
        "",
    ]

    sheets = cached_sheets()

    # --- Contracts P&L ---
    contracts_rows = find_sheet(sheets, lambda t: t == "contracts") or []
    contracts = _parse_contracts(contracts_rows)
    lines.append("=== CONTRATTI — P&L MENSILE ===")
    for c in contracts:
        fy_months = [m for m in c["months"]
                     if fiscal_year_of(date(int(m["month"][:4]), int(m["month"][5:7]), 1)) == fy]
        fy_agg = next((a for a in c.get("aggregates", []) if a["label"].upper() == fy_label), None)
        lines.append(f"\n{c['id']} — WBS {c['wbs']} — {c['description']}")
        if fy_agg:
            lines.append(
                f"  {fy_label} totale: rev {_fmt_eur(fy_agg['revenue'])}, "
                f"costi {_fmt_eur(fy_agg['total_cost'])}, "
                f"CCI {_fmt_pct(fy_agg['cci_pct'])}"
            )
        for m in fy_months:
            sp = m["revenue"] * COST_RATIO
            surplus = sp - m["total_cost"]
            lines.append(
                f"  {m['month']} ({m['tipo']}): "
                f"rev {_fmt_eur(m['revenue'])}, "
                f"costi {_fmt_eur(m['total_cost'])}, "
                f"CCI {_fmt_pct(m['cci_pct'])}, "
                f"spazio {_fmt_eur(sp)}, "
                f"surplus/deficit {_fmt_eur(surplus)}"
            )
    lines.append("")

    # --- Costi vs Forecast ---
    data = excel_monthly_costs()
    if data:
        cost_cols = _cost_cols_from_sheet(
            find_sheet(sheets, lambda t: "costi vs forecast" in t) or []
        )
        space_data = _parse_space_sections(
            find_sheet(sheets, lambda t: "costi vs forecast" in t) or [], cost_cols
        )

        # Focus months: current + next 2
        all_months = data["months"]
        idx = all_months.index(cur) if cur in all_months else -1
        focus = all_months[max(0, idx):idx + 3] if idx >= 0 else all_months[-3:]

        for fm in focus:
            total_costi = data["sum_costi"].get(fm)
            lines.append(f"=== COSTI RISORSE — {fm} ===")
            if total_costi:
                lines.append(f"  SUM costi totale: {_fmt_eur(total_costi)}")
            lines.append("  Persone:")
            for name, months in data["people"].items():
                if fm in months:
                    lines.append(f"    {name}: {_fmt_eur(months[fm])}")
            if data["other"]:
                lines.append("  Altri costi (non risorsa):")
                for o in data["other"]:
                    if fm in o["months"]:
                        lines.append(f"    {o['name']}: {_fmt_eur(o['months'][fm])}")
            lines.append("")

            # WBS space
            wbs_items = [(w["name"], w["monthly"].get(fm)) for w in space_data["wbs"] if w["monthly"].get(fm)]
            if wbs_items:
                lines.append(f"=== SPAZIO COSTI GIÀ ALLOCATO — {fm} ===")
                total_wbs = 0.0
                for name, amt in wbs_items:
                    lines.append(f"  {name}: {_fmt_eur(amt)}")
                    total_wbs += amt
                lines.append(f"  TOTALE WBS ALLOCATO: {_fmt_eur(total_wbs)}")
                lines.append("")

            # Booking / OdA
            bk_items = [(b["name"], b["monthly"].get(fm), b["total_revenue"])
                        for b in space_data["booking"] if b["monthly"].get(fm)]
            oda_items = [(o["name"], o["monthly"].get(fm), o["total_revenue"])
                         for o in space_data["oda"] if o["monthly"].get(fm)]
            if bk_items:
                lines.append(f"=== BOOKING IN CORSO — spazio costi potenziale {fm} ===")
                for name, amt, rev in bk_items:
                    rev_str = f" (opp rev totale {_fmt_eur(rev)})" if rev else ""
                    lines.append(f"  {name}: {_fmt_eur(amt)}{rev_str}")
                lines.append(f"  TOTALE BOOKING: {_fmt_eur(sum(a for _, a, _ in bk_items))}")
                lines.append("")
            if oda_items:
                lines.append(f"=== OPP IN ATTESA ODA — spazio costi potenziale {fm} ===")
                for name, amt, rev in oda_items:
                    rev_str = f" (opp rev totale {_fmt_eur(rev)})" if rev else ""
                    lines.append(f"  {name}: {_fmt_eur(amt)}{rev_str}")
                lines.append(f"  TOTALE OdA: {_fmt_eur(sum(a for _, a, _ in oda_items))}")
                lines.append("")

            # Scenarios
            sc_rev = sum(
                m["revenue"] for c in contracts
                for m in c["months"] if m["month"] == fm
            )
            sc_space = sc_rev * COST_RATIO
            sc_costs = total_costi or 0.0
            wbs_space = sum(a for _, a in wbs_items)
            bk_space = sum(a for _, a, _ in bk_items)
            oda_space = sum(a for _, a, _ in oda_items)
            lines.append(f"=== SCENARI CCI — {fm} ===")
            for label, extra in [("A — solo revenue allocate", 0),
                                  ("B — +booking in corso", bk_space),
                                  ("C — +booking +OdA confermati", bk_space + oda_space)]:
                space_tot = wbs_space + extra
                deficit = space_tot - sc_costs
                cci_pct = (sc_rev + extra / COST_RATIO * COST_RATIO - sc_costs) / (sc_rev + extra / COST_RATIO * COST_RATIO) if (sc_rev + extra / COST_RATIO * COST_RATIO) else None
                lines.append(
                    f"  Scenario {label}: spazio {_fmt_eur(space_tot)}, "
                    f"costi {_fmt_eur(sc_costs)}, "
                    f"surplus/deficit {_fmt_eur(deficit)}"
                )
            lines.append("")

    return "\n".join(lines)


def build_briefing(today: date | None = None) -> str:
    """Startup briefing as Markdown (rendered in the chat UI)."""
    today = today or date.today()
    cur = today.strftime("%Y-%m")
    fy = fiscal_year_of(today)
    fy_label = f"FY{str(fy)[-2:]}"

    sheets = cached_sheets()
    contracts_rows = find_sheet(sheets, lambda t: t == "contracts") or []
    contracts = _parse_contracts(contracts_rows)
    data = excel_monthly_costs()

    if not sheets or (not contracts and not data):
        return (
            "**Sessione ripristinata.**\n\n"
            "Dati non ancora caricati — configura la cartella dati nelle Impostazioni."
        )

    md: list[str] = [
        f"**Sessione ripristinata. Dati aggiornati al: {today.strftime('%d/%m/%Y')}**\n",
        f"Mese corrente: **{cur}** ({fy_label}) | CCI target: **35%** | spazio costi = revenue × 65%\n",
    ]

    # WBS disponibili
    wbs_list = [f"`{c['wbs']}` — {c['description']}" for c in contracts if c.get("wbs")]
    if wbs_list:
        md.append("**WBS disponibili:**")
        for w in wbs_list:
            md.append(f"• {w}")
        md.append("")

    # Contract CCI table for current month
    md.append(f"### CCI — {cur}\n")
    md.append("| Contratto | WBS | Revenue | Costi | CCI % | Spazio disponibile |")
    md.append("|-----------|-----|--------:|------:|------:|-------------------:|")
    account_rev = account_cost = 0.0
    for c in contracts:
        m = next((m for m in c["months"] if m["month"] == cur), None)
        if not m:
            m = next((x for x in c["months"] if x["month"] >= cur), None)
        if not m:
            continue
        sp = m["revenue"] * COST_RATIO
        account_rev += m["revenue"]
        account_cost += m["total_cost"]
        md.append(
            f"| {c['description'][:30]} | {c['wbs'] or '—'} "
            f"| {m['revenue']:,.0f} € | {m['total_cost']:,.0f} € "
            f"| **{_fmt_pct(m['cci_pct'])}** | {sp:,.0f} € |"
        )
    if account_rev or account_cost:
        sp_acc = account_rev * COST_RATIO
        cci_acc = (account_rev - account_cost) / account_rev if account_rev else None
        md.append(
            f"| **ACCOUNT** | — "
            f"| **{account_rev:,.0f} €** | **{account_cost:,.0f} €** "
            f"| **{_fmt_pct(cci_acc)}** | **{sp_acc:,.0f} €** |"
        )
    md.append("")

    # Resource costs for current month
    if data and cur in (data.get("sum_costi") or {}):
        total_costi = data["sum_costi"][cur]
        md.append(f"### Costi risorse — {cur} (SUM costi: **{total_costi:,.0f} €**)\n")
        md.append("| Risorsa | Costo € |")
        md.append("|---------|--------:|")
        people_rows = [(n, m[cur]) for n, m in data["people"].items() if cur in m]
        people_rows.sort(key=lambda x: -x[1])
        for name, cost in people_rows:
            md.append(f"| {name} | {cost:,.0f} |")
        for o in data.get("other", []):
            if cur in o["months"]:
                md.append(f"| *{o['name']}* | {o['months'][cur]:,.0f} |")
        md.append("")

    # Cost space + scenarios
    cost_cols = _cost_cols_from_sheet(
        find_sheet(sheets, lambda t: "costi vs forecast" in t) or []
    )
    space_data = _parse_space_sections(
        find_sheet(sheets, lambda t: "costi vs forecast" in t) or [], cost_cols
    )
    wbs_items = [(w["name"], w["monthly"].get(cur, 0)) for w in space_data["wbs"]]
    bk_items = [(b["name"], b["monthly"].get(cur, 0), b["total_revenue"])
                for b in space_data["booking"] if b["monthly"].get(cur)]
    oda_items = [(o["name"], o["monthly"].get(cur, 0), o["total_revenue"])
                 for o in space_data["oda"] if o["monthly"].get(cur)]

    wbs_total = sum(a for _, a in wbs_items if a)
    bk_total = sum(a for _, a, _ in bk_items)
    oda_total = sum(a for _, a, _ in oda_items)
    total_costi_val = (data.get("sum_costi") or {}).get(cur, 0)

    md.append(f"### Scenari spazio costi — {cur}\n")
    md.append("| Scenario | Spazio disponibile | Costi | Surplus / Deficit |")
    md.append("|----------|------------------:|------:|------------------:|")
    for label, extra in [
        ("A — solo revenue allocate", 0),
        ("B — + booking in corso", bk_total),
        ("C — + booking + OdA", bk_total + oda_total),
    ]:
        space = wbs_total + extra
        delta = space - total_costi_val
        md.append(
            f"| {label} | {space:,.0f} € | {total_costi_val:,.0f} € "
            f"| {'🟢' if delta >= 0 else '🔴'} {delta:+,.0f} € |"
        )
    md.append("")
    md.append("Pronta per analisi. Cosa vuoi approfondire?")
    return "\n".join(md)
