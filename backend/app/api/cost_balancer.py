"""Cost Balancer API: usable cost space per contract at the CCI target."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.models import Contract
from app.services.cost_balancer import balance_overview

router = APIRouter(prefix="/api/cost-balance", tags=["cost-balance"])


@router.get("")
async def cost_balance(fy: str | None = None, session: AsyncSession = Depends(get_session)):
    """Costs/revenue allocated, CCI vs target and residual usable cost space (``fy`` e.g. "FY27")."""
    contracts = (await session.scalars(select(Contract).options(selectinload(Contract.client)))).all()
    clients = {c.id: c.client.name for c in contracts if c.client}
    return balance_overview(clients, fy)
