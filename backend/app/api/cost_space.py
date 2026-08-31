"""Cost Space Monitor API endpoints."""
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services import cost_space

router = APIRouter()


class CostSpaceRow(BaseModel):
    resource_id: int
    resource_name: str
    chargeability: float
    loaded_cost_hourly: float
    available_hours: float
    available_cost_space: float
    allocated_hours: float
    allocated_cost_space: float
    remaining_hours: float
    remaining_cost_space: float
    utilization_pct: float
    status: str


class CostSpaceSummary(BaseModel):
    month: str
    resources: list[CostSpaceRow]
    totals: dict


class PipelineImpact(BaseModel):
    total_pipeline_value: float
    estimated_cost_space_required: float
    opportunities_count: int


@router.get("/summary", response_model=CostSpaceSummary)
async def cost_space_summary(
    month: str = "2026-08",  # Format: YYYY-MM
    session: AsyncSession = Depends(get_session),
):
    """Get cost space summary for a given month."""
    year, month_num = map(int, month.split("-"))
    month_date = date(year, month_num, 1)

    resources = await cost_space.get_cost_space_summary(month_date, session)

    # Calculate totals
    totals = {
        "available_cost_space": sum(r["available_cost_space"] for r in resources),
        "allocated_cost_space": sum(r["allocated_cost_space"] for r in resources),
        "remaining_cost_space": sum(r["remaining_cost_space"] for r in resources),
        "avg_utilization_pct": (
            sum(r["utilization_pct"] for r in resources) / len(resources)
            if resources
            else 0.0
        ),
    }

    return {
        "month": month,
        "resources": resources,
        "totals": totals,
    }


@router.get("/pipeline-impact", response_model=PipelineImpact)
async def pipeline_impact(session: AsyncSession = Depends(get_session)):
    """Get pipeline impact on cost space."""
    return await cost_space.get_pipeline_impact(session)
