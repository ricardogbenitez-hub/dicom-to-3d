"""
preprocessor.py
---------------
Normalize and window a raw HU volume before segmentation.

"Windowing" is a key concept in radiology: since HU values range from
-1000 to +3000, displaying or processing the full range makes most
structures invisible. A window centers on a specific tissue type:

  Structure       Window Center   Window Width
  ──────────────────────────────────────────────
  Bone            +400            1000
  Soft tissue     +40             400
  Lung            -600            1500
  Brain           +40             80
"""

import numpy as np


# Predefined clinical windows
WINDOWS = {
    "bone":        {"center": 400,  "width": 1000},
    "soft_tissue": {"center": 40,   "width": 400},
    "lung":        {"center": -600, "width": 1500},
    "brain":       {"center": 40,   "width": 80},
}


def apply_window(volume: np.ndarray, window: str = "bone") -> np.ndarray:
    """
    Apply a clinical HU window and normalize to [0, 1].

    Args:
        volume: 3D numpy array in Hounsfield Units
        window: one of 'bone', 'soft_tissue', 'lung', 'brain'

    Returns:
        Normalized float32 array in range [0.0, 1.0]
    """
    if window not in WINDOWS:
        raise ValueError(f"Unknown window '{window}'. Choose from: {list(WINDOWS.keys())}")

    center = WINDOWS[window]["center"]
    width  = WINDOWS[window]["width"]

    lower = center - width // 2
    upper = center + width // 2

    windowed = np.clip(volume, lower, upper).astype(np.float32)
    normalized = (windowed - lower) / (upper - lower)
    return normalized


def apply_custom_window(volume: np.ndarray, center: int, width: int) -> np.ndarray:
    """Apply a custom HU window. Useful for unusual structures."""
    lower = center - width // 2
    upper = center + width // 2
    windowed = np.clip(volume, lower, upper).astype(np.float32)
    return (windowed - lower) / (upper - lower)


def remove_table(volume: np.ndarray, hu_threshold: int = -500) -> np.ndarray:
    """
    Zero out the CT scanner table (typically appears as a hard structure
    below the patient). Simple approach: mask out everything below a
    horizontal plane where the table artifact is detected.

    Note: For production use, a more robust approach with connected
    component labeling is recommended.
    """
    # Create binary mask: True where there is tissue (not air)
    body_mask = volume > hu_threshold

    # Keep only the largest connected region (the patient's body)
    # This removes isolated table artifacts
    from scipy import ndimage
    labeled, n_features = ndimage.label(body_mask)
    if n_features > 1:
        sizes = ndimage.sum(body_mask, labeled, range(1, n_features + 1))
        largest = np.argmax(sizes) + 1
        body_mask = labeled == largest

    cleaned = volume.copy()
    cleaned[~body_mask] = -1000  # Set non-body regions to air HU
    return cleaned


def resample_volume(volume: np.ndarray, original_spacing: list,
                    target_spacing: list = [1.0, 1.0, 1.0]) -> tuple[np.ndarray, list]:
    """
    Resample a volume to isotropic voxel spacing (default: 1mm x 1mm x 1mm).

    CT scans often have anisotropic voxels (e.g., 0.7 x 0.7 x 3.0 mm).
    Resampling to isotropic spacing is important for accurate 3D geometry.

    Args:
        volume:           3D numpy array
        original_spacing: [z_mm, y_mm, x_mm] voxel size
        target_spacing:   desired voxel size (default 1mm isotropic)

    Returns:
        resampled_volume, actual_new_spacing
    """
    from scipy.ndimage import zoom

    resize_factor = [orig / target for orig, target in
                     zip(original_spacing, target_spacing)]

    new_shape = [int(round(dim * factor))
                 for dim, factor in zip(volume.shape, resize_factor)]

    resampled = zoom(volume.astype(np.float32), resize_factor, order=1)
    actual_spacing = [orig / factor for orig, factor in
                      zip(original_spacing, resize_factor)]

    return resampled, actual_spacing
