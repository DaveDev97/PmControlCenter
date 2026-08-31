"""Time reports API."""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import schemas
from app.core.database import get_session
from app.models import TimeEntry
from app.services.time_report import generate_time_report

router = APIRouter(prefix="/api/time-reports", tags=["time-reports"])


@router.get("/entries", response_model=list[schemas.TimeEntryOut])
async def list_time_entries(
    period: str | None = None,
    resource_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List time entries with optional filters."""
    query = select(TimeEntry).options(selectinload(TimeEntry.resource))

    if period:
        query = query.where(TimeEntry.period == period)
    if resource_id:
        query = query.where(TimeEntry.resource_id == resource_id)

    result = await session.execute(query)
    entries = result.scalars().all()

    # Populate resource_name
    return [
        schemas.TimeEntryOut(
            **{**entry.__dict__, "resource_name": entry.resource.name}
        )
        for entry in entries
    ]


@router.post("/generate")
async def generate_report(
    request: schemas.TimeReportRequest, session: AsyncSession = Depends(get_session)
):
    """Generate and download CHG Excel report."""
    excel_data = await generate_time_report(request, session)
    return StreamingResponse(
        excel_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=CHG_{request.period}.xlsx"},
    )
