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
      Pelvis / long bone  -- one dominant component (~99 %); result is identical
                             to keep-largest because the large piece passes
                             easily and tiny scan-noise fragments do not.
      Skull               -- calvaria splits at suture lines (coronal, sagittal,
                             lambdoid) into 8-10 similarly sized pieces; keep-
                             largest would silently discard 85 % of the bone.
                             This filter retains all major cranial bones.
      Foot / hand         -- 26+ separate bones; keep-largest would give only
                             the calcaneus or a metacarpal.  All tarsal,
                             metatarsal, and phalangeal bones are kept here.

    Args:
        min_faces:  absolute face-count floor -- any component with fewer faces
                    than this is always discarded as noise (default: 500)
        min_ratio:  minimum size as a fraction of the total mesh faces
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
        kept = [max(components, key=lambda m: len(m.faces))]

    kept_faces    = sum(len(c.faces) for c in kept)
    removed_faces = total_faces - kept_faces
    n_removed     = len(components) - len(kept)

    if len(kept) == 1:
        result = kept[0]
        print(f"Kept 1 component: {kept_faces:,} faces  "
              f"({removed_faces:,} faces removed from {n_removed} fragment(s)  "
              f"|  threshold: >={threshold:,} faces)")
    else:
        result = trimesh.util.concatenate(kept)
        print(f"Kept {len(kept)} components: {kept_faces:,} faces retained  "
              f"({removed_faces:,} faces removed from {n_removed} fragment(s)  "
              f"|  threshold: >={threshold:,} faces)")

    return result


def filter_max_bodies(mesh: trimesh.Trimesh, max_bodies: int) -> trimesh.Trimesh:
    """
    Keep only the N largest connected components by face count.

    Run this after keep_largest_component to discard spatially detached
    structures that passed the ratio threshold (e.g. a tibia stub included
    at the top of a foot scan, or a fibula fragment at the scan boundary).

    Args:
        max_bodies: maximum number of components to retain
    """
    components = mesh.split(only_watertight=False)
    if len(components) <= max_bodies:
        return mesh

    kept = sorted(components, key=lambda m: len(m.faces), reverse=True)[:max_bodies]
    removed = len(components) - len(kept)
    kept_faces = sum(len(c.faces) for c in kept)

    result = kept[0] if len(kept) == 1 else trimesh.util.concatenate(kept)
    print(f"--max-bodies {max_bodies}: kept {len(kept)} component(s), "
          f"{kept_faces:,} faces  ({removed} discarded)")
    return result


def smooth_mesh(mesh: trimesh.Trimesh, iterations: int = 5) -> trimesh.Trimesh:
    """
    Apply Laplacian smoothing to reduce the staircase effect from voxelization.

    Each vertex is moved toward the average position of its neighbors.
    More iterations = smoother surface but more loss of sharp features.
    Recommended: 3--10 iterations for surgical models.
    """
    trimesh.smoothing.filter_laplacian(mesh, iterations=iterations)
    print(f"Smoothing applied: {iterations} iterations")
    return mesh


def _fix_single(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Watertight repair for a single-body mesh.
    Called once per component when fix_mesh detects multiple bodies.
    """
    trimesh.smoothing.filter_laplacian(mesh, iterations=5)
    mesh.fill_holes()
    mesh.fix_normals()

    if not mesh.is_watertight:
        try:
            import pymeshfix
            vclean, fclean = pymeshfix.clean_from_arrays(
                np.asarray(mesh.vertices, dtype=np.float64),
                np.asarray(mesh.faces,    dtype=np.int32),
            )
            mesh = trimesh.Trimesh(vertices=vclean, faces=fclean, process=True)
            mesh.fix_normals()
        except ImportError:
            pass
    return mesh


def fix_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Make the mesh watertight (closed manifold).
    Required for accurate 3D printing and volume calculations.

    Two-stage repair per component:
    1. trimesh fill_holes -- closes simple planar holes fast
    2. pymeshfix         -- repairs complex non-manifold topology

    When the mesh has multiple bodies (skull sutures, foot bones), repair is
    applied to each component individually so pymeshfix cannot discard all but
    the largest body.  Components are concatenated afterwards.
    """
    if mesh.body_count > 1:
        components = mesh.split(only_watertight=False)
        fixed = [_fix_single(c) for c in components]
        mesh = trimesh.util.concatenate(fixed)
        print(f"Repaired {len(fixed)} components individually.")
    else:
        mesh = _fix_single(mesh)

    if mesh.is_watertight:
        print(f"Mesh is watertight. Volume: {mesh.volume / 1000:.1f} cm3")
    else:
        print("Warning: mesh is not fully watertight.")

    return mesh


def reorient_for_printing(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Rotate the mesh so the longest axis lies along X and the model sits flat on Z=0.

    CT scanners encode the patient's superior-inferior direction as voxel Z, so
    elongated structures (foot, femur, spine) export standing upright. Slicers
    (Creality Print, PrusaSlicer, Bambu Studio) place models on the build plate
    using the lowest Z coordinate, so a standing foot needs to be rotated 90°
    before the file is useful for printing or visual presentation.
    """
    dims = mesh.bounds[1] - mesh.bounds[0]
    long_axis = int(np.argmax(dims))  # 0=X, 1=Y, 2=Z

    if long_axis == 2:
        angle, axis = np.pi / 2, [0, 1, 0]   # rotate around Y to bring Z → X
    elif long_axis == 1:
        angle, axis = np.pi / 2, [0, 0, 1]   # rotate around Z to bring Y → X
    else:
        angle = None

    if angle is not None:
        T = trimesh.transformations.rotation_matrix(angle, axis, mesh.centroid)
        mesh.apply_transform(T)

    # Translate so the bottom of the model sits exactly at Z = 0
    mesh.apply_translation([0, 0, -mesh.bounds[0][2]])
    print(f"Reoriented: long axis was {'XYZ'[long_axis]}, model now flat on build plate.")
    return mesh


def export_stl(mesh: trimesh.Trimesh, output_path: str, binary: bool = True) -> None:
    """
    Export mesh as STL file.

    Args:
        output_path: full path including filename, e.g., 'output/stl/femur.stl'
        binary:      True = binary STL (smaller), False = ASCII (human-readable)
    """
    mesh.export(output_path, file_type="stl_ascii" if not binary else "stl")

    file_size_mb = __import__("os").path.getsize(output_path) / 1e6
    print(f"STL exported: {output_path}  ({file_size_mb:.1f} MB)")
    print(f"  Vertices: {len(mesh.vertices):,}  |  Faces: {len(mesh.faces):,}")


def get_mesh_stats(mesh: trimesh.Trimesh) -> dict:
    """Return a summary of mesh quality metrics."""
    return {
        "n_vertices":    len(mesh.vertices),
        "n_faces":       len(mesh.faces),
        "is_watertight": mesh.is_watertight,
        "volume_cm3":    mesh.volume / 1000 if mesh.is_watertight else None,
        "surface_area_cm2": mesh.area / 100,
        "bounds_mm":     mesh.bounds.tolist(),
        "dimensions_mm": (mesh.bounds[1] - mesh.bounds[0]).tolist(),
    }
