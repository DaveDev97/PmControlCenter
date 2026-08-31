"""CRUD endpoints for clients, contracts, opportunities, resources, allocations."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.models import (
    Allocation,
    Client,
    Contract,
    Opportunity,
    Resource,
    Role,
)
from app.schemas import (
    AllocationCreate,
    AllocationOut,
    AllocationUpdate,
    ClientCreate,
    ClientOut,
    ContractCreate,
    ContractOut,
    ContractUpdate,
    OpportunityCreate,
    OpportunityOut,
    OpportunityUpdate,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
    RoleOut,
)

router = APIRouter(prefix="/api", tags=["crud"])


# ---------------- Clients ----------------
@router.get("/clients", response_model=list[ClientOut])
async def list_clients(session: AsyncSession = Depends(get_session)):
    return (await session.scalars(select(Client).order_by(Client.name))).all()


@router.post("/clients", response_model=ClientOut, status_code=201)
async def create_client(payload: ClientCreate, session: AsyncSession = Depends(get_session)):
    obj = Client(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


# ---------------- Roles ----------------
@router.get("/roles", response_model=list[RoleOut])
async def list_roles(session: AsyncSession = Depends(get_session)):
    return (await session.scalars(select(Role).order_by(Role.name))).all()


# ---------------- Contracts ----------------
def _contract_out(c: Contract) -> ContractOut:
    data = {k: getattr(c, k) for k in ContractOut.model_fields if k != "client_name"}
    data["client_name"] = c.client.name if c.client else None
    return ContractOut(**data)


@router.get("/contracts", response_model=list[ContractOut])
async def list_contracts(
    client_id: int | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    q = select(Contract).options(selectinload(Contract.client)).order_by(Contract.id)
    if client_id is not None:
        q = q.where(Contract.client_id == client_id)
    if status is not None:
        q = q.where(Contract.status == status)
    rows = (await session.scalars(q)).all()
    return [_contract_out(c) for c in rows]


@router.get("/contracts/{contract_id}", response_model=ContractOut)
async def get_contract(contract_id: str, session: AsyncSession = Depends(get_session)):
    c = await session.get(Contract, contract_id, options=[selectinload(Contract.client)])
    if c is None:
        raise HTTPException(404, "Contract not found")
    return _contract_out(c)


@router.post("/contracts", response_model=ContractOut, status_code=201)
async def create_contract(payload: ContractCreate, session: AsyncSession = Depends(get_session)):
    if await session.get(Contract, payload.id):
        raise HTTPException(409, "Contract id already exists")
    obj = Contract(**payload.model_dump())
    session.add(obj)
    await session.commit()
    c = await session.get(Contract, obj.id, options=[selectinload(Contract.client)])
    return _contract_out(c)


@router.put("/contracts/{contract_id}", response_model=ContractOut)
async def update_contract(
    contract_id: str, payload: ContractUpdate, session: AsyncSession = Depends(get_session)
):
    c = await session.get(Contract, contract_id, options=[selectinload(Contract.client)])
    if c is None:
        raise HTTPException(404, "Contract not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    await session.commit()
    await session.refresh(c)
    return _contract_out(c)


@router.delete("/contracts/{contract_id}", status_code=204)
async def delete_contract(contract_id: str, session: AsyncSession = Depends(get_session)):
    c = await session.get(Contract, contract_id)
    if c is None:
        raise HTTPException(404, "Contract not found")
    # Soft delete = mark closed (keeps financial history).
    c.status = "closed"
    await session.commit()


# ---------------- Opportunities ----------------
@router.get("/opportunities", response_model=list[OpportunityOut])
async def list_opportunities(
    contract_id: str | None = None,
    stage: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    q = select(Opportunity).order_by(Opportunity.close_date)
    if contract_id is not None:
        q = q.where(Opportunity.contract_id == contract_id)
    if stage is not None:
        q = q.where(Opportunity.stage == stage)
    return (await session.scalars(q)).all()


@router.post("/opportunities", response_model=OpportunityOut, status_code=201)
async def create_opportunity(
    payload: OpportunityCreate, session: AsyncSession = Depends(get_session)
):
    obj = Opportunity(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.put("/opportunities/{opp_id}", response_model=OpportunityOut)
async def update_opportunity(
    opp_id: int, payload: OpportunityUpdate, session: AsyncSession = Depends(get_session)
):
    o = await session.get(Opportunity, opp_id)
    if o is None:
        raise HTTPException(404, "Opportunity not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(o, k, v)
    await session.commit()
    await session.refresh(o)
    return o


@router.delete("/opportunities/{opp_id}", status_code=204)
async def delete_opportunity(opp_id: int, session: AsyncSession = Depends(get_session)):
    o = await session.get(Opportunity, opp_id)
    if o is None:
        raise HTTPException(404, "Opportunity not found")
    await session.delete(o)
    await session.commit()


# ---------------- Resources ----------------
def _resource_out(r: Resource) -> ResourceOut:
    data = {k: getattr(r, k) for k in ResourceOut.model_fields if k != "role_name"}
    data["role_name"] = r.role.name if r.role else None
    return ResourceOut(**data)


@router.get("/resources", response_model=list[ResourceOut])
async def list_resources(session: AsyncSession = Depends(get_session)):
    rows = (
        await session.scalars(
            select(Resource).options(selectinload(Resource.role)).order_by(Resource.name)
        )
    ).all()
    return [_resource_out(r) for r in rows]


@router.post("/resources", response_model=ResourceOut, status_code=201)
async def create_resource(payload: ResourceCreate, session: AsyncSession = Depends(get_session)):
    obj = Resource(**payload.model_dump())
    session.add(obj)
    await session.commit()
    r = await session.get(Resource, obj.id, options=[selectinload(Resource.role)])
    return _resource_out(r)


@router.put("/resources/{resource_id}", response_model=ResourceOut)
async def update_resource(
    resource_id: int, payload: ResourceUpdate, session: AsyncSession = Depends(get_session)
):
    r = await session.get(Resource, resource_id, options=[selectinload(Resource.role)])
    if r is None:
        raise HTTPException(404, "Resource not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    await session.commit()
    await session.refresh(r)
    return _resource_out(r)


@router.delete("/resources/{resource_id}", status_code=204)
async def delete_resource(resource_id: int, session: AsyncSession = Depends(get_session)):
    r = await session.get(Resource, resource_id)
    if r is None:
        raise HTTPException(404, "Resource not found")
    await session.delete(r)
    await session.commit()


# ---------------- Allocations ----------------
def _allocation_out(a: Allocation) -> AllocationOut:
    rate = a.resource.daily_rate if a.resource else 0.0
    data = {
        k: getattr(a, k)
        for k in AllocationOut.model_fields
        if k not in ("resource_name", "contract_name", "monthly_cost")
    }
    data["resource_name"] = a.resource.name if a.resource else None
    data["contract_name"] = a.contract.name if a.contract else None
    data["monthly_cost"] = round(a.days_per_month * rate, 2)
    return AllocationOut(**data)


@router.get("/allocations", response_model=list[AllocationOut])
async def list_allocations(
    resource_id: int | None = None,
    contract_id: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    q = select(Allocation).options(
        selectinload(Allocation.resource), selectinload(Allocation.contract)
    )
    if resource_id is not None:
        q = q.where(Allocation.resource_id == resource_id)
    if contract_id is not None:
        q = q.where(Allocation.contract_id == contract_id)
    rows = (await session.scalars(q)).all()
    return [_allocation_out(a) for a in rows]


@router.post("/allocations", response_model=AllocationOut, status_code=201)
async def create_allocation(
    payload: AllocationCreate, session: AsyncSession = Depends(get_session)
):
    if not await session.get(Resource, payload.resource_id):
        raise HTTPException(400, "Resource does not exist")
    if not await session.get(Contract, payload.contract_id):
        raise HTTPException(400, "Contract does not exist")
    obj = Allocation(**payload.model_dump())
    session.add(obj)
    await session.commit()
    a = await session.get(
        Allocation,
        obj.id,
        options=[selectinload(Allocation.resource), selectinload(Allocation.contract)],
    )
    return _allocation_out(a)


@router.put("/allocations/{alloc_id}", response_model=AllocationOut)
async def update_allocation(
    alloc_id: int, payload: AllocationUpdate, session: AsyncSession = Depends(get_session)
):
    a = await session.get(
        Allocation,
        alloc_id,
        options=[selectinload(Allocation.resource), selectinload(Allocation.contract)],
    )
    if a is None:
        raise HTTPException(404, "Allocation not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    await session.commit()
    await session.refresh(a)
    return _allocation_out(a)


@router.delete("/allocations/{alloc_id}", status_code=204)
async def delete_allocation(alloc_id: int, session: AsyncSession = Depends(get_session)):
    a = await session.get(Allocation, alloc_id)
    if a is None:
        raise HTTPException(404, "Allocation not found")
    await session.delete(a)
    await session.commit()
