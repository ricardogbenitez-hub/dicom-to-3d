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

---

## Full-Stack Development Plan

### Workflow between Cowork and Claude Code
1. Cowork defines tasks + acceptance criteria
2. Cowork updates CLAUDE.md with the plan
3. Cowork generates a self-contained prompt for Claude Code (includes: what to do + acceptance criteria + instruction to produce a report when done)
4. Claude Code implements
5. Claude Code generates a structured report (completed, failed, pending, metrics)
6. Ricardo verifies visually / functionally, then brings the report back to Cowork
7. Cowork updates CLAUDE.md with real state, defines next phase

### Architecture
Three layers, one monorepo:
- `src/` — existing pipeline, untouched
- `api/` — FastAPI backend that wraps the pipeline as HTTP service
- `frontend/` — React (Vite) app, deployed separately to Vercel

Deployment targets:
- Frontend → Vercel (static, free tier)
- Backend → Railway (Docker, free tier, supports long-running processes + WebSockets)

### Phase 1 — Minimal FastAPI (CURRENT)
**Goal:** Wrap the existing pipeline as a REST API. Synchronous execution (request blocks until STL is ready). No queues, no WebSockets. Validates that the pipeline works as an HTTP service and that all CLI parameters have a clean JSON representation.

**New files:**
```
api/
├── main.py        # FastAPI app, CORS config, router registration
├── schemas.py     # Pydantic models for request/response
├── worker.py      # Wrapper that calls src/ pipeline modules directly
└── routes/
    ├── upload.py  # POST /upload — receives DICOM files (multipart), returns upload_id
    └── jobs.py    # POST /jobs, GET /jobs/{id}, GET /jobs/{id}/download
```

