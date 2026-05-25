"""
jobs.py
-------
POST /jobs               — queue the pipeline (returns immediately, status=pending)
GET  /jobs/{id}          — retrieve job status + metrics
GET  /jobs/{id}/download — stream the STL file
WS   /ws/jobs/{id}       — real-time progress updates via WebSocket
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from api.schemas import JobMetrics, JobRequest, JobResponse
from api.security import job_rate_limit
from api.worker import jobs_store, run_pipeline, uploads_store

logger = logging.getLogger(__name__)

router = APIRouter()

# STL files produced by the API are stored under output/stl/api/
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_API_OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "output", "stl", "api")

# Shared thread pool — limits concurrent pipeline runs to avoid memory exhaustion
_executor = ThreadPoolExecutor(max_workers=2)


def _run_job_in_thread(job_id: str, params, dicom_dir: str, output_path: str) -> None:
    """
    Runs in a worker thread (via run_in_executor).

    Updates jobs_store directly so both GET /jobs/{id} and the WebSocket see
    live state. Dict writes in CPython are GIL-protected and safe from threads.
    """
    def progress_cb(update: dict) -> None:
        jobs_store[job_id]["progress"] = update

    jobs_store[job_id]["status"] = "running"
    try:
        metrics = run_pipeline(params, dicom_dir, output_path, progress_callback=progress_cb)
        jobs_store[job_id]["status"] = "completed"
        jobs_store[job_id]["metrics"] = metrics
    except Exception as exc:
        # Fix 3 — log full traceback internally; return only a sanitized message to the client
        logger.exception("Pipeline failed for job %s", job_id)
        safe_msg = f"Pipeline error: {type(exc).__name__}"
        jobs_store[job_id]["status"] = "failed"
        jobs_store[job_id]["error"] = safe_msg
        jobs_store[job_id]["progress"] = {
            "stage": "failed",
            "percent": 0,
            "message": safe_msg,
        }
    finally:
        # Fix 1 — delete the DICOM upload directory once the job finishes
        upload_id = jobs_store.get(job_id, {}).get("upload_id")
        if upload_id:
            uploads_store.pop(upload_id, None)
        if dicom_dir and os.path.exists(dicom_dir):
            shutil.rmtree(dicom_dir, ignore_errors=True)
            logger.debug("Cleaned up DICOM temp dir: %s", dicom_dir)


@router.post("/jobs", response_model=JobResponse, dependencies=[Depends(job_rate_limit)])
async def create_job(req: JobRequest):
    """
    Queue the pipeline and return immediately with status=pending.

    The pipeline runs in a background thread. Poll GET /jobs/{id} or
    connect to WS /ws/jobs/{id} to track progress.
    """
    if req.upload_id not in uploads_store:
        raise HTTPException(
            status_code=404,
            detail=f"upload_id '{req.upload_id}' not found. Upload DICOM files first via POST /upload.",
        )

    job_id = str(uuid.uuid4())
    dicom_dir = uploads_store[req.upload_id]
    output_path = os.path.join(_API_OUTPUT_DIR, f"{job_id}.stl")

    jobs_store[job_id] = {
        "status": "pending",
        "metrics": None,
        "stl_path": output_path,
        "upload_id": req.upload_id,
        "error": None,
        "progress": None,
        "created_at": time.time(),  # Fix 6 — TTL reference timestamp
    }

    loop = asyncio.get_running_loop()
    loop.run_in_executor(_executor, _run_job_in_thread, job_id, req, dicom_dir, output_path)

    return JobResponse(job_id=job_id, status="pending")


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    """Return current status and metrics for a job."""
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs_store[job_id]
    return JobResponse(
        job_id=job_id,
        status=job["status"],
        metrics=JobMetrics(**job["metrics"]) if job["metrics"] else None,
        error=job.get("error"),
    )


@router.get("/jobs/{job_id}/download")
def download_stl(job_id: str):
    """Stream the STL file as a binary download."""
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = jobs_store[job_id]
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job status is '{job['status']}'. Download is only available after the job completes.",
        )

    stl_path = job["stl_path"]
    if not os.path.exists(stl_path):
        raise HTTPException(status_code=404, detail="STL file not found on disk.")

    return FileResponse(
        path=stl_path,
        media_type="application/octet-stream",
        filename=f"{job_id}.stl",
    )


@router.websocket("/ws/jobs/{job_id}")
async def job_progress_ws(websocket: WebSocket, job_id: str):
    """
    Stream pipeline progress events as JSON messages.

    Sends one message per stage transition. Closes automatically when the
    job reaches status completed or failed. Each message shape:
        {stage, percent, message, [metrics]}
    """
    if job_id not in jobs_store:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    last_sent: dict | None = None

    try:
        while True:
            job = jobs_store.get(job_id)
            if job is None:
                await websocket.close(code=1008)
                return

            progress = job.get("progress")
            if progress is not None and progress != last_sent:
                await websocket.send_json(progress)
                last_sent = progress

            if job.get("status") in ("completed", "failed"):
                # Ensure the final progress update is flushed before closing
                final = job.get("progress")
                if final is not None and final != last_sent:
                    await websocket.send_json(final)
                await websocket.close()
                return

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        # Client disconnected early — nothing to clean up
        pass
