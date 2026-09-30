"""CCI per contract, read from the formula sheets of the workbook.

* ``Contracts`` is the official P&L: one block per contract with monthly
  Revenue / Total Cost / CCI / CCI % columns. Row 1 holds the column labels
  (month dates, then aggregates such as ``Q4FY26`` / ``FY26``), row 2 says
  whether a month is ``actual`` or ``forecast``.
* ``Sheet1`` is the current-quarter snapshot (ACTUAL vs FORECAST per client)
  that the dashboard mirrors as KPI cards.

CCI = Revenue - Total Cost; CCI % = CCI / Revenue. Values are taken from the
sheet when present and only computed as a fallback. Target: ``cci_target_threshold``.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from app.core.config import settings
from app.services.workbook_cache import current_workbook, find_sheet, sheet_values

_CONTRACT_HEADER_RE = re.compile(r"^\s*(\d{6,})\s*-\s*(.+?)\s*$")
_METRICS = {
    "billing": "billing", "billings": "billing",
    "revenue": "revenue", "revenues": "revenue",
    "payroll": "payroll", "non payroll": "non_payroll", "capital charge": "capital_charge",
    "total cost": "total_cost", "total costs": "total_cost",
    "cci %": "cci_pct", "cci%": "cci_pct",
}


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def fiscal_year_of(d: date) -> int:
    """Accenture FY: September-August. 2026-09 -> 2027."""
    return d.year + 1 if d.month >= 9 else d.year


def _parse_contracts(rows: list[list]) -> list[dict]:
    if len(rows) < 2:
        return []
    header, kinds = rows[0], rows[1]
    month_cols: list[tuple[int, date, str]] = []
    agg_cols: list[tuple[int, str]] = []
    for ci, v in enumerate(header):
        if ci == 0:
            continue
        if isinstance(v, datetime):
            kind = str(kinds[ci]).strip().lower() if ci < len(kinds) and kinds[ci] else "forecast"
            month_cols.append((ci, v.date().replace(day=1), "actual" if kind == "actual" else "forecast"))
        elif isinstance(v, str) and v.strip():
            agg_cols.append((ci, v.strip()))

    contracts = []
    i, n = 0, len(rows)
    while i < n:
        head = rows[i][0] if rows[i] else None
        m = _CONTRACT_HEADER_RE.match(head) if isinstance(head, str) else None
        if not m:
            i += 1
            continue
        cid, desc = m.group(1), m.group(2)
        wbs = None
        metrics: dict[str, list] = {}
        j = i + 1
        while j < n and j < i + 14:
            label = rows[j][0] if rows[j] else None
            if isinstance(label, str) and _CONTRACT_HEADER_RE.match(label):
                break
            key = str(label).strip().lower() if isinstance(label, str) else ""
            if j == i + 1 and key and " " not in key and key not in _METRICS and key != "cci":
                wbs = str(label).strip()
            elif key == "cci":
                # First "CCI" row is the amount; a second one (if any) is the percentage.
                metrics["cci_pct" if "cci" in metrics else "cci"] = rows[j]
            elif key in _METRICS:
                metrics[_METRICS[key]] = rows[j]
            j += 1

        def val(metric: str, col: int) -> float | None:
            row = metrics.get(metric)
            return _num(row[col]) if row is not None and col < len(row) else None

        def point(col: int) -> dict:
            revenue = val("revenue", col) or 0.0
            cost = val("total_cost", col)
            if cost is None:
                cost = sum(val(k, col) or 0.0 for k in ("payroll", "non_payroll", "capital_charge"))
            cci = val("cci", col)
            if cci is None:
                cci = revenue - cost
            pct = val("cci_pct", col)
            if pct is None and revenue:
                pct = cci / revenue
            if not revenue:
                pct = None  # no revenue: the sheet's IFERROR 0% would be misleading
            return {"revenue": round(revenue, 2), "total_cost": round(cost, 2),
                    "cci": round(cci, 2), "cci_pct": round(pct, 4) if pct is not None else None}

        if metrics:
            contracts.append({
                "id": cid,
                "description": desc,
                "wbs": wbs,
                "months": [{"month": d.strftime("%Y-%m"), "tipo": kind, **point(col)}
                           for col, d, kind in month_cols],
                "aggregates": [{"label": label, **point(col)} for col, label in agg_cols],
            })
        i = j
    return contracts


def _parse_sheet1(rows: list[list]) -> dict:
    """Parse the ACTUAL / FORECAST snapshot blocks of ``Sheet1``.

    Layout per block: marker ("ACTUAL"/"FORECAST") in column c, client in c+1
    (carried down), label in c+2, value in c+3; quarter label above the labels.
    """
    blocks: dict[str, dict[str, dict]] = {"actual": {}, "forecast": {}}
    quarter = None
    for ri, row in enumerate(rows):
        for ci, v in enumerate(row):
            if not isinstance(v, str) or v.strip().lower() not in ("actual", "forecast"):
                continue
            kind = v.strip().lower()
            if quarter is None and ri > 0 and ci + 2 < len(rows[ri - 1]):
                q = rows[ri - 1][ci + 2]
                quarter = q.strip() if isinstance(q, str) and q.strip() else None
            client = None
            for rr in rows[ri:]:
                c = rr[ci + 1] if ci + 1 < len(rr) else None
                label = rr[ci + 2] if ci + 2 < len(rr) else None
                value = rr[ci + 3] if ci + 3 < len(rr) else None
                if isinstance(c, str) and c.strip():
                    client = c.strip()
                if not isinstance(label, str):
                    if client and not any(x is not None for x in rr[ci:ci + 4]):
                        break
                    continue
                lab = label.strip().lower()
                if client is None or lab.startswith("tot cost"):
                    break
                entry = blocks[kind].setdefault(client, {})
                if lab.startswith("total revenue"):
                    entry["revenue"] = _num(value)
                elif lab.startswith("total cost"):
                    entry["total_cost"] = _num(value)
                elif lab.startswith("cci"):
                    entry["cci_pct"] = _num(value)
    gained = None
    for row in rows:
        for ci, v in enumerate(row):
            if isinstance(v, str) and v.strip().lower().startswith("spazio costi guadagnato"):
                gained = next((_num(x) for x in row[ci + 1:] if _num(x) is not None), None)
    clients = sorted(set(blocks["actual"]) | set(blocks["forecast"]),
                     key=lambda c: list(blocks["actual"]).index(c) if c in blocks["actual"] else 99)
    return {
        "quarter": quarter,
        "clients": [{"client": c, "actual": blocks["actual"].get(c), "forecast": blocks["forecast"].get(c)}
                    for c in clients],
        "spazio_costi_guadagnato": gained,
    }


def _recovery(months: list[dict], target: float, today: date) -> dict:
    """FY-to-date + forecast CCI of the current FY and the levers to reach target."""
    fy = fiscal_year_of(today)
    in_fy = [m for m in months
             if fiscal_year_of(date(int(m["month"][:4]), int(m["month"][5:7]), 1)) == fy]
    revenue = sum(m["revenue"] for m in in_fy)
    cost = sum(m["total_cost"] for m in in_fy)
    pct = (revenue - cost) / revenue if revenue else None
    remaining = [m for m in in_fy if m["tipo"] == "forecast"]
    out = {"fy": f"FY{str(fy)[-2:]}", "revenue": round(revenue, 2), "total_cost": round(cost, 2),
           "cci_pct": round(pct, 4) if pct is not None else None,
           "remaining_months": len(remaining), "below_target": False,
           "gap_pct": None, "gap_eur": None, "leva_ricavi": None, "leva_costi": None}
    if pct is not None and pct < target:
        gap = target - pct
        gap_eur = revenue * gap
        per_month = gap_eur / len(remaining) if remaining else None
        out.update(below_target=True, gap_pct=round(gap, 4), gap_eur=round(gap_eur, 2),
                   leva_ricavi=round(per_month, 2) if per_month is not None else None,
                   leva_costi=round(per_month, 2) if per_month is not None else None)
    return out


def _snapshot_recovery(snap: dict | None, target: float, remaining_months: int) -> dict | None:
    """Levers when the Sheet1 FORECAST CCI is below target: gap x forecast revenue."""
    fc = (snap or {}).get("forecast") or {}
    pct, revenue = fc.get("cci_pct"), fc.get("revenue")
    if pct is None or not revenue or pct >= target:
        return None
    gap = target - pct
    gap_eur = revenue * gap
    per_month = gap_eur / remaining_months if remaining_months else None
    return {"gap_pct": round(gap, 4), "gap_eur": round(gap_eur, 2), "remaining_months": remaining_months,
            "leva_ricavi": round(per_month, 2) if per_month is not None else None,
            "leva_costi": round(per_month, 2) if per_month is not None else None}


def _match_client(name: str, candidates: list[str]) -> str | None:
    low = name.lower()
    for c in candidates:
        if c.lower() == low:
            return c
    for c in candidates:
        if c.lower()[:4] == low[:4]:
            return c
    return None


def cci_overview(client_by_contract: dict[str, str], today: date | None = None) -> dict:
    """Full CCI payload. ``client_by_contract`` maps contract id -> client name."""
    path = current_workbook()
    if path is None or not path.exists():
        return {"available": False, "target": settings.cci_target_threshold, "contracts": [], "snapshot": None}
    sheets = sheet_values(path)
    target = settings.cci_target_threshold
    today = today or date.today()
    contracts_rows = find_sheet(sheets, lambda t: t == "contracts") or []
    sheet1_rows = find_sheet(sheets, lambda t: t == "sheet1")
    snapshot = _parse_sheet1(sheet1_rows) if sheet1_rows else None

    contracts = _parse_contracts(contracts_rows)
    snap_clients = [c["client"] for c in snapshot["clients"]] if snapshot else []
    for c in contracts:
        c["client"] = client_by_contract.get(c["id"])
        snap_name = _match_client(c["client"], snap_clients) if c["client"] else None
        snap = next((s for s in snapshot["clients"] if s["client"] == snap_name), None) if snapshot else None
        c["snapshot"] = snap
        c["recovery"] = _recovery(c["months"], target, today)
        c["recovery_snapshot"] = _snapshot_recovery(snap, target, c["recovery"]["remaining_months"])
        alerts = []
        for kind in ("actual", "forecast"):
            pct = (snap or {}).get(kind, {}) and snap[kind].get("cci_pct")
            if pct is not None and pct < target:
                alerts.append(kind)
        if c["recovery"]["below_target"]:
            alerts.append("fy")
        c["alerts"] = alerts
    return {"available": True, "target": target, "contracts": contracts, "snapshot": snapshot}