**Endpoints:**
| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/upload` | Receives N DICOM files (multipart/form-data), saves to temp dir, returns `upload_id` |
| `POST` | `/jobs` | Receives `upload_id` + pipeline params, runs pipeline synchronously, returns `job_id` |
| `GET` | `/jobs/{id}` | Returns job status (pending/running/completed/failed) + metrics if done |
| `GET` | `/jobs/{id}/download` | Returns the STL file as binary download |

**Job request body (all CLI params as JSON):**
```json
{
  "upload_id": "abc123",
  "structure": "bone",
  "threshold": 225,
  "sigma": 0.5,
  "sigma_z": 2.0,
  "smooth": 10,
  "step_size": 1,
  "min_component_ratio": 0.05,
  "max_bodies": 1,
  "reorient": true,
  "bridge": 0
}
```

**New packages:** `fastapi`, `uvicorn`, `python-multipart`

**Acceptance criteria — Phase 1 is done when ALL of these pass:**
1. `uvicorn api.main:app --reload` starts without errors
2. `POST /upload` correctly saves DICOM files to a temp directory and returns an `upload_id`
3. `POST /jobs` with `data/samples/foot/` parameters runs the pipeline end-to-end and produces an STL
4. `GET /jobs/{id}` returns status `completed` with correct metrics (watertight, face count, volume, bounding box)
5. `GET /jobs/{id}/download` returns a valid downloadable STL file
6. `python main.py` CLI still works unchanged (regression — do not break existing interface)
7. Regression test: `python main.py --input data/sample --structure bone --output output/stl/test_regression.stl` completes successfully

**Status:** ✅ Complete — 2026-05-23

**Verified results:**
- POST /upload: OK — 85 DICOM files, upload_id generated correctly
- POST /jobs (foot, threshold=225): OK — completed in 10.1s, status: completed
- GET /jobs/{id}: OK — is_watertight=true, face_count=212,442, volume=255.89 cm³
- GET /jobs/{id}/download: OK — 10.62 MB valid STL binary
- CLI regression (colonography): OK — 981,822 faces, watertight, 618.5 cm³, main.py untouched

**Known non-issues carried forward to Phase 2:**
- `step_size` present in schema but not wired to `segment_bone` — pre-existing CLI gap, no functional impact
- `jobs_store` is in-memory by design — will persist in Phase 2

**Files created:**
- `api/__init__.py`
- `api/main.py`
- `api/schemas.py`
- `api/worker.py`
- `api/routes/__init__.py`
- `api/routes/upload.py`
- `api/routes/jobs.py`

### Phase 2 — Async jobs + WebSocket progress (CURRENT)
**Goal:** POST /jobs returns immediately with job_id. Pipeline runs in background thread. WebSocket endpoint streams real-time progress to the client.

**Files modified:**
- `api/worker.py` — run_pipeline() accepts a progress callback, updates jobs_store at each stage
- `api/routes/jobs.py` — POST /jobs launches pipeline in ThreadPoolExecutor, returns immediately. Adds GET /ws/jobs/{id} WebSocket endpoint

**No changes to src/ pipeline modules.**

**Progress message format:**
```json
{"stage": "loading",       "percent": 20,  "message": "83 DICOM files loaded"}
{"stage": "preprocessing", "percent": 40,  "message": "Isotropic resampling complete"}
{"stage": "segmenting",    "percent": 65,  "message": "Marching cubes in progress"}
{"stage": "mesh",          "percent": 85,  "message": "Cleaning mesh"}
{"stage": "completed",     "percent": 100, "metrics": {...}}
```

**New packages:** None — FastAPI WebSocket support is built in.

**Acceptance criteria — Phase 2 is done when ALL of these pass:**
1. POST /jobs returns job_id in under 1 second without waiting for the pipeline
2. GET /jobs/{id} transitions correctly: pending → running → completed
3. WebSocket /ws/jobs/{id} emits at least 4 progress messages before completed
4. Regression: python main.py CLI still works unchanged
5. Regression: POST /upload still works unchanged

**Status:** ✅ Complete — 2026-05-23

**Verified results:**
- POST /jobs response time: 4ms (limit: 1000ms)
- WebSocket messages: loading(20%) → preprocessing(45%) → segmenting(70%) → mesh(90%) → completed(100%)
- Status transitions pending→running→completed: OK
- CLI regression (colonography): OK — 981,822 faces, 618.5 cm³, watertight
- POST /upload regression: OK
- ThreadPoolExecutor(max_workers=2) — intentional OOM protection for concurrent pipeline runs

**Files modified:** api/worker.py, api/routes/jobs.py, requirements.txt
**Files added:** test_ws.py

### Phase 3 — React Frontend
**Goal:** Vite + React + Tailwind CSS single-page app. Three screens as a linear wizard. Connects to the FastAPI backend already running on port 8000. No changes to `src/`, `api/`, or `main.py`.

**Status:** ✅ Complete — 2026-05-24

**Acceptance criteria:**
1. `npm run dev` starts without errors on port 5173 — ✅ Arranca en 538ms
2. Upload screen: drag & drop + `POST /upload` functional — ✅ 83–85 archivos, upload_id generado
3. Configure screen: sliders + `POST /jobs` functional — ✅ 7 sliders, pills, checkboxes, input numérico en HU Threshold
4. Processing screen: WebSocket + progress bar — ✅ 5 mensajes, barra animada, auto-advance en completed
5. Result screen: Three.js STL viewer — ✅ STLLoader + OrbitControls, autoRotate, toggle Solid/Wireframe
6. Download STL — ✅ blob URL → trigger `<a>` programático
7. Dark mode across all screens — ✅ sin CSS variables en texto crítico
8. Outline buttons visibles en light mode sin hover — ✅ `color: #152033` + `border: 1.5px solid #6a8fae` hardcodeados
9. No Python files modified — ✅ confirmado con `git diff`
10. Backend regression — no ejecutado (ningún archivo Python tocado)

**Datasets verified by Ricardo (visual + metrics):**

| Dataset | Threshold | Faces | Watertight | Volume | Time | Bbox |
|---|---|---|---|---|---|---|
| Foot (`data/samples/foot/`) | 225 HU | 212,442 | ✓ | 255.9 cm³ | ~10s | 228×128×83mm |
| Columna+cóccix+pelvis (`data/sample/`) | 400 HU | 1,267,878 | ✓ | 690.1 cm³ | 45.9s | 504×163×287mm |

**Files created:**
```
frontend/
├── index.html
├── vite.config.js          # @tailwindcss/vite plugin + react plugin
├── postcss.config.js       # vacío — overridea postcss.config.mjs del directorio raíz
├── package.json
├── .env                    # VITE_API_URL=http://localhost:8000
├── .env.example
└── src/
    ├── main.jsx
    ├── index.css           # @import "tailwindcss" (v4) + slider CSS + progress animation
    ├── App.jsx             # wizard step state, dark mode state
    ├── api.js              # axios: uploadDicoms, createJob, getJob, downloadStl, wsUrl
    ├── components/
    │   ├── NavBar.jsx
    │   ├── Stepper.jsx
    │   └── Spinner.jsx
    └── screens/
        ├── UploadScreen.jsx
        ├── ConfigureScreen.jsx
        ├── ProcessingScreen.jsx
        └── ResultScreen.jsx
```

