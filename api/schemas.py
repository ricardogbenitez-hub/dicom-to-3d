"""
schemas.py
----------
Pydantic models for API request and response validation.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class JobRequest(BaseModel):
    upload_id: str
    structure: str = "bone"
    # Fix 7 — range validation: all numeric pipeline params are bounded to prevent
    # absurd inputs from consuming excessive CPU/memory or producing garbage geometry.
    threshold: float = Field(default=400.0, ge=0.0, le=3000.0)
    sigma: float = Field(default=1.0, ge=0.1, le=5.0)
    sigma_z: Optional[float] = Field(default=None, ge=0.1, le=5.0)
    smooth: int = Field(default=5, ge=0)  # upper bound enforced by smooth_limit validator
    step_size: int = Field(default=1, ge=1, le=4)
    min_component_ratio: float = Field(default=0.01, ge=0.001, le=0.5)
    max_bodies: Optional[int] = Field(default=None, ge=1, le=20)
    reorient: bool = False
    bridge: int = Field(default=0, ge=0, le=10)

    @field_validator("smooth")
    @classmethod
    def smooth_limit(cls, v: int) -> int:
        if v > 10:
            raise ValueError(
                f"smooth={v} exceeds the hard limit of 10. "
                "Values above 10 break mesh watertightness (validated from foot CT experiments)."
            )
        return v

    @field_validator("structure")
    @classmethod
    def structure_choices(cls, v: str) -> str:
        valid = {"bone", "cortical_bone", "trabecular_bone", "soft_tissue"}
        if v not in valid:
            raise ValueError(f"structure must be one of {sorted(valid)}, got '{v}'")
        return v


class UploadResponse(BaseModel):
    upload_id: str
    file_count: int
    # DICOM metadata extracted from first valid slice header — None if unreadable
    pixel_spacing: Optional[str] = None     # e.g. "0.32 mm"
    slice_thickness: Optional[str] = None  # e.g. "3.00 mm"
    modality: Optional[str] = None         # e.g. "CT"


class JobMetrics(BaseModel):
    is_watertight: bool
    face_count: int
    volume_cm3: Optional[float]
    bounding_box_mm: Optional[List[List[float]]]


class JobResponse(BaseModel):
    job_id: str
    status: str  # pending | running | completed | failed
    metrics: Optional[JobMetrics] = None
    error: Optional[str] = None
