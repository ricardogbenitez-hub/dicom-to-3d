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

## Development status — last updated 2026-05-20

Pipeline complete and working end-to-end on all tested datasets.

## What is implemented

### Pipeline modules
- `loader.py` — loads DICOM series, sorts by ImagePositionPatient Z, converts to HU, skips non-DICOM files
- `preprocessor.py` — table removal, isotropic resampling to 1mm³
- `segmentor.py` — anisotropic Gaussian, `_zero_borders`, `closing(ball(2))`, optional bridge closing, `binary_fill_holes`, Marching Cubes
- `mesh_utils.py` — `keep_largest_component`, `filter_max_bodies`, `fix_mesh` (trimesh + pymeshfix per component), `reorient_for_printing`, export STL
- `visualizer.py` — slice viewer, GIF animation, matplotlib 3D mesh render (4 views, no OpenGL)
- `main.py` — full CLI

### CLI args (complete list)
| Arg | Default | Notes |
|-----|---------|-------|
| `--input` | required | Path to DICOM folder |
| `--output` | required | Output STL path |
| `--structure` | `bone` | `bone`, `cortical_bone`, `trabecular_bone`, `soft_tissue` |
| `--smooth INT` | 5 | Laplacian iterations. **Max 10** — 15+ breaks watertightness |
| `--step-size INT` | 1 | Marching Cubes resolution. 2 = half res, faster |
| `--min-component-ratio FLOAT` | 0.01 | Fragment filter. For foot: **0.05** |
| `--max-bodies N` | off | Keep only N largest components. For foot: **1** |
| `--reorient` | off | Longest axis → X, flat on Z=0 |
| `--sigma FLOAT` | 1.0 | Isotropic Gaussian sigma, or XY sigma when `--sigma-z` also set |
| `--sigma-z FLOAT` | off | Z-axis sigma (anisotropic mode). For foot: **2.0** |
| `--threshold FLOAT` | 400 | HU isovalue. For foot trabecular: **225** |
| `--bridge INT` | 0 | Bridge inter-bone gaps (mm). Fuses adjacent bones into one solid. For foot: **4** |
| `--visualize` | off | Save slice views and mesh preview |
| `--animate` | off | Save axial slice animation GIF |

### Key architectural decisions in segmentor.py
- `_zero_borders(mask, BORDER=4)` — zeros 4-voxel border on all faces BEFORE closing/fill_holes. Prevents sigma-blurred bone from touching the volume wall, which would cause `binary_fill_holes` to seal the wall and create a flat "skirt" artifact.
- Anisotropic sigma via `(sigma_z, sigma_xy, sigma_xy)` tuple — `skimage.filters.gaussian` accepts per-axis sigma. High Z sigma bridges 3mm inter-slice artifacts without eroding thin structures like metatarsal shafts.
- `closing(ball(2))` before `binary_fill_holes` — bridges 1-2mm tarsal cartilage gaps. `binary_fill_holes` only fills enclosed voids; closing handles surface-open gaps first.
- `bridge_radius` optional second closing — larger ball to intentionally fuse adjacent bones into one solid model.

### Threshold guide by structure type
| Structure | Threshold | Reasoning |
|-----------|-----------|-----------|
| Axial skeleton (spine, pelvis, femur) | 400 HU | Thick cortex, default |
| Extremity small bones (foot, wrist, ankle) | 200–250 HU | Predominantly trabecular — cortex alone gives perforated shells |
| Trabecular detail | 150 HU | Full cancellous architecture |
| Soft tissue | 40–80 HU | Via `--structure soft_tissue` |

### Do not repeat — lessons from foot CT iteration
- **sigma=2.0 isotropic** → erodes metatarsals to hollow tubes (kernel reaches shaft center), foot shrinks 25%
- **threshold=400 for foot** → only cortical shell captured, calcaneus full of holes
- **threshold=350** → trabecular partially captured by partial-volume effect, calcaneus becomes blob
- **ball(3) closing (no border zeroing)** → 28% volume increase, risks fusing phalanges
- **smooth=15** → breaks watertightness; hard limit is 10 iterations

## Current problem — RESOLVED ✓

**Dataset:** `data/samples/foot/` — 83 slices, 3mm slice thickness, foot CT

**Best result:** `output/stl/foot_t225.stl`
```
python main.py --input data/samples/foot --structure bone \
  --output output/stl/foot_t225.stl \
  --smooth 10 --min-component-ratio 0.05 --max-bodies 1 --reorient \
  --sigma-z 2.0 --sigma 0.5 --threshold 225
```
**Metrics:** watertight=True, 212,442 faces, 228×127×82mm, 255.9 cm³

**Visual state:** Foot is anatomically recognizable. Calcaneus has correct rounded heel shape. Metatarsals clearly defined as 5 rays. Longitudinal arch visible. Tarsal region smooth and connected. Individual bones are not fully separable — this is a fundamental limitation of 3mm slice CT, not a pipeline deficiency.

**Key insight that unlocked the result:**
The original threshold=400 HU (cortical only) was wrong for foot bones. The calcaneus, cuboid, cuneiforms and navicular are predominantly trabecular bones. Their trabecular core is 150-300 HU. At 400 HU we only captured thin perforated cortical shells → holes everywhere. At 225 HU we capture the full bone volume (cortex + dense trabecular) → solid, correct anatomy.

