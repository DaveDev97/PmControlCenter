"""Resource allocation status from the "Costi vs Forecast" sheet.

Each person's ``%Charg`` is their own chargeability target (not a global
threshold). Monthly hours in the sheet are written as::

    = month_hours * %Charg                      full allocation on the account
    = (month_hours - 32) * %Charg               32 h of absence (holidays...)
    = (month_hours * %Charg) * 0.5              50% on the account, 50% on "Other"
    = (((month_hours - 12) * %Charg) * 0.5) - 16

so for every month we derive:

* ``share``   - fraction of the person's chargeable time on this account (the
  trailing multiplier; 1 when absent). ``1 - share`` is time on "Other" projects:
  the person is still correctly allocated, it is only flagged;
* ``absence_hours`` - hours subtracted (not treated as "Other");
* ``status``  - ``ok`` (hours booked), ``bench`` (a %Charg but no hours in a month
  where others are planned), ``over`` (more hours than the working hours of the
  month), ``nd`` (no %Charg), ``np`` (month not planned yet: nobody has hours).

When a cell holds a typed value instead of a formula, the share is estimated
from the value (hours / (month_hours x %Charg)).
"""
from __future__ import annotations

import re
from datetime import date

from app.services.cost_space import _MONTHS_IT
from app.services.excel_reader import classify_cost_row
from app.services.workbook_cache import cached_formulas, cached_sheets

_MULT_RE = re.compile(r"\*\s*(\d*\.?\d+)\s*\)*\s*(?:-\s*\d+(?:\.\d+)?\s*)?$")
_ABS_IN_RE = re.compile(r"\$?[A-Z]+\$?\d+\s*-\s*(\d+(?:\.\d+)?)")
_ABS_TAIL_RE = re.compile(r"\)\s*-\s*(\d+(?:\.\d+)?)\s*$")
_MONTH_CELL_RE = re.compile(r"\$[A-Z]+\$\d+")


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def parse_hours_formula(formula) -> dict | None:
    """Share / absences from an hours formula; None if it is not a formula on the month hours."""
    if not isinstance(formula, str) or not formula.startswith("=") or not _MONTH_CELL_RE.search(formula):
        return None
    f = formula.replace(" ", "")
    m = _MULT_RE.search(f)
    share = float(m.group(1)) if m else 1.0
    absence = sum(float(x) for x in _ABS_IN_RE.findall(f))
    tail = _ABS_TAIL_RE.search(f)
    if tail:
        absence += float(tail.group(1)) / (share or 1)  # hours removed after the share
    return {"share": share, "absence_hours": round(absence, 1)}


def _layout(rows: list[list]):
    """Header row index, key columns and (hours col, month key, month hours) triples."""
    hdr = next((i for i, r in enumerate(rows)
                if any(isinstance(v, str) and v.strip() == "Resource" for v in r)), None)
    if hdr is None:
        return None
    labels = [(v.strip().lower() if isinstance(v, str) else "") for v in rows[hdr]]
    res_col = labels.index("resource")
    lc_col = labels.index("lc") if "lc" in labels else None
    charg_col = next((i for i, v in enumerate(labels) if v.startswith("%charg")), None)
    fy_cols: list[tuple[int, int]] = []
    month_row = None
    for row in rows[:hdr]:
        for ci, v in enumerate(row):
            if isinstance(v, str) and v.strip().upper().startswith("FY") and v.strip()[2:].isdigit():
                fy_cols.append((ci, 2000 + int(v.strip()[2:])))
        if sum(1 for v in row if isinstance(v, str) and v.strip().lower() in _MONTHS_IT) >= 6:
            month_row = row
    if month_row is None or not fy_cols:
        return None
    cols = []
    for ci, v in enumerate(month_row):
        mnum = _MONTHS_IT.get(v.strip().lower()) if isinstance(v, str) else None
        fy = next((y for c, y in reversed(fy_cols) if c <= ci), None)
        if mnum is None or fy is None:
            continue
        year = fy - 1 if mnum >= 9 else fy
        mh = _num(rows[hdr][ci]) if ci < len(rows[hdr]) else None
        cols.append((ci, f"{year:04d}-{mnum:02d}", mh))
    return hdr, res_col, lc_col, charg_col, cols


