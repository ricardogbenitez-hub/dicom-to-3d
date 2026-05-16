"""
visualizer.py
-------------
Visualization tools: 2D slice viewer and 3D mesh preview.

Good visualizations are critical for this project — the README renders
are what make the project visually compelling on GitHub.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import trimesh
import os


def show_slices(volume: np.ndarray, title: str = "DICOM Volume",
                save_path: str = None) -> None:
    """
    Display three orthogonal slices (axial, coronal, sagittal)
    through the center of the volume.

    Args:
        volume:     3D numpy array (slices, rows, cols)
        title:      figure title
        save_path:  if provided, save as PNG instead of displaying
    """
    n_z, n_y, n_x = volume.shape
    mid_z, mid_y, mid_x = n_z // 2, n_y // 2, n_x // 2

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(title, fontsize=14, fontweight="bold")

    slices = [
        (volume[mid_z, :, :], f"Axial (z={mid_z})"),
        (volume[:, mid_y, :], f"Coronal (y={mid_y})"),
        (volume[:, :, mid_x], f"Sagittal (x={mid_x})"),
    ]

    for ax, (img, label) in zip(axes, slices):
        ax.imshow(img, cmap="gray", origin="lower")
        ax.set_title(label, fontsize=11)
        ax.axis("off")

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Slice view saved: {save_path}")
    else:
        plt.show()
    plt.close()


def show_volume_stats(volume: np.ndarray) -> None:
    """Plot HU histogram with annotated tissue ranges."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Histogram
    flat = volume.flatten()
    ax1.hist(flat, bins=200, color="#2563EB", alpha=0.75, range=(-1000, 2000))
    ax1.set_xlabel("Hounsfield Units (HU)")
    ax1.set_ylabel("Voxel count")
    ax1.set_title("HU Distribution")

    # Annotate tissue ranges
    tissue_ranges = [
        (-1000, -500, "#87CEEB", "Air"),
        (-100,  -50,  "#FFD700", "Fat"),
        (  40,   80,  "#FF8C00", "Soft tissue"),
        ( 400, 1000,  "#DC143C", "Bone"),
    ]
    for lo, hi, color, label in tissue_ranges:
        ax1.axvspan(lo, hi, alpha=0.2, color=color, label=label)
    ax1.legend(fontsize=9)

    # Middle axial slice
    ax2.imshow(volume[volume.shape[0] // 2], cmap="gray", origin="lower")
    ax2.set_title("Middle Axial Slice")
    ax2.axis("off")

    plt.tight_layout()
    plt.show()


def render_mesh_preview(mesh: trimesh.Trimesh, output_path: str = None) -> None:
    """
    Save a four-view render of the 3D mesh using matplotlib 3D.

    Uses diffuse lighting (dot product of face normals with a key light)
    to give a bone-like appearance without needing OpenGL.
    Views: Anterior, Lateral, Superior, Isometric.
    """
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    # Simplify to ~10 000 faces so matplotlib renders quickly.
    # The full surgical mesh can exceed 800 K faces.
    target_faces = 10_000
    try:
        preview = mesh.simplify_quadric_decimation(target_faces)
    except Exception:
        # Fallback: subsample faces uniformly
        step = max(1, len(mesh.faces) // target_faces)
        idx = np.arange(0, len(mesh.faces), step)
        preview = trimesh.Trimesh(vertices=mesh.vertices,
                                  faces=mesh.faces[idx], process=False)

    verts  = preview.vertices
    faces  = preview.faces
    tris   = verts[faces]           # (F, 3, 3) — three XYZ vertices per triangle
    norms  = preview.face_normals   # (F, 3)

    # Simple diffuse + ambient lighting from upper-right-front
    light = np.array([0.6, 0.4, 1.0])
    light /= np.linalg.norm(light)
    diffuse = np.clip(norms @ light, 0.0, 1.0)
    ambient = 0.25
    intensity = ambient + (1.0 - ambient) * diffuse  # (F,)

    # Warm ivory bone colour
    bone_rgb = np.array([0.87, 0.84, 0.78])
    face_colors = np.outer(intensity, bone_rgb)       # (F, 3)

    # (elev, azim) pairs for the four clinical views
    views = [
        ("Anterior",  5,   0),
        ("Lateral",   5,  90),
        ("Superior",  88,  0),
        ("Isometric", 30, 45),
    ]

    bg = "#111827"
    fig = plt.figure(figsize=(20, 5.5), facecolor=bg)

    bounds = preview.bounds
    centre = (bounds[0] + bounds[1]) / 2
    radius = np.max(bounds[1] - bounds[0]) / 2

    for i, (label, elev, azim) in enumerate(views):
        ax = fig.add_subplot(1, 4, i + 1, projection="3d", facecolor=bg)

        poly = Poly3DCollection(tris, facecolors=face_colors,
                                linewidths=0, antialiased=False)
        ax.add_collection3d(poly)

        ax.set_xlim(centre[0] - radius, centre[0] + radius)
        ax.set_ylim(centre[1] - radius, centre[1] + radius)
        ax.set_zlim(centre[2] - radius, centre[2] + radius)
        ax.view_init(elev=elev, azim=azim)

        ax.set_title(label, color="white", fontsize=12,
                     fontweight="bold", pad=8)
        ax.set_axis_off()

    fig.suptitle("CT Colonography — Bone Segmentation",
                 color="white", fontsize=14, fontweight="bold", y=0.98)
    fig.subplots_adjust(wspace=0.02, left=0.01, right=0.99)

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight",
                    facecolor=bg, edgecolor="none")
        print(f"Mesh preview saved: {output_path}")
    else:
        plt.show()
    plt.close()


def save_slice_animation(volume: np.ndarray, output_path: str,
                         axis: int = 0, fps: int = 10) -> None:
    """
    Save a GIF animation scrolling through slices along a given axis.
    Great for README visualization.

    Args:
        axis: 0=axial, 1=coronal, 2=sagittal
    """
    try:
        import imageio
    except ImportError:
        print("Install imageio: pip install imageio")
        return

    frames = []
    n_slices = volume.shape[axis]

    for i in range(n_slices):
        if axis == 0:   img = volume[i, :, :]
        elif axis == 1: img = volume[:, i, :]
        else:           img = volume[:, :, i]

        # Normalize to uint8
        img_norm = ((img - img.min()) / (img.max() - img.min() + 1e-8) * 255).astype(np.uint8)
        frames.append(img_norm)

    imageio.mimsave(output_path, frames, fps=fps, loop=0)
    print(f"Animation saved: {output_path}  ({n_slices} frames)")
