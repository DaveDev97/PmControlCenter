"""Account Overview: aggregated financial KPIs read directly from the workbook.

Data sources (all from the in-RAM workbook cache, zero disk access):
  - "Contracts" sheet  → revenue per contract per month
  - Pipeline sheets    → Close Won opportunities (Sales FY)
  - "Costi vs Forecast"→ LC (loaded cost hourly) per resource, column C
  - "Team & Resources" → hours per resource per month (for cost computation)

For per-contract cost breakdown we fall back to the DB allocation model when
the Team & Resources sheet cannot be split by contract.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.services.workbook_cache import cached_sheets, find_sheet
from app.services.cci import _parse_contracts
from app.services.team_allocation import _layout as _team_layout

_MONTHS_IT = ["", "Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
_MONTHS_EN_TO_NUM = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTHS_IT_TO_NUM = {
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
    "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12,
}
CCI_TARGET = 0.35
COST_RATIO = 1 - CCI_TARGET  # 0.65


# ── Helpers ──────────────────────────────────────────────────────────────────

def fy_range(fy_label: str) -> tuple[date, date]:
    """'FY27' → (2026-09-01, 2027-08-31)"""
    year = int("20" + fy_label[2:])
    return date(year - 1, 9, 1), date(year, 8, 31)


def fy_months(fy_start: date, fy_end: date) -> list[str]:
    """All YYYY-MM keys in the FY, Sep to Aug."""
    out = []
    d = fy_start
    while d <= fy_end:
        out.append(d.strftime("%Y-%m"))
        d = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
    return out


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _try_parse_month(v) -> str | None:
    """Convert various month representations to 'YYYY-MM'."""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m")
    if isinstance(v, date):
        return v.strftime("%Y-%m")
    if not isinstance(v, str):
        return None
    v = v.strip()
    # YYYY-MM or MM/YYYY
    m = re.match(r'^(\d{4})[/\-](\d{1,2})$', v)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}"
    m = re.match(r'^(\d{1,2})[/\-](\d{4})$', v)
    if m:
        mo, y = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}"
    # "Set 2026", "Sep 2026", "September 2026"
    m = re.match(r'^([A-Za-zàèìòù]+)\s+(\d{4})$', v)
    if m:
        mon_str, y = m.group(1).lower()[:3], int(m.group(2))
        mo = _MONTHS_IT_TO_NUM.get(mon_str) or _MONTHS_EN_TO_NUM.get(mon_str)
        if mo:
            return f"{y:04d}-{mo:02d}"
    return None


# ── LC map from "Costi vs Forecast" ──────────────────────────────────────────

def _parse_lc_map(rows: list[list]) -> dict[str, float]:
    """Resource name (col A) → LC hourly rate (col C). Skips headers/labels."""
    lc_map: dict[str, float] = {}
    SKIP_LABELS = {"risorse", "resources", "altre spese", "other costs", "totale",
                   "total", "costo", "cost", "descrizione", "description", "nome",
                   "spazio", "spazi", "sum", "fy", "forecast", "actual"}
    for row in rows:
        if len(row) < 3:
            continue
        name = row[0]
        lc = row[2]
        if not isinstance(name, str) or not name.strip():
            continue
        name_clean = name.strip()
        if name_clean.lower() in SKIP_LABELS or name_clean.startswith("#") or name_clean.startswith("="):
            continue
        # Only accept LC if it looks like an hourly rate (positive float)
        lc_val = _num(lc)
        if lc_val and lc_val > 0:
            lc_map[name_clean] = lc_val
    return lc_map


# ── Pipeline sheets → Sales ───────────────────────────────────────────────────

def _find_pipeline_rows(sheets: dict, fy_label: str) -> list[list[list]]:
    """Find all sheets that could contain pipeline/opportunity data for a FY."""
    y2 = fy_label[2:]       # "27"
    fy_full = "20" + y2     # "2027"
    EXCLUDED = {"contratt", "costi", "sheet1", "forecast", "resource", "risorsa", "team"}
    result = []
    for title, rows in sheets.items():
        tl = title.lower().strip()
        if any(ex in tl for ex in EXCLUDED):
            continue
        if f"fy{y2}" in tl or fy_full in tl:
            result.append(rows)
    return result


def _parse_sales(sheets: dict, fy_label: str, fy_start: date, fy_end: date,
                 contract_filter: str | None) -> tuple[float, int, str | None]:
    """Return (total_sales, count, warning_or_None) from pipeline sheets."""
    sheets_rows = _find_pipeline_rows(sheets, fy_label)
    if not sheets_rows:
        return 0.0, 0, f"Sheet pipeline {fy_label} non trovato"

    total, count = 0.0, 0
    for rows in sheets_rows:
        if not rows:
            continue
        # Find header row
        col_mms = col_date = col_amount = col_contract = -1
        header_ri = None
        for ri, row in enumerate(rows[:15]):
            for ci, v in enumerate(row):
                if not isinstance(v, str):
                    continue
                vl = v.strip().lower()
                if "mms" in vl:
                    col_mms = ci
                    header_ri = ri
                elif "close" in vl and "date" in vl:
                    col_date = ci
                elif "amount" in vl or "importo" in vl or "valore" in vl:
                    col_amount = ci
                elif ("contract" in vl or "wbs" in vl) and col_contract == -1:
                    col_contract = ci
        if header_ri is None or col_mms == -1:
            continue
        for row in rows[header_ri + 1:]:
            if not row or all(v is None for v in row):
                continue
            mms = row[col_mms] if col_mms < len(row) else None
            if not isinstance(mms, str):
                continue
            mms_l = mms.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
            if "closewon" not in mms_l and not ("close" in mms_l and "won" in mms_l):
                continue
            # Close date filter
            if col_date >= 0 and col_date < len(row):
                cd = row[col_date]
                if isinstance(cd, datetime):
                    cd = cd.date()
                if isinstance(cd, date) and not (fy_start <= cd <= fy_end):
                    continue
            # Contract filter
            if contract_filter:
                ct = row[col_contract] if col_contract >= 0 and col_contract < len(row) else None
                if isinstance(ct, str) and contract_filter not in ct:
                    continue
            amount = _num(row[col_amount]) if col_amount >= 0 and col_amount < len(row) else None
            if amount and amount > 0:
                total += amount
                count += 1
    return round(total, 2), count, None


# ── Costi vs Forecast → ore per risorsa per mese ─────────────────────────────

def _parse_team_hours(
    sheets: dict,
    lc_map: dict[str, float],
    fy_start: date,
    fy_end: date,
    today: date,
) -> tuple[dict[str, dict[str, float]], list[str]]:
    """
    Legge le ore per risorsa per mese dal foglio 'Costi vs Forecast' usando la
    stessa struttura già parsata dal Team Dashboard (_team_layout).
    Returns ({resource_name: {month_key: hours}}, warnings).
    """
    costi_rows = find_sheet(sheets, lambda t: "costi" in t and "forecast" in t)
    if not costi_rows:
        return {}, ["Foglio 'Costi vs Forecast' non trovato — costi impostati a zero"]

    layout = _team_layout(costi_rows)
    if layout is None:
        return {}, ["Struttura del foglio 'Costi vs Forecast' non riconosciuta — costi impostati a zero"]

    hdr, res_col, _lc_col, _charg_col, cols = layout
    mk_set = set(fy_months(fy_start, fy_end))

    # Filtra solo le colonne nel FY richiesto
    fy_cols = [(ci, mk) for ci, mk, _mh in cols if mk in mk_set]
    if not fy_cols:
        return {}, [f"Nessun mese del FY trovato nel foglio 'Costi vs Forecast'"]

    SKIP = {"totale", "total", "risorse", "resources", "team", "subtotale",
            "subtotal", "riepilogo", "summary", "nome", "name", "payroll",
            "not payroll", "notpayroll", "capex", "totale risorse"}
    result: dict[str, dict[str, float]] = {}
    missing_lc: set[str] = set()

    for row in costi_rows[hdr + 1:]:
        if not row:
            continue
        name = row[res_col] if res_col < len(row) else None
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()
        if name.lower() in SKIP or name.startswith("#") or name.startswith("="):
            continue
        if name not in lc_map:
            missing_lc.add(name)
        hours: dict[str, float] = {}
        for ci, mk in fy_cols:
            v = _num(row[ci]) if ci < len(row) else None
            if v and v > 0:
                hours[mk] = v
        if hours:
            result[name] = hours

    warnings = []
    if missing_lc:
        warnings.append(
            f"LC non trovato per: {', '.join(sorted(missing_lc))}. "
            "I costi potrebbero essere sottostimati."
        )
    return result, warnings


# ── Main builder ─────────────────────────────────────────────────────────────

def build_overview(
    fy_label: str,
    contract_filter: str,   # "all" or contract_id
    today: date | None = None,
) -> dict:
    today = today or date.today()
    fy_start, fy_end = fy_range(fy_label)
    mk_set = set(fy_months(fy_start, fy_end))
    sheets = cached_sheets()

    if not sheets:
        return {"available": False, "error": "Workbook non caricato"}

    # ── Revenue from Contracts sheet ─────────────────────────────────────────
    contracts_rows = find_sheet(sheets, lambda t: t == "contracts") or []
    all_contracts = _parse_contracts(contracts_rows)

    contracts_available = [{"id": c["id"], "label": f"{c['id']} – {c['description']}"}
                           for c in all_contracts]

    active_contracts = (
        [c for c in all_contracts if c["id"] == contract_filter]
        if contract_filter != "all"
        else all_contracts
    )

    revenue_fy = 0.0
    rev_by_contract: dict[str, float] = {}
    for c in all_contracts:
        r = sum(max(0.0, m["revenue"] or 0.0) for m in c["months"] if m["month"] in mk_set)
        rev_by_contract[c["id"]] = r
    revenue_fy = sum(rev_by_contract.get(c["id"], 0.0) for c in active_contracts)

    # ── Sales from pipeline sheets ───────────────────────────────────────────
    cf = contract_filter if contract_filter != "all" else None
    sales_total, sales_count, sales_warn = _parse_sales(sheets, fy_label, fy_start, fy_end, cf)
    warnings: list[str] = []
    if sales_warn:
        warnings.append(sales_warn)

    # ── LC map ───────────────────────────────────────────────────────────────
    costi_rows = find_sheet(sheets, lambda t: "costi" in t and "forecast" in t) or []
    lc_map = _parse_lc_map(costi_rows)

    # ── Team hours → costs ───────────────────────────────────────────────────
    team_hours, team_warns = _parse_team_hours(sheets, lc_map, fy_start, fy_end, today)
    warnings.extend(team_warns)

    costi_ad_oggi = 0.0
    costi_totali_fy = 0.0
    for res, months_map in team_hours.items():
        lc = lc_map.get(res, 0.0)
        for mk, hrs in months_map.items():
            cost = hrs * lc
            costi_totali_fy += cost
            if date(int(mk[:4]), int(mk[5:7]), 1) <= today:
                costi_ad_oggi += cost

    # ── Monthly breakdown ─────────────────────────────────────────────────────
    spazio_costi_fy = revenue_fy * COST_RATIO
    monthly = []
    for mk in sorted(mk_set):
        yr, mo = int(mk[:4]), int(mk[5:7])
        month_date = date(yr, mo, 1)
        is_past = month_date <= today

        # Revenue this month (filtered contracts)
        rev_m = 0.0
        for c in active_contracts:
            for m in c["months"]:
                if m["month"] == mk:
                    rev_m += max(0.0, m["revenue"] or 0.0)

        # Costs this month (all resources; contract split not available from Team sheet)
        costi_piano_m = sum(
            team_hours[res].get(mk, 0.0) * lc_map.get(res, 0.0)
            for res in team_hours
        )

        spazio_m = rev_m * COST_RATIO
        cci_m = (rev_m / costi_piano_m) if (is_past and costi_piano_m > 0) else None

        monthly.append({
            "month": mk,
            "month_label": f"{_MONTHS_IT[mo]} {yr}",
            "revenue": round(rev_m, 2),
            "costi_allocati": round(costi_piano_m, 2) if is_past else None,
            "costi_pianificati": round(costi_piano_m, 2),
            "spazio_costi": round(spazio_m, 2),
            "cci": round(cci_m, 4) if cci_m is not None else None,
            "is_past": is_past,
        })

    # ── Per-contract breakdown ────────────────────────────────────────────────
    # Note: costs are global (Team sheet has no per-contract split) → show revenue only.
    # CCI is computed from revenue only (costs = None, shown as "n/d" in UI).
    per_contract = []
    if contract_filter == "all":
        for c in all_contracts:
            r = rev_by_contract.get(c["id"], 0.0)
            per_contract.append({
                "id": c["id"],
                "name": c["description"],
                "revenue_fy": round(r, 2),
                "spazio_costi_fy": round(r * COST_RATIO, 2),
            })

    # ── Derived metrics ───────────────────────────────────────────────────────
    cci_proiettato = revenue_fy / costi_totali_fy if costi_totali_fy > 0 else None
    coverage_pct = revenue_fy / sales_total * 100 if sales_total > 0 else None
    pct_spazio = costi_ad_oggi / spazio_costi_fy * 100 if spazio_costi_fy > 0 else None

    return {
        "available": True,
        "fy": fy_label,
        "fy_start": fy_start.isoformat(),
        "fy_end": fy_end.isoformat(),
        "contracts_available": contracts_available,
        "sales": {"amount": sales_total, "count": sales_count},
        "revenue": {
            "amount": round(revenue_fy, 2),
            "coverage_pct": round(coverage_pct, 1) if coverage_pct is not None else None,
        },
        "costi_ad_oggi": {
            "amount": round(costi_ad_oggi, 2),
            "pct_spazio_costi": round(pct_spazio, 1) if pct_spazio is not None else None,
        },
        "costi_totali_fy": {
            "amount": round(costi_totali_fy, 2),
            "cci_proiettato": round(cci_proiettato, 2) if cci_proiettato is not None else None,
        },
        "monthly": monthly,
        "per_contract": per_contract,
        "warnings": warnings,
    }
