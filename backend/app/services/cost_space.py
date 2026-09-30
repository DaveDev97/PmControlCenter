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
from app.services.workbook_cache import current_workbook, find_sheet, sheet_values

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
    return {
        "ratio": round(ratio, 4),
        "cci_target": settings.cci_target_threshold,
        "fys": sorted(wanted) if wanted else None,
        "totals": with_space(totals),
        "by_fy": [with_space(by_fy[k]) for k in sorted(by_fy)],
        "booked": booked_rows,
        "excel_wbs": excel_wbs_cost_space(),
    }


def excel_wbs_cost_space() -> list[dict]:
    """Cost-space rows already computed in ``Costi vs Forecast`` (e.g. "WBS Findo").

    Located below the "Spazio costi già presente" header, whose columns are
    labelled "Available" and "SpazioCosti Tot". Returned for cross-checking the
    opportunity-based figure; empty if the block is not found.
    """
    path = current_workbook()
    if path is None or not path.exists():
        return []
    try:
        rows = find_sheet(sheet_values(path), lambda t: "costi vs forecast" in t)
    except Exception:  # noqa: BLE001 - an unreadable file must not break the page
        return []
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
