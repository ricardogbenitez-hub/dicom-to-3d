"""
mesh_utils.py
-------------
Clean, smooth, and export 3D meshes as STL files.

A raw Marching Cubes output often has issues:
  - Disconnected floating fragments (noise from scan artifacts)
  - Rough staircase surface (from voxel grid)
  - Non-manifold geometry (edges shared by >2 faces)

These functions fix those problems and prepare the mesh for
3D printing or surgical simulation software (e.g., Mimics, 3D Slicer).
"""

import numpy as np
import trimesh


def build_mesh(verts: np.ndarray, faces: np.ndarray) -> trimesh.Trimesh:
    """Create a trimesh object from raw vertices and faces."""
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    return mesh


def keep_largest_component(
    mesh: trimesh.Trimesh,
    min_faces: int = 500,
    min_ratio: float = 0.01,
) -> trimesh.Trimesh:
    """
    Keep all connected components large enough to represent real anatomy.

    Unlike a strict 'keep only the largest', this approach retains every
    component whose face count meets EITHER threshold:
      - absolute : faces >= min_faces
      - relative : faces >= min_ratio * total_faces  (default 1 %)

    Why this matters by anatomical structure:
      Pelvis / long bone  — one dominant component (~99 %); result is identical
                            to keep-largest because the large piece passes
                            easily and tiny scan-noise fragments do not.
      Skull               — calvaria splits at suture lines (coronal, sagittal,
                            lambdoid) into 8-10 similarly sized pieces; keep-
                            largest would silently discard 85 % of the bone.
                            This filter retains all major cranial bones.
      Foot / hand         — 26+ separate bones; keep-largest would give only
                            the calcaneus or a metacarpal.  All tarsal,
                            metatarsal, and phalangeal bones are kept here.

    Args:
        min_faces:  absolute face-count floor — any component with fewer faces
                    than this is always discarded as noise (default: 500)
        min_ratio:  minimum size expressed as a fraction of the total mesh faces
                    (default: 0.01 = 1 %).  Scales automatically with scan
                    resolution so the threshold is always meaningful.

    Falls back to the single largest component if nothing meets either threshold
    (edge case: extremely noisy scan with no clear dominant structure).
    """
    components = mesh.split(only_watertight=False)
    if not components:
        return mesh

    total_faces = len(mesh.faces)
    threshold   = max(min_faces, int(min_ratio * total_faces))

    kept = [c for c in components if len(c.faces) >= threshold]

    if not kept:
        # Nothing passed the threshold — fall back to largest single component
        kept = [max(components, key=lambda m: len(m.faces))]

    kept_faces    = sum(len(c.faces) for c in kept)
    removed_faces = total_faces - kept_faces
    n_removed     = len(components) - len(kept)

    if len(kept) == 1:
        result = kept[0]
        print(f"Kept 1 component: {kept_faces:,} faces  "
              f"({removed_faces:,} faces removed from {n_removed} fragment(s)  "
              f"|  threshold: ≥{threshold:,} faces)")
    else:
        result = trimesh.util.concatenate(kept)
        print(f"Kept {len(kept)} components: {kept_faces:,} faces retained  "
              f"({removed_faces:,} faces removed from {n_removed} fragment(s)  "
              f"|  threshold: ≥{threshold:,} faces)")

    return result


def smooth_mesh(mesh: trimesh.Trimesh, iterations: int = 5) -> trimesh.Trimesh:
    """
    Apply Laplacian smoothing to reduce the staircase effect from voxelization.

    Each vertex is moved toward the average position of its neighbors.
    More iterations = smoother surface but more loss of sharp features.
    Recommended: 3–10 iterations for surgical models.
    """
    trimesh.smoothing.filter_laplacian(mesh, iterations=iterations)
    print(f"Smoothing applied: {iterations} iterations")
    return mesh


def fix_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Make the mesh watertight (closed manifold).
    Required for accurate 3D printing and volume calculations.

    Two-stage repair:
    1. t