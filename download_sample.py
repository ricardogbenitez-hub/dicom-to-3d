"""
download_sample.py
Downloads a DICOM series from The Cancer Imaging Archive (TCIA)
using the public NBIA REST API (no login required).

Supported datasets:
  colonography  CT Colonography — abdomen/pelvis bones (default)
  cranial       CPTAC-AML Head CT — skull / craniofacial structures
  foot          CMB-MEL Foot CT  — all 26 foot/ankle bones (bone kernel)

Usage:
    python download_sample.py
    python download_sample.py --dataset foot
    python download_sample.py --dataset cranial --output ./data/samples/brainix
    python download_sample.py --series <SeriesInstanceUID>
    python download_sample.py --output ./data/my_folder
"""

import argparse
import io
import os
import sys
import zipfile

import requests
from tqdm import tqdm

BASE_URL = "https://services.cancerimagingarchive.net/nbia-api/services/v1"

# ── Colonography (abdomen/pelvis, default) ────────────────────────────────────
COLONOGRAPHY_COLLECTION = "CT COLONOGRAPHY"
COLONOGRAPHY_OUTPUT     = os.path.join("data", "sample")
COLONOGRAPHY_MIN_SLICES = 300
COLONOGRAPHY_MAX_SLICES = 500
COLONOGRAPHY_BODY_PART  = None          # no filter needed

# ── Cranial (head CT, CPTAC-AML — publicly accessible, no login) ──────────────
# CPTAC-AML = Cancer Proteome Atlas - Acute Myeloid Leukemia.
# Staging workup routinely includes a non-contrast head CT.
# "Head WO" = Head Without contrast  →  clean HU values ideal for bone threshold.
CRANIAL_COLLECTION  = "CPTAC-AML"
CRANIAL_BODY_PART   = "HEAD"
CRANIAL_OUTPUT      = os.path.join("data", "samples", "cranial")
CRANIAL_MIN_SLICES  = 80
CRANIAL_MAX_SLICES  = 300

# ── Foot (CMB-MEL, bone kernel axial CT — publicly accessible, no login) ─────────
# CMB-MEL = Cancer Moonshot Biobank - Melanoma.
# Staging CTs include extremity scans; the FOOT series uses a dedicated bone
# reconstruction kernel (B40+) that sharpens cortical edges — ideal for the
# 26-bone foot anatomy (7 tarsals, 5 metatarsals, 14 phalanges).
FOOT_COLLECTION  = "CMB-MEL"
FOOT_BODY_PART   = "FOOT"
FOOT_OUTPUT      = os.path.join("data", "samples", "foot")
FOOT_MIN_SLICES  = 50
FOOT_MAX_SLICES  = 150
# Pin to the known-good bone-kernel axial series (83 slices, 43.8 MB)
FOOT_SERIES_UID  = "1.3.6.1.4.1.14519.5.2.1.1.19721033482203527319428560825963697198"

# Legacy alias — keeps backwards compatibility if other scripts reference this
COLLECTION    = COLONOGRAPHY_COLLECTION
DEFAULT_OUTPUT = COLONOGRAPHY_OUTPUT
MIN_SLICES    = COLONOGRAPHY_MIN_SLICES
MAX_SLICES    = COLONOGRAPHY_MAX_SLICES


def get_series_list(collection: str, body_part: str | None = None) -> list[dict]:
    """
    Query TCIA for all series in a collection.
    Optionally filter by BodyPartExamined (e.g. 'HEAD').
    Returns a list of dicts, each describing one imaging series.
    """
    url = f"{BASE_URL}/getSeries"
    params: dict = {"Collection": collection}
    if body_part:
        params["BodyPartExamined"] = body_part
    print(f"Querying TCIA for collection '{collection}'"
          + (f" / body part '{body_part}'" if body_part else "") + "...")
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def pick_series(
    series_list: list[dict],
    min_slices: int,
    max_slices: int,
    target_slices: int,
) -> dict:
    """
    Pick a CT series whose slice count falls in [min_slices, max_slices].
    Among qualifying series, picks the one closest to target_slices.

    Colonography: target 400 slices — covers full pelvis + spine.
    Cranial:      target 120 slices — covers full calvarium at ~1.5 mm/slice.
    """
    if not series_list:
        raise ValueError("No series returned from TCIA for this collection.")

    candidates = [
        s for s in series_list
        if s.get("Modality") == "CT"
        and min_slices <= int(s.get("ImageCount", 0)) <= max_slices
    ]

    if not candidates:
        # Show what was available to help the user debug
        counts = sorted(
            int(s.get("ImageCount", 0))
            for s in series_list
            if s.get("Modality") == "CT"
        )
        raise ValueError(
            f"No CT series found with {min_slices}–{max_slices} slices. "
            f"Available slice counts: {counts[:20]}"
        )

    return min(candidates, key=lambda s: abs(int(s.get("ImageCount", 0)) - target_slices))


