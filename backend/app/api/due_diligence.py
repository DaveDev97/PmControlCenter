"""Due Diligence tracking API."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.core.config import settings
from app.core.database import get_session
from app.dd_templates import get_template_by_type, DD_TEMPLATE_SECURITY
from app.models import DueDiligence, Opportunity
from app.services.overlay_manager import OverlayManager

router = APIRouter(prefix="/api", tags=["due-diligence"])


@router.get(
    "/opportunities/{opp_id}/due-diligence", response_model=list[schemas.DueDiligenceOut]
)
async def list_dd_for_opportunity(
    opp_id: int, session: AsyncSession = Depends(get_session)
):
    """List all due diligence items for an opportunity."""
    result = await session.execute(
        select(DueDiligence).where(DueDiligence.opportunity_id == opp_id)
    )
    return result.scalars().all()


@router.post(
    "/opportunities/{opp_id}/due-diligence",
    response_model=schemas.DueDiligenceOut,
    status_code=201,
)
async def create_dd(
    opp_id: int, dd: schemas.DueDiligenceCreate, session: AsyncSession = Depends(get_session)
):
    """Create a new due diligence item."""
    db_dd = DueDiligence(**dd.model_dump())
    session.add(db_dd)
    await session.commit()
    await session.refresh(db_dd)
    return db_dd


@router.put("/due-diligence/{dd_id}", response_model=schemas.DueDiligenceOut)
async def update_dd(
    dd_id: int,
    updates: schemas.DueDiligenceUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update due diligence status/completion."""
    result = await session.execute(select(DueDiligence).where(DueDiligence.id == dd_id))
    dd = result.scalar_one_or_none()
    if not dd:
        raise HTTPException(status_code=404, detail="Due diligence item not found")

    changes = updates.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(dd, key, value)

    await session.commit()
    await session.refresh(dd)

    # Persist the edit to the shared overlay so it survives a data refresh.
    if settings.data_folder:
        OverlayManager(settings.data_folder).record_dd_update(dd_id, changes)
    return dd


class ApplyTemplateRequest(BaseModel):
    template_type: str = "standard"  # standard, fast-track, extension
    start_date: date | None = None  # Auto-calculate due dates from this


@router.post("/opportunities/{opp_id}/due-diligence/apply-template")
async def apply_dd_template(
    opp_id: int,
    request: ApplyTemplateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Apply a DD template to an opportunity, creating all sequential steps."""

    # Verify opportunity exists
    opp_result = await session.execute(
        select(Opportunity).where(Opportunity.id == opp_id)
    )
    opportunity = opp_result.scalar_one_or_none()
    if not opportunity:
        raise HTTPException(404, f"Opportunity {opp_id} not found")

    # Get template
    template = get_template_by_type(request.template_type)

    # Delete existing DD items for this opportunity
    existing = await session.execute(
        select(DueDiligence).where(DueDiligence.opportunity_id == opp_id)
    )
    for item in existing.scalars():
        await session.delete(item)

    # Calculate start date
    start_date = request.start_date or date.today()
    current_date = start_date

    # Create DD items from template
    created_items = []
    for step in template:
        # Calculate due date based on typical duration
        duration = step.get("typical_duration_days", 5)
        due_date = current_date + timedelta(days=duration)

        dd_item = DueDiligence(
            opportunity_id=opp_id,
            milestone=step["milestone"],
            step_order=step["step_order"],
            status="pending",
            is_mandatory=step.get("is_mandatory", True),
            depends_on_step=step.get("depends_on_step"),
            assigned_to=step.get("assigned_role"),
            due_date=due_date,
            notes=step.get("description"),
        )
        session.add(dd_item)
        created_items.append(dd_item)

        # Next step starts after this one completes
        current_date = due_date

    await session.commit()

    return {
        "success": True,
        "template_type": request.template_type,
        "steps_created": len(created_items),
        "estimated_total_days": (current_date - start_date).days,
        "estimated_completion": current_date.isoformat(),
    }


@router.get("/opportunities/{opp_id}/due-diligence/progress")
async def get_dd_progress(
    opp_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get DD completion progress for an opportunity."""

    result = await session.execute(
        select(DueDiligence)
        .where(DueDiligence.opportunity_id == opp_id)
        .order_by(DueDiligence.step_order)
    )
    items = result.scalars().all()

    if not items:
        return {
            "total_steps": 0,
            "completed_steps": 0,
            "progress_pct": 0,
            "current_step": None,
            "blocked_steps": 0,
        }

    completed = sum(1 for item in items if item.status == "completed")
    blocked = sum(1 for item in items if item.status == "blocked")
    mandatory = [item for item in items if item.is_mandatory]
    mandatory_completed = sum(1 for item in mandatory if item.status == "completed")

    # Find current step (first non-completed)
    current = next((item for item in items if item.status != "completed"), None)

    return {
        "total_steps": len(items),
        "completed_steps": completed,
        "progress_pct": round(completed / len(items) * 100, 1) if items else 0,
        "mandatory_steps": len(mandatory),
        "mandatory_completed": mandatory_completed,
        "mandatory_progress_pct": round(mandatory_completed / len(mandatory) * 100, 1) if mandatory else 0,
        "current_step": current.milestone if current else "All completed",
        "current_step_due": current.due_date.isoformat() if current and current.due_date else None,
        "blocked_steps": blocked,
        "status": "completed" if completed == len(items) else "in_progress" if completed > 0 else "not_started",
    }