def _month_status(hours, month_hours, perc, parsed) -> dict:
    out = {"hours": round(hours, 1) if hours else None, "month_hours": month_hours,
           "share": None, "other_pct": None, "absence_hours": None}
    if perc is None:
        out["status"] = "nd"
        return out
    if not hours:
        out["status"] = "bench"
        return out
    full = (month_hours or 0) * perc
    if parsed is not None:
        share = parsed["share"]
        out["absence_hours"] = parsed["absence_hours"] or None
    else:
        share = round(min(hours / full, 1.0) * 20) / 20 if full else 1.0  # nearest 5%
    out["share"] = round(share, 2)
    out["other_pct"] = round(1 - share, 2) if share < 0.99 else None
    out["status"] = "over" if month_hours and hours > month_hours + 0.5 else "ok"
    return out


def allocation_overview(month: str | None = None) -> dict:
    """Per-person monthly allocation status; ``month`` = 'YYYY-MM' (default: current)."""
    sheets = cached_sheets()
    title = next((t for t in sheets if "costi vs forecast" in t.lower()), None)
    if title is None:
        return {"available": False, "month": month, "months": [], "people": []}
    rows = sheets[title]
    frows = cached_formulas().get(title, [])
    lay = _layout(rows)
    if lay is None:
        return {"available": False, "month": month, "months": [], "people": []}
    hdr, res_col, lc_col, charg_col, cols = lay
    months = [k for _, k, _ in cols]
    today = date.today().strftime("%Y-%m")
    month = month if month in months else (today if today in months else (months[-1] if months else None))
    if month is None:
        return {"available": False, "month": None, "months": [], "people": []}

    # A month nobody has hours in is simply not planned yet (future forecast).
    planned: set[str] = set()
    people = []
    for ri in range(hdr + 1, len(rows)):
        row = rows[ri]
        name = row[res_col] if res_col < len(row) else None
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()
        if name.lower().startswith("sum costi"):
            break
        lc = row[lc_col] if lc_col is not None and lc_col < len(row) else None
        charg = row[charg_col] if charg_col is not None and charg_col < len(row) else None
        if classify_cost_row(name, lc, charg) != "person":
            continue
        perc = _num(charg)
        frow = frows[ri] if ri < len(frows) else []
        by_month = {}
        for ci, key, mh in cols:
            hours = _num(row[ci]) if ci < len(row) else None
            parsed = parse_hours_formula(frow[ci] if ci < len(frow) else None)
            by_month[key] = {"month": key, **_month_status(hours, mh, perc, parsed)}
            if hours:
                planned.add(key)
        people.append({"name": name, "lc": _num(lc), "perc_charg": perc, "by_month": by_month})

    for p in people:
        by_month = p.pop("by_month")
        for key, m in by_month.items():
            if key not in planned and m["status"] == "bench":
                m["status"] = "np"
        p["current"] = by_month.get(month) or {"status": "nd"}
        p["months"] = [by_month[k] for k in months]

    counts = {k: sum(1 for p in people if p["current"]["status"] == k) for k in ("ok", "bench", "over", "nd", "np")}
    counts["partial"] = sum(1 for p in people if p["current"].get("other_pct"))
    order = {"over": 0, "bench": 1, "ok": 2, "np": 3, "nd": 4}
    people.sort(key=lambda p: (order[p["current"]["status"]], p["name"].lower()))
    return {"available": True, "month": month, "months": months, "counts": counts, "people": people}


def status_by_name(month: str | None = None) -> dict[str, dict]:
    """{person name: current-month allocation} for other dashboards."""
    return {p["name"]: p["current"] for p in allocation_overview(month)["people"]}
