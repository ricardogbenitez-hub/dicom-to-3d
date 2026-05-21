"""
generate_comparison_gif.py
--------------------------
Generates a rotating side-by-side comparison GIF:
  Left:  foot_bad_baseline.stl  (threshold=400, default settings)
  Right: foot_t225.stl          (threshold=225, anisotropic sigma)

Output: output/renders/comparison.gif
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from io import BytesIO
import os
import trimesh
import imageio.v2 as imageio


def _light_mesh(mesh_preview):
    """Pre-compute face colors for a decimated mesh under fixed lighting."""
    verts = mesh_preview.vertices
    faces = mesh_preview.faces
    tris  = verts[faces]
    norms = mesh_preview.face_normals

    light = np.array([0.6, 0.4, 1.0])
    light /= np.linalg.norm(light)
    diffuse   = np.clip(norms @ light, 0.0, 1.0)
    intensity = 0.25 + 0.75 * diffuse
    bone_rgb  = np.array([0.87, 0.84, 0.78])
    face_colors = np.outer(intensity, bone_rgb)
    return tris, face_colors


def _add_mesh_to_ax(ax, tris, face_colors, elev, azim, bounds, title):
    poly = Poly3DCollection(tris, facecolors=face_colors,
                            linewidths=0, antialiased=False)
    ax.add_collection3d(poly)

    centre = (bounds[0] + bounds[1]) / 2
    radius = np.max(bounds[1] - bounds[0]) / 2 * 1.05
    ax.set_xlim(centre[0] - radius, centre[0] + radius)
    ax.set_ylim(centre[1] - radius, centre[1] + radius)
    ax.set_zlim(centre[2] - radius, centre[2] + radius)
    ax.view_init(elev=elev, azim=azim)
    ax.set_title(title, color="white", fontsize=12, fontweight="bold", pad=8)
    ax.set_axis_off()


def main():
    os.makedirs("output/renders", exist_ok=True)

    print("Loading meshes...")
    bad  = trimesh.load("output/stl/foot_bad_baseline.stl")
    good = trimesh.load("output/stl/foot_t225.stl")

    # Decimate once — matplotlib 3D is slow above ~8K faces
    print("Decimating for render...")
    TARGET = 8_000
    try:
        bad_prev  = bad.simplify_quadric_decimation(TARGET)
        good_prev = good.simplify_quadric_decimation(TARGET)
    except Exception:
        step_b = max(1, len(bad.faces)  // TARGET)
        step_g = max(1, len(good.faces) // TARGET)
        bad_prev  = trimesh.Trimesh(vertices=bad.vertices,
                                    faces=bad.faces[::step_b],  process=False)
        good_prev = trimesh.Trimesh(vertices=good.vertices,
                                    faces=good.faces[::step_g], process=False)

    # Pre-compute lighting — same for every frame
    bad_tris,  bad_colors  = _light_mesh(bad_prev)
    good_tris, good_colors = _light_mesh(good_prev)

    N_FRAMES = 36   # full 360° rotation at 10° per frame
    ELEV     = 22
    FPS      = 12
    BG       = "#111827"

    frames = []
    print(f"Rendering {N_FRAMES} frames...")

    for i in range(N_FRAMES):
        azim = i * (360 / N_FRAMES)

        fig = plt.figure(figsize=(13, 5.8), facecolor=BG)
        ax1 = fig.add_subplot(1, 2, 1, projection="3d", facecolor=BG)
        ax2 = fig.add_subplot(1, 2, 2, projection="3d", facecolor=BG)

        _add_mesh_to_ax(ax1, bad_tris,  bad_colors,
                        ELEV, azim, bad_prev.bounds,
                        "Baseline  |  threshold=400 HU")
        _add_mesh_to_ax(ax2, good_tris, good_colors,
                        ELEV, azim, good_prev.bounds,
                        "Resultado  |  threshold=225 HU")

        fig.suptitle("DICOM → STL  |  CT de Pie  |  Comparación de Segmentación",
                     color="white", fontsize=13, fontweight="bold", y=1.01)
        fig.tight_layout(pad=0.5)

        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                    facecolor=BG, edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        frames.append(imageio.imread(buf))

        if (i + 1) % 6 == 0:
            print(f"  {i+1}/{N_FRAMES} frames done")

    out = "output/renders/comparison.gif"
    imageio.mimsave(out, frames, fps=FPS, loop=0)
    print(f"\nGIF saved: {out}  ({len(frames)} frames @ {FPS} fps)")


if __name__ == "__main__":
    main()
