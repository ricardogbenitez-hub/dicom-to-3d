"""
worker.py
---------
Pipeline orchestration layer for the API.

Calls src/ modules directly (no subprocess) in the same order as main.py CLI:
  loader → preprocessor → segmentor → mesh_utils

In-memory state for uploads and jobs is also kept here so both route modules
share a single source of truth without circular imports.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Jobs older than this are removed by the background TTL cleanup task
JOB_TTL_SECONDS = 3600  # 1 hour

# Ensure project root is on sys.path so `src.*` imports resolve when uvicorn
# is launched from any working directory.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.loader import load_dicom_series
from src.preprocessor import remove_table, resample_volume
from src.segmentor import segment_bone, segment_soft_tissue
from src.mesh_utils import (
    build_mesh,
    export_stl,
    filter_max_bodies,
    fix_mesh,
    get_mesh_stats,
    keep_largest_component,
    reorient_for_printing,
    smooth_mesh,
)

# ── Shared in-memory state ────────────────────────────────────────────────────
uploads_store: dict = {}
# upload_id -> absolute path to temp DICOM directory

jobs_store: dict = {}
# job_id -> {status, metrics, stl_path, upload_id, error, progress}


# ── Pipeline runner ───────────────────────────────────────────────────────────

def run_pipeline(
    params,
    dicom_dir: str,
    output_path: str,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> dict:
    """
    Execute the full segmentation pipeline and return mesh metrics.

    Args:
        params:            JobRequest instance (already validated by Pydantic)
        dicom_dir:         path to the DICOM series folder
        output_path:       destination path for the output STL
        progress_callback: optional callable invoked after each pipeline stage
                           receives a dict: {stage, percent, message, [metrics]}

    Returns:
        dict with keys: is_watertight, face_count, volume_cm3, bounding_box_mm
    """

    def emit(update: dict) -> None:
        if progress_callback is not None:
            progress_callback(update)

    # 1. Load
    volume, metadata = load_dicom_series(dicom_dir)
    spacing = metadata["voxel_size_mm"]
    emit({
        "stage": "loading",
        "percent": 20,
        "message": f"DICOM loaded — {metadata['n_slices']} slices, "
                   f"voxel {spacing[0]:.2f}×{spacing[1]:.2f}×{spacing[2]:.2f} mm",
    })

    # 2. Preprocess
    volume = remove_table(volume)
    volume, spacing = resample_volume(volume, spacing, target_spacing=[1.0, 1.0, 1.0])
    emit({
        "stage": "preprocessing",
        "percent": 45,
        "message": f"Resampled to 1 mm isotropic — shape {volume.shape}",
    })

    # 3. Segment
    if "bone" in params.structure:
        bone_type = "trabecular" if "trabecular" in params.structure else "cortical"
        verts, faces, normals = segment_bone(
            volume,
            spacing=spacing,
            bone_type=bone_type,
            sigma_override=params.sigma,
            sigma_z_override=params.sigma_z,
            threshold_override=params.threshold,
            bridge_mm=params.bridge,
        )
    else:
        verts, faces, normals = segment_soft_tissue(volume, spacing=spacing)

    emit({
        "stage": "segmenting",
        "percent": 70,
        "message": f"Surface extracted — {len(faces):,} triangles",
    })

    # 4. Build and clean mesh
    mesh = build_mesh(verts, faces)
    mesh = keep_largest_component(mesh, min_ratio=params.min_component_ratio)
    if params.max_bodies is not None:
        mesh = filter_max_bodies(mesh, params.max_bodies)
    mesh = smooth_mesh(mesh, iterations=params.smooth)
    mesh = fix_mesh(mesh)
    if params.reorient:
        mesh = reorient_for_printing(mesh)

    emit({
        "stage": "mesh",
        "percent": 90,
        "message": f"Mesh cleaned — {len(mesh.faces):,} faces, watertight={mesh.is_watertight}",
    })

    # 5. Export + final metrics
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    export_stl(mesh, output_path)

    stats = get_mesh_stats(mesh)
    metrics = {
        "is_watertight": stats["is_watertight"],
        "face_count": stats["n_faces"],
        "volume_cm3": stats["volume_cm3"],
        "bounding_box_mm": stats["bounds_mm"],
    }
    emit({
        "stage": "completed",
        "percent": 100,
        "message": "STL exported successfully",
        "metrics": metrics,
    })

    return metrics


# ── TTL cleanup ───────────────────────────────────────────────────────────────

def cleanup_expired_jobs() -> int:
    """
    Delete jobs (and their STL files) that are older than JOB_TTL_SECONDS.
    Called periodically by the background task in main.py.
    Returns the number of jobs removed.
    """
    now = time.time()
    expired = [
        jid for jid, job in list(jobs_store.items())
        if now - job.get("created_at", now) > JOB_TTL_SECONDS
    ]
    for jid in expired:
        job = jobs_store.pop(jid, None)
        if job:
            stl = job.get("stl_path")
            if stl and os.path.exists(stl):
                try:
                    os.remove(stl)
                except OSError as exc:
                    logger.warning("TTL cleanup: could not delete %s: %s", stl, exc)
    if expired:
        logger.info("TTL cleanup: removed %d expired job(s)", len(expired))
    return len(expired)
