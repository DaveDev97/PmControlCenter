"""Time report service - Excel export in CHG format."""
from io import BytesIO

import openpyxl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import schemas
from app.models import Resource, TimeEntry


async def generate_time_report(
    request: schemas.TimeReportRequest, session: AsyncSession
) -> BytesIO:
    """
    Generate CHG Excel report from time entries.

    Format: TR | Resource ID | Ore | WBS | Tipologia
    Example: 2Q | paolo.zinzi | 83.2 | B7PMH002 | Chargeable
    """
    # Query time entries filtered by period + optional resources
    query = select(TimeEntry).where(TimeEntry.period == request.period)

    if request.resource_ids:
        query = query.where(TimeEntry.resource_id.in_(request.resource_ids))

    query = query.options(selectinload(TimeEntry.resource))
    result = await session.execute(query)
    entries = result.scalars().all()

    # Create Excel workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"CHG_{request.period}"

    # Header row
    ws.append(["TR", "Resource ID", "Ore", "WBS", "Tipologia"])

    # Data rows
    for entry in entries:
        # Resource ID = email or name in lowercase with dots
        resource_id = (
            entry.resource.email.split("@")[0]
            if entry.resource.email
            else entry.resource.name.lower().replace(" ", ".")
        )

        ws.append(
            [
                entry.period,  # TR
                resource_id,  # Resource ID
                entry.hours,  # Ore
                entry.wbs,  # WBS
                entry.type,  # Tipologia (Chargeable/Not Chargeable)
            ]
        )

    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
