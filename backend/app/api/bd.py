"""BD Tracking API: BD budget lines with the state derived from the linked opportunity."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.bd_tracking import bd_overview

router = APIRouter(prefix="/api/bd", tags=["bd"])


@router.get("")
async def list_bd(session: AsyncSession = Depends(get_session)):
    return await bd_overview(session)
