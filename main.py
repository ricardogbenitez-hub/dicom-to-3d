"""
main.py
-------
CLI entry point for the DICOM to 3D Surgical Model pipeline.

Usage examples:
  # Convert a CT scan folder to a bone STL
  python main.py --input ./data/sample --structure bone --output ./output/stl/bone.stl

  # Soft tissue (organ) segmentation
  python main.py --input ./data/sample --structure soft_tissue --output ./output/stl/organ.stl

  # Full pipeline with visualization
  python main.py --input ./data/sample --structure bone --output ./output/stl/bone.stl --visualize
"""

import argparse
import os
import sys

from src.loader import load_dicom_series
from src.preprocessor import remove_table, resample_volume
from src.segmentor import segment_bone, segment_soft_tissue
from src.mesh_utils import build_mesh, keep_largest_component, filter_max_bodies, smooth_mesh, fix_mesh, reorient_for_printing, export_stl, get_mesh_stats
from src.visualizer import show_slices, save_slice_animation


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert a DICOM CT/MRI series to a 3D STL model for surgical simulation."
    )
    parser.add_argument("--input",      required=True,  help="Path to folder with DICOM files")
    parser.add_argument("--output",     required=True,  help="Output STL file path")
    parser.add_argument("--structure",  default="bone",
                        choices=["bone", "cortical_bone", "trabecular_bone", "soft_tissue"],
                        help="Anatomical structure to segment")
    parser.add_argument("--smooth",     type=int, default=5,
                        help="Laplacian smoothing iterations (default: 5)")
    parser.add_argument("--min-component-ratio", type=float, default=0.01,
                        metavar="FLOAT",
                        help="Minimum component size as fraction of total faces. "
                             "Use higher values (0.02-0.05) to discard floating "
                             "fragments. Default: 0.01")
    parser.add_argument("--max-bodies", type=int, default=None,
                        metavar="N",
                        help="Keep only the N largest connected components after "
                             "ratio filtering. Use --max-bodies 1 for a single "
                             "structure (femur, tibia). Omit to keep all components "
                             "that pass --min-component-ratio.")
    parser.add_argument("--reorient", action="store_true",
                        help="Rotate the mesh so the longest axis lies along X. "
                             "Prevents elongated structures (foot, femur) from "
                             "loading upright in slicers.")
    parser.add_argument("--sigma",      type=float, default=None,
                        help="Isotropic Gaussian sigma for HU volume smoothing before "
                             "thresholding. Default: 1.0 (cortical), 1.5 (trabecular). "
                             "When --sigma-z is also given, this value is used for XY axes.")
    parser.add_argument("--sigma-z",    type=float, default=None,
                        metavar="FLOAT",
                        help="Z-axis Gaussian sigma (inter-slice direction). Enables "
                             "anisotropic smoothing: heavy Z smoothing bridges 3mm "
                             "inter-slice artifacts; low XY sigma (--sigma 0.5) preserves "
                             "metatarsal shaft detail. Recommended for thick-slice foot CT: "
                             "--sigma-z 2.0 --sigma 0.5")
    parser.add_argument("--threshold",  type=float, default=None,
                        help="HU isovalue for bone surface (default: 400 cortical, "
                             "150 trabecular). Use 350 for foot/extremity CT where "
                             "tarsal cortex is less dense than axial skeleton.")
    parser.add_argument("--bridge",     type=int, default=0,
                        metavar="MM",
                        help="Bridge inter-bone gaps to produce a single fused model. "
                             "Applies morphological closing of radius MM (mm) after the "
                             "standard r=2 closing. Joint spaces become visible "
                             "cartilage-like connections. Use 3 or 4 for foot CT tarsal "
                             "bridging. Default: 0 (disabled, bones may be separate).")
    parser.add_argument("--step-size",  type=int, default=1,
                        help="Marching cubes step size. Higher = faster but lower res")
    parser.add_argument("--visualize",  action="store_true",
                        help="Save slice views and mesh preview images")
    parser.add_argument("--animate",    action="store_true",
                        help="Save axial slice animation GIF")
    return parser.parse_args()


def run_pipeline(args):
    print("\n" + "="*60)
    print("  DICOM to 3D Surgical Model Pipeline")
    print("="*60)

    # ── 1. LOAD ──────────────────────────────────────────────
    print("\n[1/5] Loading DICOM series...")
    volume, metadata = load_dicom_series(args.input)
    spacing = metadata["voxel_size_mm"]
    print(f"      Modality: {metadata['modality']}  |  "
          f"Slices: {metadata['n_slices']}  |  "
          f"Voxel: {spacing[0]:.2f} x {spacing[1]:.2f} x {spacing[2]:.2f} mm")

    # ── 2. PREPROCESS ────────────────────────────────────────
    print("\n[2/5] Preprocessing...")
    volume = remove_table(volume)
    volume, spacing = resample_volume(volume, spacing, target_spacing=[1.0, 1.0, 1.0])
    print(f"      Resampled to 1mm isotropic. New shape: {volume.shape}")

    # ── 3. VISUALIZE SLICES (optional) ──────────────────────
    if args.visualize:
        print("\n[3/5] Saving slice visualizations...")
        out_dir = os.path.dirname(args.output)
        show_slices(volume, title="CT Volume — Preprocessed",
                    save_path=os.path.join(out_dir, "../renders/slices.png"))
        if args.animate:
            save_slice_animation(volume,
                output_path=os.path.join(out_dir, "../renders/axial_scroll.gif"))
    else:
        print("\n[3/5] Skipping visualization (use --visualize to enable)")

    # ── 4. SEGMENT ──────────────────────────────────────────
    print(f"\n[4/5] Segmenting: {args.structure}...")
    if "bone" in args.structure:
        bone_type = "trabecular" if "trabecular" in args.structure else "cortical"
        verts, faces, normals = segment_bone(volume, spacing=spacing, bone_type=bone_type,
                                             sigma_override=args.sigma,
                                             sigma_z_override=args.sigma_z,
                                             threshold_override=args.threshold,
                                             bridge_mm=args.bridge)
    else:
        verts, faces, normals = segment_soft_tissue(volume, spacing=spacing)

    # ── 5. BUILD & EXPORT MESH ──────────────────────────────
    print("\n[5/5] Building and cleaning mesh...")
    mesh = build_mesh(verts, faces)
    mesh = keep_largest_component(mesh, min_ratio=args.min_component_ratio)
    if args.max_bodies is not None:
        mesh = filter_max_bodies(mesh, args.max_bodies)
    mesh = smooth_mesh(mesh, iterations=args.smooth)
    mesh = fix_mesh(mesh)

    if args.reorient:
        mesh = reorient_for_printing(mesh)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    export_stl(mesh, args.output)

    stats = get_mesh_stats(mesh)
    print(f"\n{'='*60}")
    print(f"  Pipeline complete!")
    print(f"  Output: {args.output}")
    if stats["volume_cm3"]:
        print(f"  Volume: {stats['volume_cm3']:.1f} cm³")
    print(f"  Dimensions: {[f'{d:.1f}mm' for d in stats['dimensions_mm']]}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(args)
