import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8080"
DICOM_DIR = Path("data/samples/foot")

# 1. UPLOAD
print("1. Subiendo archivos DICOM...")
files = [("files", (f.name, open(f, "rb"))) for f in DICOM_DIR.iterdir() if f.is_file()]
r = requests.post(f"{BASE_URL}/upload", files=files)
print(json.dumps(r.json(), indent=2))
upload_id = r.json()["upload_id"]

# 2. CREAR JOB
print("\n2. Creando job...")
r = requests.post(f"{BASE_URL}/jobs", json={
    "upload_id": upload_id,
    "structure": "bone",
    "threshold": 225,
    "sigma": 0.5,
    "sigma_z": 2.0,
    "smooth": 10,
    "min_component_ratio": 0.05,
    "max_bodies": 1,
    "reorient": True,
    "bridge": 0
})
print(json.dumps(r.json(), indent=2))
job_id = r.json()["job_id"]

# 3. STATUS
print("\n3. Status del job...")
r = requests.get(f"{BASE_URL}/jobs/{job_id}")
print(json.dumps(r.json(), indent=2))

# 4. DOWNLOAD
print("\n4. Descargando STL...")
r = requests.get(f"{BASE_URL}/jobs/{job_id}/download")
out = Path(f"output/stl/api_test_{job_id[:8]}.stl")
out.write_bytes(r.content)
print(f"STL guardado en {out} — {len(r.content) / 1e6:.2f} MB")