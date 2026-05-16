"""
download_sample.py
Downloads a CT-COLONOGRAPHY DICOM series from The Cancer Imaging Archive (TCIA)
into ./data/sample/ using the public NBIA REST API (no login required).

Usage:
    python download_sample.py
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
COLLECTION = "CT COLONOGRAPHY"  # exact name as returned by the TCIA API
DEFAULT_OUTPUT = os.path.join("data", "sample")
MIN_SLICES = 300  # lower bound for a quality render series
MAX_SLICES = 500  # upper bound to keep download manageable (~250 MB max)


def get_series_list(collection: str) -> list[dict]:
    """
    Query TCIA for all series in a collection.
    Returns a list of dicts, each describing one imaging series.
    """
    url = f"{BASE_URL}/getSeries"
    print(f"Querying TCIA for collection '{collection}'...")
    resp = requests.get(url, params={"Collection": collection}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def pick_series(series_list: list[dict]) -> dict:
    """
    Pick a CT series with between MIN_SLICES and MAX_SLICES slices.

    CT-COLONOGRAPHY scans cover the abdomen and pelvis — every series
    includes pelvic bones, spine, and femoral heads. A 300–500 slice
    series gives enough Z-depth for the mesh to be watertight and for
    renders to show clear bone anatomy.
    """
    if not series_list:
        raise ValueError("No series returned from TCIA for this collection.")

    candidates = [
        s for s in series_list
        if s.get("Modality") == "CT"
        and MIN_SLICES <= int(s.get("ImageCount", 0)) <= MAX_SLICES
    ]

    if not candidates:
        raise ValueError(
            f"No CT series found with {MIN_SLICES}–{MAX_SLICES} slices. "
            f"Try widening the range."
        )

    # Among qualifying series, pick the one closest to 400 slices (middle of range)
    # for a balance of quality and download size
    return min(candidates, key=lambda s: abs(int(s.get("ImageCount", 0)) - 400))


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
        description="Download a CT-COLONOGRAPHY DICOM series from TCIA."
    )
    parser.add_argument(
        "--series",
        metavar="UID",
        help="SeriesInstanceUID to download (default: auto-select first available)",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        metavar="DIR",
        help=f"Destination folder (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    try:
        if args.series:
            series_uid = args.series
            print(f"Using provided SeriesInstanceUID: {series_uid}")
        else:
            series_list = get_series_list(COLLECTION)
            print(f"Found {len(series_list)} series in '{COLLECTION}'.")

            series = pick_series(series_list)
            print_series_info(series)
            series_uid = series["SeriesInstanceUID"]

        download_series(series_uid, args.output)

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
