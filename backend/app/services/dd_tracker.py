"""Due diligence tracking service."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import schemas
from app.models import Opportunity


async def get_opportunity_detail(
    opp_id: int, session: AsyncSession
) -> schemas.OpportunityDetail:
    """Load opportunity with all DD milestones."""
    result = await session.execute(
        select(Opportunity)
        .where(Opportunity.id == opp_id)
        .options(
            selectinload(Opportunity.due_diligences),
            selectinload(Opportunity.invoices),
        )
    )
    opp = result.scalar_one_or_none()
    if not opp:
        raise ValueError(f"Opportunity {opp_id} not found")

    return schemas.OpportunityDetail.model_validate(opp)
