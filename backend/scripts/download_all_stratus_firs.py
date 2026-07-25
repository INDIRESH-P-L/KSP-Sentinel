import os
import sys
import io
import time
import subprocess
import requests
import pandas as pd
from datetime import datetime

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def log_info(msg):
    print(f"\033[94m[INFO]\033[0m {msg}")

def log_success(msg):
    print(f"\033[92m[SUCCESS]\033[0m {msg}")

def log_warn(msg):
    print(f"\033[93m[WARN]\033[0m {msg}")

def log_error(msg):
    print(f"\033[91m[ERROR]\033[0m {msg}", file=sys.stderr)

def get_cli_access_token():
    log_info("Decrypting Catalyst CLI OAuth token...")
    node_cmd = (
        "node -e \""
        "const Credential = require('/usr/lib/node_modules/zcatalyst-cli/lib/authentication/credential.js').default; "
        "const fs = require('fs'); "
        "const config = JSON.parse(fs.readFileSync('/home/keshav/.config/zcatalyst-cli-nodejs/zcatalyst-cli-v1.json', 'utf8')); "
        "console.log(Credential.decrypt(config.in.credential).access_token);"
        "\""
    )
    res = subprocess.run(node_cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Failed to decrypt Catalyst CLI credentials: {res.stderr}")
    return res.stdout.strip()

def download_file_from_stratus(key, token, target_path, max_retries=3):
    url = f"https://sentinel-migration-bucket-development.zohostratus.in/{key}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Catalyst-org": "60078436924",
        "Environment": "Development"
    }
    
    # Check if existing local file is already fully downloaded
    if os.path.exists(target_path):
        try:
            head_r = requests.head(url, headers=headers, timeout=10)
            if head_r.status_code == 200:
                expected_len = int(head_r.headers.get("content-length", 0))
                local_len = os.path.getsize(target_path)
                if expected_len > 0 and local_len == expected_len:
                    log_success(f"File '{key}' already exists locally and matches size ({local_len:,} bytes). Skipping.")
                    return True
        except Exception:
            pass

    log_info(f"Downloading '{key}' from Stratus bucket 'sentinel-migration-bucket'...")

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, headers=headers, stream=True, timeout=60)
            if r.status_code != 200:
                log_error(f"Attempt {attempt}/{max_retries}: Failed to download '{key}' (Status {r.status_code})")
                time.sleep(2)
                continue

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            tmp_path = target_path + ".tmp"
            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            
            os.replace(tmp_path, target_path)
            file_size = os.path.getsize(target_path)
            log_success(f"Downloaded '{key}' successfully ({file_size:,} bytes) -> '{target_path}'.")
            return True
        except Exception as e:
            log_warn(f"Attempt {attempt}/{max_retries} for '{key}' failed with network error: {e}")
            if os.path.exists(target_path + ".tmp"):
                try: os.remove(target_path + ".tmp")
                except Exception: pass
            time.sleep(attempt * 2)

    log_error(f"All {max_retries} download attempts failed for '{key}'.")
    return False

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dir = os.path.join(repo_root, "datasets", "raw")
    fir_dir = os.path.join(raw_dir, "fir")
    os.makedirs(fir_dir, exist_ok=True)
    
    token = get_cli_access_token()
    downloaded = []
    
    # 1. Download Metadata Datasets first
    metadata_files = [
        "districts.csv",
        "police_stations.csv",
        "crime_categories.csv",
        "crime_subcategories.csv",
        "officers.csv"
    ]
    for meta_file in metadata_files:
        target_path = os.path.join(raw_dir, meta_file)
        if download_file_from_stratus(meta_file, token, target_path):
            downloaded.append(target_path)

    # 2. Download FIR archives
    for n in range(1, 10):
        name = f"FIR{n}.csv"
        key = f"archive/{name}"
        target_path = os.path.join(fir_dir, name)
        if download_file_from_stratus(key, token, target_path):
            downloaded.append(target_path)

    log_success(f"Downloaded/Verified {len(downloaded)} total datasets from Zoho Catalyst Stratus bucket!")

if __name__ == "__main__":
    main()
