"""Cost balancing API."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.core.database import get_session
from app.services.cost_balancer import propose_cost_rebalancing

router = APIRouter(prefix="/api/cost-balance", tags=["cost-balance"])


@router.get("/proposal/{contract_id}", response_model=schemas.CostBalanceProposal)
async def get_proposal(contract_id: str, session: AsyncSession = Depends(get_session)):
    """Get cost rebalancing proposal for a contract."""
    return await propose_cost_rebalancing(contract_id, session)
