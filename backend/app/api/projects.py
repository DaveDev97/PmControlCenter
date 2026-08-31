"""Project CRUD API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.core.database import get_session
from app.models import Project

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[schemas.ProjectOut])
async def list_projects(
    contract_id: str | None = None, session: AsyncSession = Depends(get_session)
):
    """List all projects, optionally filtered by contract."""
    query = select(Project)
    if contract_id:
        query = query.where(Project.contract_id == contract_id)
    result = await session.execute(query)
    return result.scalars().all()


@router.post("", response_model=schemas.ProjectOut, status_code=201)
async def create_project(
    project: schemas.ProjectCreate, session: AsyncSession = Depends(get_session)
):
    """Create a new project."""
    db_project = Project(**project.model_dump())
    session.add(db_project)
    await session.commit()
    await session.refresh(db_project)
    return db_project


@router.get("/{project_id}", response_model=schemas.ProjectOut)
async def get_project(project_id: int, session: AsyncSession = Depends(get_session)):
    """Get project by ID."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=schemas.ProjectOut)
async def update_project(
    project_id: int,
    updates: schemas.ProjectUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update project."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for key, value in updates.model_dump(exclude_unset=True).items():
        setattr(project, key, value)

    await session.commit()
    await session.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int, session: AsyncSession = Depends(get_session)):
    """Delete project (soft delete via status)."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.status = "closed"
    await session.commit()