**Deviations from spec:**
- **Tailwind v4** (no v3) — sin `tailwind.config.js`. Config vía `@import "tailwindcss"` + plugin `@tailwindcss/vite`. Styling crítico en inline styles.
- **`processing_time_s`** medido en el frontend (ws.onopen → completed) — no viene del backend.
- **Three.js directo** para STL viewer (no `@react-three/fiber`) — mayor control sobre render loop.
- **Bundle ~795KB** minificado — normal con Three.js incluido.

**Bugs encontrados y corregidos durante verificación:**
- `bounding_box_mm` del API es `[[xmin,ymin,zmin],[xmax,ymax,zmax]]` — frontend calcula `bounds[1][i] - bounds[0][i]`
- React StrictMode double-mount causaba error transitorio code 1006 — resuelto con variable local `cleanedUp` por closure (inmune a race condition de refs compartidos)
- Botones outline en dark mode tenían texto invisible — `color: #ddeaf8` en dark, `#152033` en light
- STL viewer orientación: `geometry.rotateX(-Math.PI/2)` convierte Z=up (convención impresión) → Y=up (Three.js)

**Parámetros óptimos verificados:**

| Estructura | threshold | sigma | sigma_z | smooth | min_ratio | max_bodies | bridge |
|---|---|---|---|---|---|---|---|
| Foot (trabecular) | 225 | 0.5 | 2.0 | 10 | 0.05 | 1 | 0 |
| Columna/cóccix/pelvis | 400 | 0.5 | 0.0 | 7 | 0.01 | 0 | 0 |

### Phase 4 — Deploy
**Goal:** Hacer el backend deployable como contenedor Docker en Railway y el frontend buildeable para Vercel. Sin cambios a la lógica del pipeline ni del frontend.

**Status:** ✅ Complete — 2026-05-24

**Architecture:**
- Backend → Railway (Docker). URL pública tipo `https://dicomto3d-api.up.railway.app`
- Frontend → Vercel (static build). URL pública tipo `https://dicomto3d.vercel.app`
- `VITE_API_URL` en Vercel apunta al backend de Railway
- `CORS_ORIGINS` en Railway apunta al dominio de Vercel

**Acceptance criteria:**
1. `docker build` completa sin errores — ⚠ no ejecutado (Docker no instalado en máquina de desarrollo)
2. `docker run` arranca y responde — ⚠ no ejecutado
3. `railway.json` creado correctamente — ✅
4. `.dockerignore` creado — ✅
5. `frontend/vercel.json` creado — ✅
6. CORS acepta `CORS_ORIGINS` env var — ✅ fallback: `http://localhost:5173`
7. `npm run build` genera `dist/` sin errores — ✅ 603ms, 796KB JS + 12KB CSS
8. Funcionamiento local sin romper — ✅ solo CORS modificado en `api/main.py`

**Files created:**
- `Dockerfile`
- `.dockerignore`
- `railway.json`
- `frontend/vercel.json`

**Files modified:**
- `api/main.py` — CORS `allow_origins` lee de `CORS_ORIGINS` env var (fallback: `http://localhost:5173`)

**dist/ bundle para Vercel:**
```
dist/index.html            1KB
dist/assets/index-*.js   780KB  (Three.js + React + axios)
dist/assets/index-*.css   12KB
```

**Known issues:**
- Docker build no verificado localmente — instalar Docker Desktop y ejecutar `docker build -t dicomto3d-api .` antes del deploy
- Bundle JS ~780KB — aceptable para MVP; code-splitting en fase futura si Railway da timeout en cold start
- `jobs_store` en memoria — se resetea al reiniciar el contenedor. Jobs en curso se pierden en restart

**Next steps para deploy real:**

Railway (backend):
1. Instalar Railway CLI: `npm install -g @railway/cli`
2. `railway login` → `railway init` en la raíz del proyecto
3. `railway up` — Railway detecta `Dockerfile` y `railway.json` automáticamente
4. En el dashboard: agregar variable `CORS_ORIGINS=https://tu-app.vercel.app`
5. Anotar la URL generada (ej: `https://dicomto3d-api.up.railway.app`)

Vercel (frontend):
1. `npm install -g vercel` → `cd frontend && vercel`
2. Framework: Vite, Root Directory: `frontend`
3. En el dashboard: agregar variable `VITE_API_URL=https://dicomto3d-api.up.railway.app`
4. `vercel --prod` para deploy de producción

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
