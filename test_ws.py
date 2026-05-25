"""
test_ws.py
----------
Integration test for Phase 2 async jobs + WebSocket progress.

Usage:
    python test_ws.py

Requires the server to be running:
    uvicorn api.main:app --host 127.0.0.1 --port 8080
"""

import asyncio
import json
import time
from pathlib import Path

import requests
import websockets

BASE = "http://127.0.0.1:8080"
WS_BASE = "ws://127.0.0.1:8080"


async def test():
    # ── 1. Upload foot DICOM ──────────────────────────────────────────────────
    foot_dir = Path("data/samples/foot")
    files = [
        ("files", (f.name, open(f, "rb"), "application/octet-stream"))
        for f in foot_dir.iterdir()
        if f.is_file()
    ]
    print(f"Uploading {len(files)} DICOM files...")
    r = requests.post(f"{BASE}/upload", files=files)
    r.raise_for_status()
    upload_id = r.json()["upload_id"]
    print(f"  upload_id: {upload_id}")

    # ── 2. POST /jobs — must return in < 1 second ─────────────────────────────
    payload = {
        "upload_id": upload_id,
        "structure": "bone",
        "threshold": 225,
        "sigma": 0.5,
        "sigma_z": 2.0,
        "smooth": 10,
        "min_component_ratio": 0.05,
        "max_bodies": 1,
        "reorient": True,
        "bridge": 0,
    }
    t0 = time.time()
    r = requests.post(f"{BASE}/jobs", json=payload)
    elapsed_ms = (time.time() - t0) * 1000
    r.raise_for_status()
    job = r.json()
    job_id = job["job_id"]
    print(f"\nPOST /jobs → status='{job['status']}' in {elapsed_ms:.0f} ms")
    assert job["status"] == "pending", f"Expected 'pending', got '{job['status']}'"
    assert elapsed_ms < 1000, f"POST /jobs took {elapsed_ms:.0f} ms — should be < 1000 ms"
    print("  ✓ returned pending in < 1 second")

    # ── 3. WebSocket progress ─────────────────────────────────────────────────
    uri = f"{WS_BASE}/ws/jobs/{job_id}"
    print(f"\nConnecting to WebSocket: {uri}")
    messages = []

    async with websockets.connect(uri) as ws:
        async for raw in ws:
            data = json.loads(raw)
            messages.append(data)
            pct = data.get("percent", "?")
            stage = data.get("stage", "?")
            msg = data.get("message", "")
            print(f"  [{pct:>3}%] {stage:<15} {msg}")
            if data.get("stage") in ("completed", "failed"):
                break

    # ── 4. Verify final state ─────────────────────────────────────────────────
    last = messages[-1]
    assert last["stage"] == "completed", f"Last stage was '{last['stage']}', expected 'completed'"
    metrics = last.get("metrics", {})
    print(f"\nFinal metrics:")
    print(f"  is_watertight : {metrics.get('is_watertight')}")
    print(f"  face_count    : {metrics.get('face_count'):,}")
    print(f"  volume_cm3    : {metrics.get('volume_cm3'):.1f}" if metrics.get('volume_cm3') else "  volume_cm3    : N/A")

    # ── 5. GET /jobs/{id} status transition ───────────────────────────────────
    r = requests.get(f"{BASE}/jobs/{job_id}")
    final_job = r.json()
    print(f"\nGET /jobs/{job_id[:8]}... → status='{final_job['status']}'")
    assert final_job["status"] == "completed"
    assert final_job["metrics"]["is_watertight"] is True

    # ── 6. Download STL ───────────────────────────────────────────────────────
    r = requests.get(f"{BASE}/jobs/{job_id}/download")
    r.raise_for_status()
    size_mb = len(r.content) / 1e6
    print(f"\nGET /jobs/{job_id[:8]}.../download → {size_mb:.2f} MB")
    assert size_mb > 1, "STL file seems too small"

    print("\n✓ All Phase 2 tests passed")
    print(f"\nWebSocket messages received ({len(messages)} total):")
    for m in messages:
        print(f"  [{m['percent']:>3}%] {m['stage']}")


if __name__ == "__main__":
    asyncio.run(test())
