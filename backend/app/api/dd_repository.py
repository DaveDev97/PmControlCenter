"""Due Diligence repository API (reference documents + automatic pre-filling)."""
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.services import dd_repository as dd
from app.services.claude_cli import find_claude

router = APIRouter(prefix="/api/dd-repo", tags=["dd-repository"])


@router.get("/documents")
async def list_documents():
    return {"documents": dd.list_documents(), "types": dd.DOC_TYPES,
            "claude_available": find_claude() is not None}


@router.post("/documents", status_code=201)
async def upload_document(file: UploadFile = File(...), doc_type: str = Form("risposte"),
                          use_claude: bool = Form(True)):
    try:
        return await dd.add_document(await file.read(), file.filename or "documento.xlsx", doc_type, use_claude)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str):
    if not dd.delete_document(doc_id):
        raise HTTPException(404, "Documento non trovato")


@router.post("/fill", status_code=202)
async def fill(file: UploadFile = File(...), use_claude: bool = Form(True)):
    """Start pre-filling a new DD questionnaire; poll /jobs/{id} for progress."""
    try:
        job_id = dd.start_fill(await file.read(), file.filename or "due_diligence.xlsx", use_claude)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
async def job_status(job_id: str):
    job = dd.JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Elaborazione non trovata")
    return {k: v for k, v in job.items() if k != "output"}


@router.get("/jobs/{job_id}/download")
async def job_download(job_id: str):
    job = dd.JOBS.get(job_id)
    if job is None or not job.get("output") or not Path(job["output"]).is_file():
        raise HTTPException(404, "Documento non disponibile")
    return FileResponse(job["output"], filename=job["output_name"],
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
