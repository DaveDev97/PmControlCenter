"""Cost Space Monitor API endpoints."""
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services import cost_space

router = APIRouter()


class AllocationRow(BaseModel):
    resource_id: int
    resource_name: str
    loaded_cost_hourly: float
    perc_charg: float | None
    charged_hours: float | None
    monthly_cost: float | None
    status: str  # ok | high | over | nd


class CostSpaceSummary(BaseModel):
    month: str
    resources: list[AllocationRow]
    totals: dict


@router.get("/summary", response_model=CostSpaceSummary)
async def cost_space_summary(
    month: str | None = None,  # Format: YYYY-MM (default: current month)
    session: AsyncSession = Depends(get_session),
):
    """Resource allocation (%Charg from Excel) for a given month."""
    today = date.today()
    year, month_num = map(int, month.split("-")) if month else (today.year, today.month)
    resources = await cost_space.get_cost_space_summary(date(year, month_num, 1), session)
    known = [r["perc_charg"] for r in resources if r["perc_charg"] is not None]
    totals = {
        "monthly_cost": round(sum(r["monthly_cost"] or 0 for r in resources), 2),
        "avg_perc_charg": round(sum(known) / len(known), 4) if known else None,
        "over": sum(r["status"] == "over" for r in resources),
        "high": sum(r["status"] == "high" for r in resources),
        "ok": sum(r["status"] == "ok" for r in resources),
        "nd": sum(r["status"] == "nd" for r in resources),
    }
    return {"month": f"{year:04d}-{month_num:02d}", "resources": resources, "totals": totals}


@router.get("/booked")
async def booked_cost_space(fy: str | None = None, session: AsyncSession = Depends(get_session)):
    """Cost Space bookato (CloseWon + 3B) vs pipeline. ``fy`` = comma list, e.g. "FY26,FY27"."""
    fys = [f.strip() for f in fy.split(",") if f.strip()] if fy else None
    return await cost_space.get_booked_cost_space(session, fys)
