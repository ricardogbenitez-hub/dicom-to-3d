# DICOM to 3D Surgical Model Converter
## Project context for Claude

This is a Python project by **Ricardo Garza Benítez**, Biomedical Engineering student at Universidad de Monterrey (6th semester). Ricardo is:
- Doing research in medical imaging (DICOM, MRI/CT preprocessing, CNNs)
- Working on physical anatomical models for surgical simulation
- Intermediate Python level — can write functional scripts and use libraries, but has not built large software systems before

## What this project does
Takes DICOM medical imaging data (CT/MRI scans) of anatomical structures and converts them into 3D models exportable as `.STL` files — ready for 3D printing or surgical simulation. Target structures: bones (femur, skull, vertebrae) and organs.

## Tech stack
- `pydicom` — DICOM file loading and parsing
- `SimpleITK` or `scikit-image` — image preprocessing, normalization, thresholding
- `scikit-image` marching cubes — surface extraction from volumetric data
- `trimesh` — mesh processing, cleaning, STL export
- `vtk` (optional) — advanced rendering and visualization
- `matplotlib` / `numpy` — general processing and plotting
- `tqdm` — progress bars

## Project structure
```
dicom-to-3d/
├── src/
│   ├── loader.py        # DICOM loading and series handling
│   ├── preprocessor.py  # Normalization, windowing, filtering
│   ├── segmentor.py     # Thresholding + marching cubes
│   ├── mesh_utils.py    # Mesh cleaning, smoothing, STL export
│   └── visualizer.py    # 2D slice viewer + 3D preview
├── data/
│   └── sample/          # Sample DICOM series go here (not committed to git)
├── output/
│   ├── stl/             # Generated STL files
│   └── renders/         # PNG/GIF renders of 3D models
├── notebooks/
│   └── pipeline_demo.ipynb   # Interactive walkthrough of full pipeline
├── docs/
│   └── clinical_context.md   # Why this matters medically
├── main.py              # CLI entry point
├── requirements.txt
├── README.md
└── CLAUDE.md            # This file
```

## Public DICOM datasets to use
- **TCIA (The Cancer Imaging Archive)**: https://www.cancerimagingarchive.net — free, no login required for many collections
  - Good starter: "CT Colonography" or "Visible Human" collections
- **OsiriX DICOM Sample Files**: https://www.osirix-viewer.com/resources/dicom-image-library/
- **Embodi3D**: community-shared medical 3D models with source DICOM

## Development status — last updated 2026-05-19

The full pipeline is working end-to-end. All core modules are implemented.
Active dataset for foot work: `data/samples/foot/` (83 slices, 3mm thickness, bone kernel axial CT).

## What is implemented (do not redo)

### Pipeline modules — all complete
- `loader.py` — loads DICOM series, sorts by ImagePositionPatient Z, converts to HU, skips non-DICOM files
- `preprocessor.py` — table removal, isotropic resampling to 1mm³
- `segmentor.py` — Gaussian smoothing (σ=1.0 cortical, σ=1.5 trabecular), `binary_fill_holes` before Marching Cubes (`fill_cavities=True` for bone), Marching Cubes at HU isovalue
- `mesh_utils.py` — multi-component aware: `keep_largest_component` (min_faces=500, min_ratio=1%), `filter_max_bodies`, `_fix_single` + `fix_mesh` (repairs each body individually with trimesh + pymeshfix), `reorient_for_printing` (rotates longest axis to X, puts flat on Z=0), export STL
- `visualizer.py` — slice viewer, GIF animation, matplotlib 3D mesh render (4 views, no OpenGL)
- `main.py` — full CLI with: `--input`, `--output`, `--structure`, `--smooth`, `--step-size`, `--min-component-ratio`, `--max-bodies`, `--reorient`, `--visualize`, `--animate`

### CLI args added this session
- `--min-component-ratio FLOAT` — filter small fragments (default 0.01). For foot: 0.02
- `--max-bodies N` — keep only N largest components. For foot: 1
- `--reorient` — rotate mesh so long axis = X, flat on Z=0. Use for foot, femur, tibia

### Key bugs fixed this session (v2)
1. `fix_mesh`: two-stage repair (trimesh fill_holes → pymeshfix), extra 5 Laplacian iterations inside fix
2. `segment_bone`: σ=1.5 for trabecular vs σ=1.0 for cortical
3. `keep_largest_component`: retains ALL components ≥ max(500, 1% of total faces), not just largest
4. `fix_mesh` multi-body: repairs each component individually to prevent pymeshfix dropping all but largest
5. `extract_surface`: `binary_fill_holes` closes hollow trabecular interiors before Marching Cubes
6. `reorient_for_printing`: fixes standing-upright orientation from CT scanner coordinate system

## Current problem — UNRESOLVED (start here next session)

**Dataset:** `data/samples/foot/` — 83 slices, 3mm slice thickness, foot CT  
**Command last run:**
```
python main.py --input data/samples/foot --structure bone \
  --output output/stl/footv3.stl \
  --min-component-ratio 0.02 --max-bodies 1 --smooth 8 --reorient
```
**Result:** `footv3.stl` — watertight, 176,416 faces, 160×102×73mm  
**Visual problem:** Still artifacts in the tarsal region (midfoot chaos). The 3mm slice thickness causes adjacent tarsal bones (cuboid, cuneiformes, navicular) to fuse incorrectly and create irregular surface. `binary_fill_holes` helped with interior voids but the external surface still has artifacts from inter-bone fusion at thick slices.

**What was NOT tried yet:**
- Morphological closing (`binary_closing(mask, ball(r))`) with r=2 or r=3 before fill_holes to smooth inter-bone gaps
- Lower HU threshold (e.g. 350 instead of 400) to capture less-dense foot bones more completely
- `--step-size 2` to reduce resolution and smooth the surface at the cost of detail
- Increasing sigma to 2.0 specifically for the foot dataset

**Files to focus on:** `src/segmentor.py` (morphological closing), `src/mesh_utils.py` if needed

## Datasets available locally
- `data/sample/` — CT Colonography, 400 slices, 0.66mm in-plane, 1.25mm Z. Pelvis + spine + femoral heads. Pipeline works cleanly on this dataset. Reference for regression testing.
- `data/samples/foot/` — Foot CT, 83 slices, 3mm Z, 0.32mm in-plane. Problem dataset.

## Commit state
Uncommitted changes in this session:
- `src/segmentor.py` — binary_fill_holes added
- `src/mesh_utils.py` — filter_max_bodies, reorient_for_printing added
- `main.py` — --max-bodies, --reorient args added
- `README.md` — updated for v2 (pymeshfix, adaptive sigma)
Ricardo will commit when foot STL is visually acceptable.

## Notes for Claude
- Prioritize clean, readable, well-commented code over clever abstractions
- Each module should work independently and be testable on its own
- The README and visual outputs (renders, GIFs) are as important as the code itself
- When suggesting approaches, explain the clinical/anatomical reasoning, not just the code
- Ricardo checks visual results in Creality Print before committing — never claim success without visual confirmation
- Do not mention King's College London anywhere in the project
