"""
main.py
-------
FastAPI application entry point.

Start with:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

Interactive docs available at http://localhost:8000/docs (disabled when
RAILWAY_ENVIRONMENT is set, i.e. in production).
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.jobs import router as jobs_router
from api.routes.upload import router as upload_router
from api.worker import cleanup_expired_jobs

logger = logging.getLogger(__name__)


# ── Background TTL cleanup ────────────────────────────────────────────────────

async def _cleanup_loop() -> None:
    """Run cleanup_expired_jobs every 5 minutes for the lifetime of the process."""
    while True:
        await asyncio.sleep(300)
        try:
            cleanup_expired_jobs()
        except Exception:
            logger.exception("Unexpected error in TTL cleanup loop")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ── App factory ───────────────────────────────────────────────────────────────

# Fix 4 — disable interactive docs in production to reduce attack surface
_is_prod = bool(os.getenv("RAILWAY_ENVIRONMENT"))

app = FastAPI(
    title="DICOM to 3D Surgical Model API",
    version="1.0.0",
    description=(
        "Convert DICOM CT/MRI series to STL files for surgical simulation. "
        "Upload a DICOM series via POST /upload, then submit a job via POST /jobs."
    ),
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
    lifespan=_lifespan,
)

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(jobs_router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Liveness probe used by Railway (healthcheckPath: /health)."""
    return {"status": "ok"}
