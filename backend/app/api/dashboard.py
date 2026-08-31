"""Dashboard endpoints (account / contract / team / person)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas import (
    AccountDashboard,
    ContractDashboard,
    OpportunityDetail,
    PersonDashboard,
    TeamDashboard,
)
from app.services import dashboards, dd_tracker

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/account", response_model=AccountDashboard)
async def account_dashboard(
    client_id: int | None = None,
    from_month: str | None = None,  # "2026-01"
    to_month: str | None = None,    # "2026-08"
    fy: str | None = None,          # "2026"
    session: AsyncSession = Depends(get_session)
):
    return await dashboards.build_account(
        session, client_id, from_month=from_month, to_month=to_month, fy=fy
    )


@router.get("/contract/{contract_id}", response_model=ContractDashboard)
async def contract_dashboard(
    contract_id: str,
    from_month: str | None = None,
    to_month: str | None = None,
    fy: str | None = None,
    session: AsyncSession = Depends(get_session)
):
    result = await dashboards.build_contract(
        session, contract_id, from_month=from_month, to_month=to_month, fy=fy
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Contract not found")
    return result


@router.get("/team", response_model=TeamDashboard)
async def team_dashboard(session: AsyncSession = Depends(get_session)):
    return await dashboards.build_team(session)


@router.get("/person/{resource_id}", response_model=PersonDashboard)
async def person_dashboard(
    resource_id: int, session: AsyncSession = Depends(get_session)
):
    result = await dashboards.build_person(session, resource_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return result


@router.get("/opportunity/{opp_id}", response_model=OpportunityDetail)
async def opportunity_detail(
    opp_id: int, session: AsyncSession = Depends(get_session)
):
    """Get opportunity with due diligence tracking."""
    try:
        return await dd_tracker.get_opportunity_detail(opp_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
