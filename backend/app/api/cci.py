"""CCI module API: per-contract CCI from the Contracts sheet + Sheet1 snapshot."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.models import Contract
from app.services.cci import cci_overview

router = APIRouter(prefix="/api/cci", tags=["cci"])


@router.get("")
async def get_cci(session: AsyncSession = Depends(get_session)):
    contracts = (await session.scalars(select(Contract).options(selectinload(Contract.client)))).all()
    clients = {c.id: c.client.name for c in contracts if c.client}
    return cci_overview(clients)  # served from the in-memory workbook snapshot
