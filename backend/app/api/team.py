"""Team allocation API: monthly status of each person vs their own %Charg."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import Resource
from app.services.team_allocation import allocation_overview

router = APIRouter(prefix="/api/team", tags=["team"])


@router.get("/allocation")
async def team_allocation(month: str | None = None, session: AsyncSession = Depends(get_session)):
    """Per-person allocation for ``month`` (YYYY-MM, default current) plus the FY timeline."""
    data = allocation_overview(month)
    ids = {r.name: r.id for r in (await session.scalars(select(Resource))).all()}
    for p in data["people"]:
        p["resource_id"] = ids.get(p["name"])
    return data
