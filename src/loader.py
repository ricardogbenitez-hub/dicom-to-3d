"""
loader.py
---------
Loads a DICOM series from a folder and returns a sorted 3D numpy array.

A DICOM series = a set of 2D image slices (axial, sagittal, or coronal)
that together form a 3D volume. Each slice has metadata (pixel spacing,
slice thickness, position) that we need to sort and interpret correctly.
"""

import os
import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError
from tqdm import tqdm


def load_dicom_series(folder_path: str) -> tuple[np.ndarray, dict]:
    """
    Load all DICOM slices from a folder and return a sorted 3D volume.

    Args:
        folder_path: Path to folder containing .dcm files

    Returns:
        volume:   3D numpy array of shape (slices, rows, cols) in Hounsfield Units
        metadata: dict with spacing, origin, and other scan parameters
    """
    dicom_files = _find_dicom_files(folder_path)

    if not dicom_files:
        raise FileNotFoundError(f"No DICOM files found in: {folder_path}")

    print(f"Found {len(dicom_files)} DICOM slices. Loading...")

    # Read all slices and sort by slice position (Z axis)
    slices = []
    skipped = 0
    for filepath in tqdm(dicom_files):
        try:
            ds = pydicom.dcmread(filepath)
            slices.append(ds)
        except InvalidDicomError:
            skipped += 1
    if skipped:
        print(f"Skipped {skipped} non-DICOM file(s) found in folder.")

    slices = _sort_slices(slices)

    # Extract pixel data and convert to Hounsfield Units
    volume = _build_volume(slices)

    # Extract spatial metadata for correct physical dimensions
    metadata = _extract_metadata(slices)

    print(f"Volume shape: {volume.shape}  |  HU range: [{volume.min()}, {volume.max()}]")
    return volume, metadata


def _find_dicom_files(folder_path: str) -> list[str]:
    """Recursively find all .dcm files in a folder."""
    dicom_files = []
    for root, _, files in os.walk(folder_path):
        for f in files:
            if f.lower().endswith(".dcm") or _is_dicom(os.path.join(root, f)):
                dicom_files.append(os.path.join(root, f))
    return dicom_files


def _is_dicom(filepath: str) -> bool:
    """Check DICOM magic bytes without relying on file extension."""
    try:
        with open(filepath, "rb") as f:
            f.seek(128)
            return f.read(4) == b"DICM"
    except Exception:
        return False


def _sort_slices(slices: list) -> list:
    """
    Sort slices by ImagePositionPatient Z coordinate.
    This is crucial — DICOM files in a folder are not always in order.
    """
    try:
        slices.sort(key=lambda s: float(s.ImagePositionPatient[2]))
    except AttributeError:
        # Fallback: sort by InstanceNumber if position is missing
        slices.sort(key=lambda s: int(s.InstanceNumber))
    return slices


def _build_volume(slices: list) -> np.ndarray:
    """
    Stack 2D pixel arrays into a 3D volume and convert to Hounsfield Units (HU).

    Hounsfield Units are a standardized scale for radiodensity:
      -1000 HU = air
          0 HU = water
       +400 HU = soft tissue (muscle, organs)
      +1000 HU = cortical bone
    """
    volume = np.stack([s.pixel_array for s in slices], axis=0).astype(np.int16)

    # Apply rescale slope/intercept to get true HU values
    # HU = pixel_value * RescaleSlope + RescaleIntercept
    slope     = float(getattr(slices[0], "RescaleSlope",     1.0))
    intercept = float(getattr(slices[0], "RescaleIntercept", 0.0))

    if slope != 1.0:
        volume = (volume * slope).astype(np.int16)
    volume += np.int16(intercept)

    return volume


def _extract_metadata(slices: list) -> dict:
    """Extract spatial parameters needed to interpret the 3D volume."""
    ref = slices[0]

    # Pixel spacing: distance (mm) between pixel centers in-plane
    pixel_spacing = [float(x) for x in ref.PixelSpacing]

    # Slice thickness: distance (mm) between slices
    slice_thickness = float(getattr(ref, "SliceThickness", 1.0))

    return {
        "pixel_spacing_mm": pixel_spacing,          # [row_spacing, col_spacing]
        "slice_thickness_mm": slice_thickness,
        "voxel_size_mm": [slice_thickness] + pixel_spacing,  # [z, y, x]
        "rows": int(ref.Rows),
        "cols": int(ref.Columns),
        "n_slices": len(slices),
        "modality": getattr(ref, "Modality", "UNKNOWN"),     # CT or MR
        "patient_id": getattr(ref, "PatientID", "UNKNOWN"),
    }
