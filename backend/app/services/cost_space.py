"""Cost Space tracking service per documento operativo.

Spazio Costi = ore mensili × chargeability × loaded_cost
Confronto: disponibile vs allocato vs remaining
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Resource, Allocation, Contract
from app.core.config import settings


def calculate_working_hours_per_month(month: date) -> float:
    """Calculate billable working hours for a given month (typically ~160 hours = 20 days * 8h)."""
    return settings.working_days_per_month * 8.0


async def get_cost_space_summary(
    month: date, session: AsyncSession
) -> list[dict]:
    """Calculate cost space summary for all active resources for a given month.

    Returns list of:
    {
        "resource_id": int,
        "resource_name": str,
        "chargeability": float,
        "loaded_cost_hourly": float,
        "available_hours": float,  # working_hours * chargeability
        "available_cost_space": float,  # available_hours * loaded_cost
        "allocated_hours": float,  # sum of allocations
        "allocated_cost_space": float,  # allocated_hours * loaded_cost
        "remaining_hours": float,
        "remaining_cost_space": float,
        "utilization_pct": float,  # allocated / available
        "status": str  # "overallocated" | "full" | "partial" | "available"
    }
    """
    # Load all active resources
    result = await session.execute(
        select(Resource)
        .where(Resource.status == "active")
        .options(selectinload(Resource.allocations))
    )
    resources = result.scalars().all()

    summary = []
    for res in resources:
        # Calculate available space
        working_hours = calculate_working_hours_per_month(month)
        chargeability = res.chargeability if res.chargeability else 0.80  # Default 80%
        loaded_cost = res.loaded_cost_hourly if res.loaded_cost_hourly else res.daily_rate / 8.0

        available_hours = working_hours * chargeability
        available_cost_space = available_hours * loaded_cost

        # Calculate allocated space for this month
        allocated_hours = 0.0
        for alloc in res.allocations:
            # Check if allocation is active in this month
            if alloc.start_date and month < date(alloc.start_date.year, alloc.start_date.month, 1):
                continue
            if alloc.end_date and month > date(alloc.end_date.year, alloc.end_date.month, 1):
                continue

            # Convert days_per_month to hours (1 day = 8 hours)
            allocated_hours += alloc.days_per_month * 8.0

        allocated_cost_space = allocated_hours * loaded_cost

        # Calculate remaining
        remaining_hours = available_hours - allocated_hours
        remaining_cost_space = available_cost_space - allocated_cost_space
        utilization_pct = (allocated_hours / available_hours) if available_hours > 0 else 0.0

        # Determine status
        if utilization_pct > 1.0:
            status = "overallocated"
        elif utilization_pct >= settings.util_full_threshold:  # >= 80%
            status = "full"
        elif utilization_pct >= settings.util_bench_threshold:  # >= 50%
            status = "partial"
        else:
            status = "available"

        summary.append({
            "resource_id": res.id,
            "resource_name": res.name,
            "chargeability": chargeability,
            "loaded_cost_hourly": loaded_cost,
            "available_hours": round(available_hours, 2),
            "available_cost_space": round(available_cost_space, 2),
            "allocated_hours": round(allocated_hours, 2),
            "allocated_cost_space": round(allocated_cost_space, 2),
            "remaining_hours": round(remaining_hours, 2),
            "remaining_cost_space": round(remaining_cost_space, 2),
            "utilization_pct": round(utilization_pct, 4),
            "status": status,
        })

    # Sort by status priority (overallocated first, then by name)
    status_priority = {"overallocated": 0, "full": 1, "partial": 2, "available": 3}
    summary.sort(key=lambda x: (status_priority.get(x["status"], 999), x["resource_name"]))

    return summary


async def get_pipeline_impact(session: AsyncSession) -> dict:
    """Calculate cost space impact of pipeline opportunities.

    Returns:
    {
        "total_pipeline_value": float,
        "estimated_cost_space_required": float,
        "opportunities_count": int,
    }
    """
    # Placeholder: in real implementation, sum estimated_value from Opportunity
    # where stage in ("Qualified", "Proposal") and calculate cost space needed
    # based on opportunity size and team composition

    from app.models import Opportunity

    result = await session.execute(
        select(Opportunity).where(
            Opportunity.stage.in_(["Qualified", "Proposal"])
        )
    )
    opportunities = result.scalars().all()

    total_value = sum(opp.estimated_value for opp in opportunities)

    # Assume 65% of revenue goes to costs (inverse of 35% CI target)
    estimated_costs = total_value * 0.65

    return {
        "total_pipeline_value": round(total_value, 2),
        "estimated_cost_space_required": round(estimated_costs, 2),
        "opportunities_count": len(opportunities),
    }