**Threshold exploration done (all use --sigma-z 2.0 --sigma 0.5 --smooth 10):**
| Threshold | Volume  | Visual result |
|-----------|---------|---------------|
| 400 HU    | 132 cm³ | Holes in calcaneus, tarsal chaos |
| 350 HU    | 163 cm³ | Better but calcaneus still rough |
| 300 HU    | 199 cm³ | Good shape, some bone distinction |
| 250 HU    | 235 cm³ | Very good, slightly overfilled |
| **225 HU**| **256 cm³** | **Best — solid anatomy, correct proportions** |
| 200 HU    | 275 cm³ | Good but slightly over-captures soft tissue |

**Remaining minor issues (acceptable for this dataset resolution):**
- Ankle/fibula protrusion at top of heel — CT scan includes lower leg
- Individual tarsal bones not distinguishable (inherent 3mm limitation)
- Some small surface pits on calcaneus inferior surface

## Datasets available locally
- `data/sample/` — CT Colonography, 400 slices, 0.66mm in-plane, 1.25mm Z. Pelvis + spine + femoral heads. Pipeline works cleanly on this dataset. Reference for regression testing.
- `data/samples/foot/` — Foot CT, 83 slices, 3mm Z, 0.32mm in-plane. **DONE — best result at threshold=225.**

## Commit state
All changes uncommitted. Ready to commit.

## Notes for Claude
- Prioritize clean, readable, well-commented code over clever abstractions
- Each module should work independently and be testable on its own
- The README and visual outputs (renders, GIFs) are as important as the code itself
- When suggesting approaches, explain the clinical/anatomical reasoning, not just the code
- Ricardo checks visual results in Creality Print before committing — never claim success without visual confirmation
- Do not mention King's College London anywhere in the project

---

## Workflow Orchestration

### 1. Plan Before Touching Code
- For ANY non-trivial change (touching more than one module, or changing pipeline logic): write a plan first
- The plan must name which file(s) change, what the function signature looks like before and after, and what the acceptance test is
- If a fix attempt fails once, STOP and re-plan — do not keep iterating blind changes
- Use plan mode for verification steps, not just for building
- This is especially important for `segmentor.py` and `mesh_utils.py` — errors there cascade through the entire pipeline

### 2. Subagent Strategy
- Offload isolated explorations to subagents: "what HU threshold range works for foot cortical bone", "what does morphological closing do to a binary mask at 3mm resolution"
- Do not mix research tasks and code edits in the same context — keep the main thread clean
- One task per subagent: don't ask a subagent to both analyze AND fix

### 3. Self-Improvement Loop
- After any correction from Ricardo: note the pattern explicitly — what assumption was wrong and why
- Common failure modes in this project to watch for:
  - Assuming `min_ratio=0.01` is safe for all datasets — it is not (foot vs. pelvis behave differently)
  - Forgetting the filesystem sync step after editing `.py` files (stale `.pyc` bytecode)
  - Calling pymeshfix on a multi-body mesh without splitting first — it silently drops all but the largest body
  - Claiming a mesh is "clean" without checking `is_watertight`, face count, and bounding box dimensions

### 4. Verification Before Done
- A change is NOT complete until the pipeline runs end-to-end and produces a valid STL
- Minimum checks after any pipeline change:
  1. `python main.py --input data/sample --structure bone --output output/stl/test_regression.stl` — colonography must still work (regression)
  2. For foot work: run against `data/samples/foot/` and report `is_watertight`, face count, component count, bounding box
  3. Ricardo visually inspects the result in Creality Print — do not claim visual success without this confirmation
- Never mark a task complete based on "no errors thrown" alone — the pipeline can complete silently and produce garbage geometry

### 5. Filesystem Sync (Known Gotcha — Do Not Skip)
- After editing ANY `.py` file with the Edit tool, always run:
  ```bash
  touch src/segmentor.py src/mesh_utils.py main.py
  find . -name "*.pyc" -delete
  find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
  ```
- Python will silently use stale `.pyc` bytecode if the `.py` mtime is not newer — this has caused hours of debugging in this project
- This is a Windows-mounted filesystem in a Linux sandbox; Edit tool and bash see the same files but timestamps can diverge

### 6. Autonomous Bug Fixing
- When given a bug: read the relevant module fully before proposing a fix
- Point to the specific line and explain why it produces the wrong output before touching anything
- Zero unnecessary context-switching: don't ask Ricardo to run intermediate commands unless you genuinely need the output to proceed
- For mesh artifacts: always distinguish between surface artifacts (fixable in `mesh_utils.py`) and segmentation artifacts (root cause in `segmentor.py`) — treating the wrong layer wastes iterations

---

## Task Management

1. **Plan First**: Before any non-trivial edit, state which file changes, what the function does before/after, and what the test is
2. **Verify Plan**: Confirm approach before implementing — especially for segmentor or mesh_utils changes
3. **Track Progress**: List steps and mark them complete as you go
4. **Explain Changes**: For each edit, one-line summary of what changed and why (clinical + technical)
5. **Document Results**: After a successful run, update the "Current problem" section in this file with the new state
6. **Regression Test**: Always confirm `data/sample/` (colonography) still works after any pipeline change

---

## Core Principles

- **Simplicity First**: Make each change as small as possible. Touch only the module that owns the problem.
- **No Lazy Fixes**: Find the anatomical root cause. A 3mm slice thickness problem is not fixed by more smoothing iterations — it requires the right preprocessing strategy.
- **Minimal Impact**: Changes to `segmentor.py` must not break `mesh_utils.py` behavior. Changes to `main.py` args must not change default behavior for existing users.
- **Clinical Accuracy Over Aesthetics**: A watertight mesh with correct anatomical proportions is the goal. A smooth but geometrically wrong model is worse than a rough correct one.
- **Explain the Why**: Every non-obvious parameter choice (HU threshold, sigma, min_ratio, ball radius) must have a comment explaining the anatomical reasoning behind it.
