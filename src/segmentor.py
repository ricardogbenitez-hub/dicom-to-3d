"""
segmentor.py
------------
Extract a 3D surface mesh from a volumetric image using Marching Cubes.

Marching Cubes is the core algorithm here. It works by:
1. Taking a 3D scalar field (our HU volume)
2. Defining an isovalue (threshold) — "surface is where HU = X"
3. Marching through each cube of 8 neighboring voxels
4. For each cube, determining how the surface intersects it
5. Outputting triangles that approximate the surface

The result is a polygon mesh (vertices + faces) that represents the
surface of the selected anatomical structure.

Typical HU thresholds:
  Cortical bone:    > 400 HU   (dense, hard bone)
  Trabecular bone:  > 150 HU   (spongy inner bone)
  Soft tissue:      40–80 HU
  Fat:              -100 to -50 HU
"""

import numpy as np
from skimage.measure import marching_cubes
from skimage.filters import gaussian
from skimage.morphology import binary_closing, ball


def extract_surface(
    volume: np.ndarray,
    threshold: float = 400.0,
    spacing: list = (1.0, 1.0, 1.0),
    smooth_sigma: float = 1.0,
    step_size: int = 1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extract an isosurface mesh from a HU volume using Marching Cubes.

    Args:
        volume:       3D numpy array in Hounsfield Units
        threshold:    HU isovalue defining the surface (400 = cortical bone)
        spacing:      voxel size in mm [z, y, x] for correct physical scale
        smooth_sigma: Gaussian smoothing sigma before extraction (reduces noise)
        step_size:    marching cubes step size (1 = full res, 2 = half res, faster)

    Returns:
        verts:  (N, 3) array of vertex coordinates in mm
        faces:  (M, 3) array of triangle indices
        normals:(N, 3) array of vertex normals
    """
    print(f"Segmenting structure at threshold: {threshold} HU...")

    # Optional Gaussian smoothing to reduce staircase artifacts on the mesh
    if smooth_sigma > 0:
        volume_smooth = gaussian(volume.astype(np.float32), sigma=smooth_sigma)
    else:
        volume_smooth = volume.astype(np.float32)

    # Run Marching Cubes
    verts, faces, normals, _ = marching_cubes(
        volume_smooth,
        level=threshold,
        spacing=spacing,   # converts voxel coords to mm
        step_size=step_size,
        allow_degenerate=False,
    )

    print(f"Mesh extracted: {len(verts):,} vertices, {len(faces):,} triangles")
    return verts, faces, normals


def segment_bone(volume: np.ndarray, spacing: list = (1.0, 1.0, 1.0),
                 bone_type: str = "cortical") -> tuple:
    """
    Convenience wrapper for bone segmentation with clinically appropriate thresholds.

    Args:
        bone_type: 'cortical' (dense outer bone) or 'trabecular' (inner spongy bone)
    """
    thresholds = {"cortical": 400.0, "trabecular": 150.0}
    if bone_type not in thresholds:
        raise ValueError(f"bone_type must be 'cortical' or 'trabecular'")

    threshold = thresholds[bone_type]
    # Trabecular bone (150–400 HU) is heterogeneous — σ=1.5 suppresses spikes
    # in vertebral bodies and cancellous regions that σ=1.0 leaves behind.
    sigma = 1.5 if bone_type == "trabecular" else 1.0
    return extract_surface(volume, threshold=threshold, spacing=spacing,
                           smooth_sigma=sigma)


def segment_soft_tissue(volume: np.ndarray, spacing: list = (1.0, 1.0, 1.0),
                        structure: str = "general") -> tuple:
    """
    Soft tissue segmentation (organs, muscle).
    Uses morphological closing to fill internal holes common in organ segmentation.
    """
    thresholds = {
        "general": 40.0,
        "muscle":  60.0,
        "fat":    -80.0,
    }
    threshold = thresholds.get(structure, 40.0)

    # Morphological closing fills small holes inside soft tissue regions
    binary_mask = volume > threshold
    closed_mask = binary_closing(binary_mask, ball(3))

    # Use closed mask as the input for marching cubes
    return extract_surface(
        closed_mask.astype(np.float32),
        threshold=0.5,   # binary mask threshold
        spacing=spacing
    )
