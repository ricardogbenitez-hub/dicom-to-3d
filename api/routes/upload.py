"""
upload.py
---------
POST /upload — receives DICOM files, saves to a temp directory, returns upload_id.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from api.schemas import UploadResponse
from api.security import upload_rate_limit
from api.worker import uploads_store

router = APIRouter()

# Fix 2 — upload limits
_MAX_FILES = 1000                      # max DICOM files per upload
_MAX_FILE_BYTES = 10 * 1024 * 1024    # 10 MB per individual file
_SAFE_FILENAME = re.compile(r"[^\w.\-]")  # allow alphanumeric, dot, hyphen, underscore


@router.post("/upload", response_model=UploadResponse, dependencies=[Depends(upload_rate_limit)])
async def upload_dicom(files: List[UploadFile] = File(...)):
    """
    Receive N DICOM files via multipart/form-data.

    Saves them to a unique temp directory and returns an upload_id to reference
    in POST /jobs. Files are stored with sanitized names.
    """
    if len(files) > _MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files: received {len(files)}, maximum is {_MAX_FILES}.",
        )

    upload_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp(prefix=f"dicom_{upload_id[:8]}_")

    try:
        for i, f in enumerate(files):
            content = await f.read()
            if len(content) > _MAX_FILE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="One or more files exceed the 10 MB per-file limit.",
                )
            # Sanitize filename to prevent path traversal
            raw_name = os.path.basename(f.filename or "")
            safe_name = _SAFE_FILENAME.sub("_", raw_name) or f"file_{i:04d}"
            dest = os.path.join(temp_dir, safe_name)
            with open(dest, "wb") as out:
                out.write(content)
    except HTTPException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    uploads_store[upload_id] = temp_dir
    return UploadResponse(upload_id=upload_id, file_count=len(files))
