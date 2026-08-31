"""Time reports API."""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import schemas
from app.core.database import get_session
from app.models import Contract, Financial, Resource, TimeEntry
from app.services.time_report import generate_time_report

router = APIRouter(prefix="/api/time-reports", tags=["time-reports"])

NON_CHARGEABLE_WBS = ["Meeting Time", "Permesso", "Other Client"]


@router.get("/wbs")
async def list_wbs(session: AsyncSession = Depends(get_session)):
    """Real WBS list with budget (from the owning contract) and consumed cost.

    - budgetTotal   = contract initial_budget, else sum of contract revenues
    - budgetUsed    = sum(hours * resource loaded cost/hour) of time entries on WBS
    - budgetAvailable = max(0, total - used)
    """
    contracts = (await session.scalars(select(Contract))).all()
    financials = (await session.scalars(select(Financial))).all()
    resources = {r.id: r for r in (await session.scalars(select(Resource))).all()}
    entries = (await session.scalars(select(TimeEntry))).all()

    rev_by_contract: dict[str, float] = {}
    for f in financials:
        rev_by_contract[f.contract_id] = rev_by_contract.get(f.contract_id, 0.0) + \
            (f.revenues_actual or 0.0) + (f.revenues_forecast or 0.0)

    # WBS -> owning contract (contract-level WBS + also the wbs_l2 if present)
    wbs_contract: dict[str, Contract] = {}
    for c in contracts:
        for code in (c.wbs_l1, c.wbs_l2):
            if code:
                wbs_contract.setdefault(code, c)

    # consumed cost per WBS (hours * loaded cost/hour)
    used_by_wbs: dict[str, float] = {}
    for e in entries:
        res = resources.get(e.resource_id)
        rate = (res.loaded_cost_hourly if res and res.loaded_cost_hourly else 0.0)
        used_by_wbs[e.wbs] = used_by_wbs.get(e.wbs, 0.0) + (e.hours or 0.0) * rate

    all_wbs = set(wbs_contract) | set(used_by_wbs) | set(NON_CHARGEABLE_WBS)

    def budget_of(c: Contract | None) -> float:
        if c is None:
            return 0.0
        if c.initial_budget:
            return float(c.initial_budget)
        return round(rev_by_contract.get(c.id, 0.0), 2)

    out = []
    for wbs in sorted(all_wbs):
        c = wbs_contract.get(wbs)
        total = 0.0 if wbs in NON_CHARGEABLE_WBS else budget_of(c)
        used = round(used_by_wbs.get(wbs, 0.0), 2)
        out.append({
            "wbs": wbs,
            "contractName": c.name if c else ("Non Chargeable" if wbs in NON_CHARGEABLE_WBS else "—"),
            "budgetTotal": round(total, 2),
            "budgetUsed": used,
            "budgetAvailable": round(max(0.0, total - used), 2),
        })
    return out


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
