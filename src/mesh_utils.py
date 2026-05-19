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


def keep_largest_component(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Keep only the largest connected component of the mesh.

    Marching Cubes often produces small floating fragments from
    scan noise or metal artifacts. For a femur or skull, we want
    only the main bone structure.
    """
    components = mesh.split(only_watertight=False)
    if not components:
        return mesh

    # Sort by volume and keep the largest
    largest = max(components, key=lambda m: m.volume if m.is_watertight else len(m.faces))
    print(f"Kept largest component: {len(largest.faces):,} faces "
          f"(removed {len(mesh.faces) - len(largest.faces):,} faces from {len(components)-1} fragments)")
    return largest


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
    1. trimesh fill_holes — closes simple planar holes fast
    2. pymeshfix       — repairs complex non-manifold topology that fill_holes misses
    """
    # Extra Laplacian pass before repair: smooths spikes that inflate hole count
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
            print("pymeshfix not installed — skipping advanced hole repair. "
                  "Run: pip install pymeshfix")

    if mesh.is_watertight:
        print(f"Mesh is watertight. Volume: {mesh.volume / 1000:.1f} cm³")
    else:
        print("Warning: mesh is not fully watertight. May have issues in slicing software.")

    return mesh


def export_stl(mesh: trimesh.Trimesh, output_path: str, binary: bool = True) -> None:
    """
    Export mesh as STL file.

    Args:
        output_path: full path including filename, e.g., 'output/stl/femur.stl'
        binary:      True = binary STL (smaller file), False = ASCII (human-readable)
    """
    mesh.export(output_path, file_type="stl_ascii" if not binary else "stl")

    file_size_mb = __import__("os").path.getsize(output_path) / 1e6
    print(f"STL exported: {output_path}  ({file_size_mb:.1f} MB)")
    print(f"  Vertices: {len(mesh.vertices):,}  |  Faces: {len(mesh.faces):,}")


def get_mesh_stats(mesh: trimesh.Trimesh) -> dict:
    """Return a summary of mesh quality metrics."""
    return {
        "n_vertices":   len(mesh.vertices),
        "n_faces":      len(mesh.faces),
        "is_watertight": mesh.is_watertight,
        "volume_cm3":   mesh.volume / 1000 if mesh.is_watertight else None,
        "surface_area_cm2": mesh.area / 100,
        "bounds_mm":    mesh.bounds.tolist(),
        "dimensions_mm": (mesh.bounds[1] - mesh.bounds[0]).tolist(),
    }
