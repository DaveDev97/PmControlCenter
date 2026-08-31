"""Invoice CRUD API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import schemas
from app.core.database import get_session
from app.models import Invoice, Opportunity, Contract

router = APIRouter()


@router.get("", response_model=list[schemas.InvoiceOut])
async def list_invoices(
    opportunity_id: int | None = None,
    contract_id: str | None = None,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List invoices with optional filters."""
    query = select(Invoice)

    if opportunity_id:
        query = query.where(Invoice.opportunity_id == opportunity_id)
    if contract_id:
        query = query.where(Invoice.contract_id == contract_id)
    if status:
        query = query.where(Invoice.status == status)

    query = query.order_by(Invoice.invoice_date.desc())
    result = await session.execute(query)
    return result.scalars().all()


@router.post("", response_model=schemas.InvoiceOut)
async def create_invoice(
    data: schemas.InvoiceCreate, session: AsyncSession = Depends(get_session)
):
    """Create new invoice."""
    # Validate opportunity or contract exists
    if data.opportunity_id:
        opp_result = await session.execute(
            select(Opportunity).where(Opportunity.id == data.opportunity_id)
        )
        if not opp_result.scalar_one_or_none():
            raise HTTPException(404, f"Opportunity {data.opportunity_id} not found")

    if data.contract_id:
        contract_result = await session.execute(
            select(Contract).where(Contract.id == data.contract_id)
        )
        if not contract_result.scalar_one_or_none():
            raise HTTPException(404, f"Contract {data.contract_id} not found")

    invoice = Invoice(**data.model_dump())
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return invoice


@router.get("/{invoice_id}", response_model=schemas.InvoiceOut)
async def get_invoice(invoice_id: int, session: AsyncSession = Depends(get_session)):
    """Get invoice by ID."""
    result = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return invoice


@router.patch("/{invoice_id}", response_model=schemas.InvoiceOut)
async def update_invoice(
    invoice_id: int,
    data: schemas.InvoiceUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update invoice."""
    result = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)

    await session.commit()
    await session.refresh(invoice)
    return invoice


@router.delete("/{invoice_id}")
async def delete_invoice(invoice_id: int, session: AsyncSession = Depends(get_session)):
    """Delete invoice."""
    result = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    await session.delete(invoice)
    await session.commit()
    return {"ok": True}
