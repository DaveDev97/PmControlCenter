"""API endpoints for syncing data back to Excel file."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.services.excel_writer import ExcelDataWriter

router = APIRouter(prefix="/api/excel", tags=["excel"])


@router.post("/sync")
async def sync_to_excel(session: AsyncSession = Depends(get_session)):
    """Write current database state back to the Excel file."""
    if settings.data_folder is None:
        raise HTTPException(400, "Data folder not configured")

    data_path = Path(settings.data_folder)
    if not data_path.exists():
        raise HTTPException(404, f"Data folder not found: {data_path}")

    try:
        writer = ExcelDataWriter()
        counts = await writer.save_all(data_path, session)
        return {
            "success": True,
            "message": "Data synced to Excel file",
            "counts": counts,
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to sync to Excel: {str(e)}")
