"""FastAPI application entrypoint for PM Control Center (desktop edition).

On startup the app creates the in-memory schema and, if a data folder has
already been configured, loads the Excel workbooks. When no folder is
configured yet the API still starts (returning empty datasets / a "not
configured" status) so the frontend can present the Setup Wizard.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    cost_balancer,
    cost_space,
    crud,
    dashboard,
    due_diligence,
    invoices,
    projects,
    settings as settings_api,
    time_reports,
    time_upload,
)
from app.core.config import settings
from app.core.database import init_db
from app.services.data_sync import reload_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Load data if a folder was configured in a previous session and is valid.
    if settings.data_folder is not None:
        try:
            await reload_data()
        except (FileNotFoundError, ValueError) as exc:
            # Folder moved/unavailable: start unconfigured so the wizard can run.
            print(f"[startup] Could not load data folder: {exc}")
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings_api.router)
app.include_router(dashboard.router)
app.include_router(crud.router)
app.include_router(projects.router)
app.include_router(due_diligence.router)
app.include_router(cost_balancer.router)
app.include_router(cost_space.router, prefix="/api/cost-space", tags=["cost-space"])
app.include_router(time_reports.router)
app.include_router(time_upload.router, prefix="/api/time-upload", tags=["time-upload"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])


@app.get("/api/health", tags=["health"])
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "configured": settings.data_folder is not None,
    }
