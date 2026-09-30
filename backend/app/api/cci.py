"""CCI module API: per-contract CCI from the Contracts sheet + Sheet1 snapshot."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
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
    try:
        return await run_in_threadpool(cci_overview, clients)
    except OSError as exc:
        raise HTTPException(503, f"File Excel non leggibile: {exc}") from exc
