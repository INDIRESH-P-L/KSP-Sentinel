"""
Pulls the Karnataka Police FIR dataset from Kaggle straight into this repo's existing
ingestion path, instead of the manual browse -> download -> unzip -> re-upload workflow.

Auth: this script never touches your Kaggle token directly. kagglehub reads it itself
from (in order) ~/.kaggle/access_token, a kaggle.json, or the KAGGLE_USERNAME /
KAGGLE_KEY environment variables -- set one of those up first via
`kaggle.com -> account -> API -> Create New API Token`, then rotate it immediately if
it was ever pasted anywhere in plaintext (chat, screenshot, etc).

Usage:
    python scripts/ingest_kaggle_fir_dataset.py [--dataset owner/dataset-name]

This overwrites datasets/raw/fir/FIR_Details_Data.csv (the exact path
scripts/load_data.py reads from), after backing up the existing file. It does NOT run
load_data.py itself -- that script drops and rebuilds the whole database, so re-seeding
is left as a deliberate separate step:
    python scripts/load_data.py
"""
import argparse
import os
import shutil
import sys
from datetime import datetime

import pandas as pd

DEFAULT_DATASET = "vanshangaria/fir-details-karnataka-police"
TARGET_PATH = os.path.join(os.path.dirname(__file__), "..", "datasets", "raw", "fir", "FIR_Details_Data.csv")

# Columns scripts/load_data.py actually reads -- used to sanity-check whatever CSV we
# find in the downloaded dataset before we let it clobber the working pipeline input.
EXPECTED_COLUMNS = {
    "District_Name", "UnitName", "FIR_YEAR", "FIR_MONTH", "FIR_Day",
    "CrimeGroup_Name", "CrimeHead_Name", "Latitude", "Longitude",
}


def find_best_csv(download_path: str) -> str:
    candidates = []
    for root, _, files in os.walk(download_path):
        for fname in files:
            if fname.lower().endswith(".csv"):
                candidates.append(os.path.join(root, fname))

    if not candidates:
        raise FileNotFoundError(f"No CSV files found under {download_path}")

    # Prefer a file whose header matches what load_data.py expects; fall back to the
    # largest CSV if nothing matches cleanly (dataset authors rename columns sometimes).
    for path in candidates:
        try:
            header = set(pd.read_csv(path, nrows=0).columns)
        except Exception:
            continue
        if EXPECTED_COLUMNS.issubset(header):
            return path

    print("Warning: no CSV in the dataset has all expected columns; falling back to the largest CSV file. "
          "You may need to update EXPECTED_COLUMNS / load_data.py's column mapping.")
    return max(candidates, key=os.path.getsize)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Kaggle dataset slug, owner/name")
    parser.add_argument("--yes", action="store_true", help="Skip the overwrite confirmation prompt")
    args = parser.parse_args()

    try:
        import kagglehub
    except ImportError:
        print("kagglehub is not installed. Run: pip install kagglehub")
        sys.exit(1)

    print(f"Downloading dataset '{args.dataset}' via kagglehub (using your locally configured Kaggle credentials)...")
    try:
        download_path = kagglehub.dataset_download(args.dataset)
    except Exception as e:
        print(f"Download failed: {e}")
        print("Check that a Kaggle token is configured (~/.kaggle/access_token, kaggle.json, "
              "or KAGGLE_USERNAME/KAGGLE_KEY env vars) and that the token hasn't been revoked.")
        sys.exit(1)

    print(f"Downloaded to: {download_path}")
    for f in sorted(os.listdir(download_path)):
        print(f"  - {f}")

    source_csv = find_best_csv(download_path)
    print(f"Selected source file: {source_csv}")

    target_abs = os.path.abspath(TARGET_PATH)
    os.makedirs(os.path.dirname(target_abs), exist_ok=True)

    if os.path.exists(target_abs):
        backup_path = f"{target_abs}.bak-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        shutil.copy2(target_abs, backup_path)
        print(f"Backed up existing dataset to: {backup_path}")

        if not args.yes:
            resp = input(f"Overwrite {target_abs} with the freshly downloaded dataset? [y/N] ")
            if resp.strip().lower() != "y":
                print("Aborted. Existing dataset left unchanged.")
                sys.exit(0)

    shutil.copy2(source_csv, target_abs)
    row_count = sum(1 for _ in open(target_abs, encoding="utf-8", errors="ignore")) - 1
    print(f"Wrote {target_abs} ({row_count} data rows).")
    print("\nNext step (this drops and rebuilds the whole database -- run it deliberately, not from this script):")
    print("  python scripts/load_data.py")


if __name__ == "__main__":
    main()
