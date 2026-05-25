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

import gc

import numpy as np
from scipy.ndimage import binary_fill_holes
from skimage.measure import marching_cubes
from skimage.filters import gaussian
from skimage.morphology import closing, ball


def _zero_borders(mask: np.ndarray, border: int) -> np.ndarray:
    """Zero out N voxels on every face of a binary 3D mask.

    Prevents bone signal from touching volume walls after Gaussian smoothing.
    If the mask reaches any wall, binary_fill_holes treats the entire wall
    as an enclosed surface and seals it → flat "skirt" artifact.
    border must be >= sigma_z to guarantee wall clearance.
    """
    mask[:border,  :,  :] = False
    mask[-border:, :,  :] = False
    mask[:,  :border,  :] = False
    mask[:, -border:,  :] = False
    mask[:,  :, :border]  = False
    mask[:,  :, -border:] = False
    return mask


def extract_surface(
    volume: np.ndarray,
    threshold: float = 400.0,
    spacing: list = (1.0, 1.0, 1.0),
    smooth_sigma: float = 1.0,
    step_size: int = 1,
    fill_cavities: bool = False,
    bridge_radius: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extract an isosurface mesh from a HU volume using Marching Cubes.

    Args:
        volume:         3D numpy array in Hounsfield Units
        threshold:      HU isovalue defining the surface (400 = cortical bone)
        spacing:        voxel size in mm [z, y, x] for correct physical scale
        smooth_sigma:   Gaussian smoothing sigma before extraction (reduces noise)
        step_size:      marching cubes step size (1 = full res, 2 = half res, faster)
        fill_cavities:  if True, fill enclosed voids in the binary mask before
                        running Marching Cubes. Prevents hollow-shell artifacts in
                        bones with low-density trabecular interiors (e.g. tarsals,
                        vertebral bodies at thick slice thickness).
        bridge_radius:  if > 0, applies an additional closing of this radius (mm at
                        1mm³ isotropic) to bridge inter-bone gaps. Produces a single
                        fused model where joint spaces appear as thin cartilage-like
                        connections. Use 3–4 for foot CT tarsal bridging.

    Returns:
        verts:  (N, 3) array of vertex coordinates in mm
        faces:  (M, 3) array of triangle indices
        normals:(N, 3) array of vertex normals
    """
    print(f"Segmenting structure at threshold: {threshold} HU...")

    if smooth_sigma is None or (np.isscalar(smooth_sigma) and smooth_sigma == 0):
        volume_smooth = volume.astype(np.float32)
    else:
        # smooth_sigma can be a scalar (isotropic) or a (z, y, x) tuple (anisotropic).
        # Anisotropic is preferred for thick-slice CT: high sigma_z bridges inter-slice
        # artifacts while low sigma_xy preserves fine in-plane bone boundaries.
        volume_smooth = gaussian(volume.astype(np.float32), sigma=smooth_sigma)

    if fill_cavities:
        # Build binary mask, fill enclosed voids, then feed filled mask to MC.
        # This converts hollow cortical shells (trabecular interior below threshold)
        # into solid bones — eliminates tunnels and internal surface artifacts.
        mask = volume_smooth > threshold
        # volume_smooth (float32, ~270 MB for 400-slice CT) is no longer needed now
        # that we have the binary mask. Free it before closing/fill_holes to stay
        # within Railway's 512 MB limit.
        del volume_smooth
        gc.collect()

        # Zero volume border (4 voxels). Prevents sigma-blurred bone from touching
        # the scan wall — wall contact lets binary_fill_holes seal the entire face,
        # producing a large flat "skirt" plate at the base of the model.
        # BORDER > sigma_z (2.0) guarantees clearance after anisotropic smoothing.
        BORDER = 4
        mask = _zero_borders(mask, BORDER)

        # Closing r=2: bridges the 1–2mm tarsal cartilage gaps that disappear in
        # 3mm-slice CT. r>2 risks fusing phalanges; r<2 leaves inter-slice valleys.
        mask = closing(mask, ball(2))

        if bridge_radius > 0:
            # Bridge mode: larger closing fuses adjacent bones into one solid model.
            # The extra r=(bridge_radius - 2) dilation reaches across joint spaces
            # (typically 2–4mm in the foot) and fills them with bone-like material,
            # creating visible cartilage-analog connections between tarsal bones.
            mask = closing(mask, ball(bridge_radius))
            # Re-zero borders: the larger closing may expand the mask back to the wall.
            mask = _zero_borders(mask, BORDER)
            print(f"  Bridge mode: closing(r={bridge_radius}) fusing inter-bone gaps.")

        mask = binary_fill_holes(mask)
        volume_smooth = mask.astype(np.float32)
        level = 0.5
        print(f"  Border zeroing (BORDER={BORDER}) + closing(r=2) + cavity fill applied.")
    else:
        level = threshold

    verts, faces, normals, _ = marching_cubes(
        volume_smooth,
        level=level,
        spacing=spacing,
        step_size=step_size,
        allow_degenerate=False,
    )
    # volume_smooth is now consumed by marching_cubes — free it before returning
    # the large verts/faces arrays to the caller.
    del volume_smooth
    gc.collect()

    print(f"Mesh extracted: {len(verts):,} vertices, {len(faces):,} triangles")
    return verts, faces, normals


def segment_bone(volume: np.ndarray, spacing: list = (1.0, 1.0, 1.0),
                 bone_type: str = "cortical",
                 sigma_override: float = None,
                 sigma_z_override: float = None,
                 threshold_override: float = None,
                 bridge_mm: int = 0) -> tuple:
    """
    Convenience wrapper for bone segmentation with clinically appropriate thresholds.

    Args:
        bone_type:          'cortical' (dense outer bone) or 'trabecular' (inner spongy bone)
        sigma_override:     scalar Gaussian sigma for all axes (default: 1.0/1.5)
        sigma_z_override:   if set, builds anisotropic sigma (sigma_z, sigma_xy, sigma_xy)
                            where sigma_xy = sigma_override or the default. Use sigma_z=2.0
                            with sigma=0.5 for thick-slice foot CT (3mm slices): heavy Z
                            smoothing bridges inter-slice artifacts without eroding metatarsal
                            shafts (~8mm diam) that scalar sigma=2.0 would hollow out.
        threshold_override: HU isovalue override. Use 350 for foot/extremity CT where
                            tarsal cortex is less dense than axial skeleton.
        bridge_mm:          if > 0, fuses adjacent bones into a single solid model by
                            applying closing(ball(bridge_mm)) after the standard r=2 closing.
                            Use 3–4 for foot tarsal bridging. Produces one unified mesh
                            where joint spaces appear as cartilage-like connections.
    """
    thresholds = {"cortical": 400.0, "trabecular": 150.0}
    if bone_type not in thresholds:
        raise ValueError(f"bone_type must be 'cortical' or 'trabecular'")

    threshold = thresholds[bone_type]
    sigma = 1.5 if bone_type == "trabecular" else 1.0

    if sigma_override is not None:
        sigma = sigma_override

    if sigma_z_override is not None:
        # Build anisotropic kernel: (Z, Y, X). Volume axes after resampling are (Z, Y, X).
        sigma = (sigma_z_override, sigma, sigma)
        print(f"  Anisotropic sigma: z={sigma_z_override}, xy={sigma[1]} "
              f"(thick-slice Z smoothing, fine XY preserved)")
    elif sigma_override is not None:
        print(f"  Sigma override: {sigma}")

    if threshold_override is not None:
        threshold = threshold_override
        print(f"  Threshold override: {threshold} HU")

    return extract_surface(volume, threshold=threshold, spacing=spacing,
                           smooth_sigma=sigma, fill_cavities=True,
                           bridge_radius=bridge_mm)


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
    closed_mask = closing(binary_mask, ball(3))

    # Use closed mask as the input for marching cubes
    return extract_surface(
        closed_mask.astype(np.float32),
        threshold=0.5,   # binary mask threshold
        spacing=spacing
    )
