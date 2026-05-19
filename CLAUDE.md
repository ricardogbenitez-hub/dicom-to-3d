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

## Development status
See TODO section below. Always update this file when significant progress is made.

## Current TODO
- [ ] `loader.py` — load DICOM series from folder, sort by slice position, return 3D numpy array
- [ ] `preprocessor.py` — HU windowing (bone window: 400/1000, soft tissue: 40/400), normalization
- [ ] `segmentor.py` — Otsu thresholding + marching cubes surface extraction
- [ ] `mesh_utils.py` — mesh smoothing (Laplacian), remove small disconnected components, export STL
- [ ] `visualizer.py` — matplotlib slice viewer, trimesh 3D preview
- [ ] `main.py` — CLI: `python main.py --input ./data/sample --structure bone --output ./output/stl`
- [ ] `pipeline_demo.ipynb` — end-to-end walkthrough with visualizations
- [ ] README with renders, clinical context, and usage instructions

## Notes for Claude
- Prioritize clean, readable, well-commented code over clever abstractions
- Each module should work independently and be testable on its own
- The README and visual outputs (renders, GIFs) are as important as the code itself
- When suggesting approaches, explain the clinical/anatomical reasoning, not just the code