def download_series(series_uid: str, output_dir: str) -> None:
    """
    Download a DICOM series by SeriesInstanceUID.

    TCIA's getImage endpoint returns a ZIP file containing all DICOM slices
    for that series. We stream the ZIP into memory, then extract each slice
    as a flat .dcm file into output_dir.
    """
    os.makedirs(output_dir, exist_ok=True)

    url = f"{BASE_URL}/getImage"
    print(f"Requesting ZIP from TCIA...")
    resp = requests.get(
        url,
        params={"SeriesInstanceUID": series_uid},
        stream=True,
        timeout=300,  # large CT series can take a while
    )
    resp.raise_for_status()

    total_bytes = int(resp.headers.get("Content-Length", 0))

    # Stream the ZIP into a memory buffer, showing download progress
    buffer = io.BytesIO()
    with tqdm(
        total=total_bytes or None,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc="Downloading",
        dynamic_ncols=True,
    ) as bar:
        for chunk in resp.iter_content(chunk_size=65536):
            buffer.write(chunk)
            bar.update(len(chunk))

    buffer.seek(0)

    # Extract DICOM files flat into output_dir.
    # TCIA ZIPs sometimes have files without .dcm extension (just numbered),
    # or nested in subdirectories — we handle both.
    print(f"\nExtracting DICOM files to {output_dir}/")
    with zipfile.ZipFile(buffer) as zf:
        members = [m for m in zf.namelist() if not m.endswith("/")]

        for member in tqdm(members, desc="Extracting", unit="file"):
            filename = os.path.basename(member)
            if not filename:
                continue

            # Ensure .dcm extension so pydicom picks them up automatically
            if not filename.lower().endswith(".dcm"):
                filename += ".dcm"

            dest = os.path.join(output_dir, filename)
            with zf.open(member) as src, open(dest, "wb") as dst:
                dst.write(src.read())

    extracted = [f for f in os.listdir(output_dir) if f.lower().endswith(".dcm")]
    print(f"\nDone. {len(extracted)} DICOM slices saved to {output_dir}/")
    print("Next step: run  python main.py --input ./data/sample --structure bone")


def print_series_info(series: dict) -> None:
    size_mb = int(series.get("FileSize", 0)) / 1_048_576
    print("\nSelected series:")
    print(f"  Patient ID      : {series.get('PatientID', 'N/A')}")
    print(f"  Modality        : {series.get('Modality', 'N/A')}")
    print(f"  Body Part       : {series.get('BodyPartExamined', 'N/A')}")
    print(f"  Slices          : {series.get('ImageCount', 'N/A')}")
    print(f"  File size       : {size_mb:.1f} MB")
    print(f"  Series UID      : {series.get('SeriesInstanceUID', 'N/A')}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download a DICOM series from TCIA (no login required).\n\n"
            "Datasets:\n"
            "  colonography  CT Colonography — abdomen/pelvis bones (default)\n"
            "  cranial       CPTAC-AML Head CT — skull / craniofacial structures\n"
            "  foot          CMB-MEL Foot CT  — all 26 foot/ankle bones (bone kernel)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        choices=["colonography", "cranial", "foot"],
        default="colonography",
        help="Which dataset to download (default: colonography)",
    )
    parser.add_argument(
        "--series",
        metavar="UID",
        help="SeriesInstanceUID to download directly (skips auto-selection)",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="DIR",
        help="Destination folder (default depends on --dataset)",
    )
    args = parser.parse_args()

    # ── Resolve config based on selected dataset ──────────────────────────────
    if args.dataset == "foot":
        collection  = FOOT_COLLECTION
        body_part   = FOOT_BODY_PART
        min_slices  = FOOT_MIN_SLICES
        max_slices  = FOOT_MAX_SLICES
        target      = 83
        output_dir  = args.output or FOOT_OUTPUT
        print("\n[Dataset] Foot CT  (CMB-MEL / FOOT, bone kernel, no login required)")
        print("[Note]    Bone reconstruction kernel — sharp cortical edges on all 26 bones.")
        print("          HU values calibrated. Bone threshold 400 HU works as-is.\n")
        # Use pinned UID for the known-good bone-kernel axial series
        if not args.series:
            args.series = FOOT_SERIES_UID
    elif args.dataset == "cranial":
        collection  = CRANIAL_COLLECTION
        body_part   = CRANIAL_BODY_PART
        min_slices  = CRANIAL_MIN_SLICES
        max_slices  = CRANIAL_MAX_SLICES
        target      = 120
        output_dir  = args.output or CRANIAL_OUTPUT
        print("\n[Dataset] Cranial CT  (CPTAC-AML / HEAD, no login required)")
        print("[Note]    These are non-contrast head CTs acquired for staging.")
        print("          HU values are fully calibrated — bone threshold 400 HU works as-is.\n")
    else:
        collection  = COLONOGRAPHY_COLLECTION
        body_part   = None
        min_slices  = COLONOGRAPHY_MIN_SLICES
        max_slices  = COLONOGRAPHY_MAX_SLICES
        target      = 400
        output_dir  = args.output or COLONOGRAPHY_OUTPUT
        print("\n[Dataset] CT Colonography  (abdomen/pelvis bones)\n")

    try:
        if args.series:
            series_uid = args.series
            print(f"Using provided SeriesInstanceUID: {series_uid}")
        else:
            series_list = get_series_list(collection, body_part)
            print(f"Found {len(series_list)} series in '{collection}'.")

            series = pick_series(series_list, min_slices, max_slices, target)
            print_series_info(series)
            series_uid = series["SeriesInstanceUID"]

        download_series(series_uid, output_dir)

    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not reach TCIA. Check your internet connection.")
        sys.exit(1)
    except requests.exceptions.HTTPError as exc:
        print(f"\nERROR: TCIA returned HTTP {exc.response.status_code}.")
        sys.exit(1)
    except zipfile.BadZipFile:
        print("\nERROR: Response was not a valid ZIP file.")
        print("The series UID may be invalid, or TCIA may be temporarily unavailable.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()
