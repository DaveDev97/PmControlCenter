"""Cost Space services.

Two distinct views:

* **Cost Space bookato** (opportunity based): the cost budget unlocked by booked
  work, ``Revenues × (1 - CCI target)`` summed over opportunities whose MMS
  Status is ``CloseWon`` or ``3B``. The pipeline figure includes every open
  opportunity, so the delta shows how much depends on unconfirmed deals.
* **Allocazione risorse** (resource based): the ``%Charg`` of each person as
  written in the ``Costi vs Forecast`` sheet. Over-allocation means
  ``%Charg > 100%``; nothing is inferred from synthetic allocations.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Opportunity, Resource
from app.services.excel_reader import fy_label
from app.services.workbook_cache import cached_sheets, find_sheet

BOOKED_MMS = {"closewon", "3b"}
ALLOC_HIGH = 0.80  # > 80% -> yellow
ALLOC_OVER = 1.00  # > 100% -> red (real over-allocation)


def cost_space_ratio() -> float:
    """Share of revenue available for costs: 1 - CCI target (35% -> 0.65)."""
    return 1.0 - settings.cci_target_threshold


def is_booked(mms_status: str | None) -> bool:
    return (mms_status or "").strip().lower() in BOOKED_MMS


def allocation_status(perc_charg: float | None) -> str:
    """'ok' (<= 80%), 'high' (80-100%], 'over' (> 100%) or 'nd' when %Charg is missing."""
    if perc_charg is None:
        return "nd"
    if perc_charg > ALLOC_OVER:
        return "over"
    if perc_charg > ALLOC_HIGH:
        return "high"
    return "ok"


def calculate_working_hours_per_month(month: date) -> float:
    """Billable working hours for a month (20 days x 8h)."""
    return settings.working_days_per_month * 8.0


async def get_cost_space_summary(month: date, session: AsyncSession) -> list[dict]:
    """Per-resource allocation from ``%Charg`` plus the monthly cost it implies."""
    resources = (
        await session.scalars(select(Resource).where(Resource.status == "active"))
    ).all()
    hours = calculate_working_hours_per_month(month)
    sheet = excel_monthly_costs() or {"people": {}}
    key = month.strftime("%Y-%m")
    rows = []
    for res in resources:
        lc = res.loaded_cost_hourly if res.loaded_cost_hourly else res.daily_rate / 8.0
        perc = res.perc_charg
        charged_hours = hours * perc if perc is not None else None
        rows.append({
            "resource_id": res.id,
            "resource_name": res.name,
            "loaded_cost_hourly": round(lc, 2),
            "perc_charg": perc,
            "charged_hours": round(charged_hours, 1) if charged_hours is not None else None,
            "monthly_cost": round(charged_hours * lc, 2) if charged_hours is not None else None,
            "sheet_cost": sheet["people"].get(res.name, {}).get(key),  # "costo €" of the month in Excel
            "status": allocation_status(perc),
        })
    priority = {"over": 0, "high": 1, "ok": 2, "nd": 3}
    rows.sort(key=lambda r: (priority[r["status"]], r["resource_name"].lower()))
    return rows


async def get_booked_cost_space(session: AsyncSession, fys: list[str] | None = None) -> dict:
    """Cost Space bookato vs pipeline, optionally restricted to some FYs (e.g. ["FY26", "FY27"])."""
    ratio = cost_space_ratio()
    opps = (await session.scalars(select(Opportunity))).all()
    wanted = {f.upper() for f in fys} if fys else None

    by_fy: dict[str, dict] = {}
    booked_rows = []
    totals = {"booked_revenue": 0.0, "pipeline_revenue": 0.0, "booked_count": 0, "pipeline_count": 0}
    for o in opps:
        fy = fy_label(o.fiscal_year) or "N/D"
        if wanted is not None and fy not in wanted:
            continue
        if o.stage == "CloseLost":
            continue
        value = o.estimated_value or 0.0
        bucket = by_fy.setdefault(fy, {"fy": fy, "booked_revenue": 0.0, "pipeline_revenue": 0.0,
                                       "booked_count": 0, "pipeline_count": 0})
        bucket["pipeline_revenue"] += value
        bucket["pipeline_count"] += 1
        totals["pipeline_revenue"] += value
        totals["pipeline_count"] += 1
        if is_booked(o.mms_status):
            bucket["booked_revenue"] += value
            bucket["booked_count"] += 1
            totals["booked_revenue"] += value
            totals["booked_count"] += 1
            booked_rows.append({
                "id": o.id, "name": o.name, "fy": fy, "mms_status": o.mms_status,
                "revenues": round(value, 2), "cost_space": round(value * ratio, 2),
            })

    def with_space(d: dict) -> dict:
        d["booked_cost_space"] = round(d["booked_revenue"] * ratio, 2)
        d["pipeline_cost_space"] = round(d["pipeline_revenue"] * ratio, 2)
        d["delta_cost_space"] = round(d["pipeline_cost_space"] - d["booked_cost_space"], 2)
        d["booked_revenue"] = round(d["booked_revenue"], 2)
        d["pipeline_revenue"] = round(d["pipeline_revenue"], 2)
        return d

    booked_rows.sort(key=lambda r: -r["revenues"])
    costs = planned_costs(sorted(wanted) if wanted else None)
    return {
        "planned_costs": costs,
        "ratio": round(ratio, 4),
        "cci_target": settings.cci_target_threshold,
        "fys": sorted(wanted) if wanted else None,
        "totals": with_space(totals),
        "by_fy": [with_space(by_fy[k]) for k in sorted(by_fy)],
        "booked": booked_rows,
        "excel_wbs": excel_wbs_cost_space(),
    }


_MONTHS_IT = {"gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6, "lug": 7, "ago": 8,
              "set": 9, "sett": 9, "ott": 10, "otto": 10, "nov": 11, "dic": 12}


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def excel_monthly_costs() -> dict | None:
    """Monthly costs of the ``Costi vs Forecast`` resource table.

    Layout: a row of FY labels ("FY25", "FY26"...), a row of month names
    ("sett", "otto", "nov"...) above each hours column, then the "Resource" header
    row; each month is an (hours, "costo €") column pair. Rows run until
    "SUM costi". People and other cost lines (subcontracts, "Unicredit",
    "PMO Account"...) are split with :func:`classify_cost_row`; both are real
    costs and together make up the sheet's "SUM costi".

    Returns ``{"months": [...], "people": {name: {month: cost}},
    "other": [{"name", "total", "months": {month: cost}}], "sum_costi": {month: cost}}``.
    """
    from app.services.excel_reader import classify_cost_row

    rows = find_sheet(cached_sheets(), lambda t: "costi vs forecast" in t)
    if not rows:
        return None
    hdr = res_col = None
    for ri, row in enumerate(rows):
        if "Resource" in [v.strip() if isinstance(v, str) else v for v in row]:
            hdr = ri
            res_col = next(i for i, v in enumerate(row) if isinstance(v, str) and v.strip() == "Resource")
            break
    if hdr is None:
        return None
    labels = [(v.strip().lower() if isinstance(v, str) else "") for v in rows[hdr]]
    lc_col = labels.index("lc") if "lc" in labels else None
    charg_col = next((i for i, v in enumerate(labels) if v.startswith("%charg")), None)

    # FY label row and month-name row sit above the header.
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
    cost_cols: list[tuple[int, str]] = []
    for ci, v in enumerate(month_row):
        m = _MONTHS_IT.get(v.strip().lower()) if isinstance(v, str) else None
        fy = next((y for c, y in reversed(fy_cols) if c <= ci), None)
        if m is None or fy is None:
            continue
        year = fy - 1 if m >= 9 else fy
        col = ci + 1 if ci + 1 < len(labels) and labels[ci + 1].startswith("costo") else ci
        cost_cols.append((col, f"{year:04d}-{m:02d}"))

    def monthly(row) -> dict[str, float]:
        out = {}
        for col, key in cost_cols:
            v = _num(row[col]) if col < len(row) else None
            if v:
                out[key] = round(v, 2)
        return out

    people: dict[str, dict[str, float]] = {}
    other: list[dict] = []
    sum_costi: dict[str, float] = {}
    for row in rows[hdr + 1:]:
        name = row[res_col] if res_col < len(row) else None
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()
        if name.lower().startswith("sum costi"):
            sum_costi = monthly(row)
            break
        lc = row[lc_col] if lc_col is not None and lc_col < len(row) else None
        charg = row[charg_col] if charg_col is not None and charg_col < len(row) else None
        kind = classify_cost_row(name, lc, charg)
        if kind == "person":
            people.setdefault(name, monthly(row))
        elif kind == "cost":
            months = monthly(row)
            other.append({"name": name, "total": _num(lc) if _num(lc) is not None else round(sum(months.values()), 2),
                          "months": months})
    return {"months": [k for _, k in cost_cols], "people": people, "other": other, "sum_costi": sum_costi}


def fy_of_month(month: str) -> str:
    """'2026-09' -> 'FY27' (FY runs September-August)."""
    y, m = int(month[:4]), int(month[5:7])
    return f"FY{str(y + 1 if m >= 9 else y)[-2:]}"


def planned_costs(fys: list[str] | None, today: date | None = None) -> dict | None:
    """Costs planned in the selected FYs: people + other cost lines (= SUM costi)."""
    data = excel_monthly_costs()
    if data is None:
        return None
    wanted = {f.upper() for f in fys} if fys else None
    now = (today or date.today()).strftime("%Y-%m")

    def in_scope(m: str) -> bool:
        return wanted is None or fy_of_month(m) in wanted

    people_total = sum(v for months in data["people"].values() for m, v in months.items() if in_scope(m))
    other_rows = []
    for o in data["other"]:
        by_fy: dict[str, float] = {}
        for m, v in o["months"].items():
            by_fy[fy_of_month(m)] = round(by_fy.get(fy_of_month(m), 0.0) + v, 2)
        other_rows.append({
            "name": o["name"],
            "total": o["total"],
            "by_fy": by_fy,
            "in_scope": round(sum(v for m, v in o["months"].items() if in_scope(m)), 2),
            "remaining": round(sum(v for m, v in o["months"].items() if m >= now), 2),
        })
    other_total = sum(o["in_scope"] for o in other_rows)
    return {
        "people": round(people_total, 2),
        "other": round(other_total, 2),
        "total": round(people_total + other_total, 2),
        "sum_costi_sheet": round(sum(v for m, v in data["sum_costi"].items() if in_scope(m)), 2),
        "other_rows": other_rows,
    }


def excel_wbs_cost_space() -> list[dict]:
    """Cost-space rows already computed in ``Costi vs Forecast`` (e.g. "WBS Findo").

    Located below the "Spazio costi già presente" header, whose columns are
    labelled "Available" and "SpazioCosti Tot". Returned for cross-checking the
    opportunity-based figure; empty if the block is not found.
    """
    rows = find_sheet(cached_sheets(), lambda t: "costi vs forecast" in t)
    if not rows:
        return []
    out: list[dict] = []
    in_block = False
    avail_col = tot_col = None
    for row in rows:
        labels = [str(v).strip().lower() if isinstance(v, str) else None for v in row]
        if "available" in labels:
            in_block = True
            avail_col = labels.index("available")
            tot_col = next((i for i, v in enumerate(labels) if v and v.startswith("spaziocosti")), None)
            continue
        if not in_block:
            continue
        name_col = avail_col - 1 if avail_col else None
        name = row[name_col] if name_col is not None and name_col < len(row) else None
        if not isinstance(name, str):
            continue
        low = name.strip().lower()
        if low.startswith("sum spazio"):
            break
        if low.startswith("wbs"):
            avail = row[avail_col] if avail_col < len(row) else None
            tot = row[tot_col] if tot_col is not None and tot_col < len(row) else None
            out.append({
                "label": name.strip(),
                "available": float(avail) if isinstance(avail, (int, float)) else None,
                "total": float(tot) if isinstance(tot, (int, float)) else None,
            })
    return out
