import os
import sys
import csv
import json
import requests
import subprocess
from datetime import datetime

# Add parent dir to path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def log_info(msg):
    print(f"\033[94m[INFO]\033[0m {msg}")

def log_success(msg):
    print(f"\033[92m[SUCCESS]\033[0m {msg}")

def log_warn(msg):
    print(f"\033[93m[WARN]\033[0m {msg}")

def log_error(msg):
    print(f"\033[91m[ERROR]\033[0m {msg}", file=sys.stderr)

# Configuration
PROJECT_ID = "48446000000013048"
FOLDER_ID = "48446000000036421"
ORG_ID = "60078436924"
BASE_URL = "https://api.catalyst.zoho.in"

FIR_DIR = "datasets/raw/fir"
REVIEW_DIR = "datasets/raw/crime_review"

def get_access_token():
    log_info("Retrieving decrypted access token from Catalyst CLI configuration...")
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

def list_files(access_token):
    log_info("Fetching list of files from Catalyst File Store folder...")
    url = f"{BASE_URL}/baas/v1/project/{PROJECT_ID}/folder/{FOLDER_ID}/file"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Catalyst-org": ORG_ID,
        "Environment": "Development"
    }
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to list files: Status {r.status_code}, Response: {r.text}")
    return r.json().get("data", [])

def download_file(access_token, file_id, file_name, dest_path):
    url = f"{BASE_URL}/baas/v1/project/{PROJECT_ID}/folder/{FOLDER_ID}/file/{file_id}/download"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Catalyst-org": ORG_ID,
        "Environment": "Development"
    }
    r = requests.get(url, headers=headers, stream=True)
    if r.status_code != 200:
        log_error(f"Failed to download {file_name}: Status {r.status_code}")
        return False
        
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return True

def merge_fir_files(downloaded_fir_files, backup_path):
    log_info("Merging all FIR CSV files into a unified FIR_Details_Data.csv...")
    target_path = os.path.join(FIR_DIR, "FIR_Details_Data.csv")
    
    # Headers should be determined from the first file read
    headers = None
    all_rows = []
    
    # If backup exists, start with it
    if backup_path and os.path.exists(backup_path):
        log_info(f"Loading existing backup data from {os.path.basename(backup_path)}...")
        with open(backup_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            all_rows.extend(list(reader))
            
    # Load all downloaded FIR parts
    for filepath in downloaded_fir_files:
        log_info(f"Processing downloaded file: {os.path.basename(filepath)}...")
        with open(filepath, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.reader(f)
            file_headers = next(reader, None)
            if not headers:
                headers = file_headers
            all_rows.extend(list(reader))
            
    if not headers:
        log_error("No headers found in any of the FIR CSV files. Merge aborted.")
        return
        
    log_info(f"Writing {len(all_rows)} total rows to {target_path}...")
    with open(target_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(all_rows)
        
    log_success(f"Unified FIR_Details_Data.csv successfully updated with {len(all_rows)} rows!")

def main():
    try:
        access_token = get_access_token()
        files = list_files(access_token)
        log_info(f"Found {len(files)} files in File Store folder.")
        
        # Ensure directories exist
        os.makedirs(FIR_DIR, exist_ok=True)
        os.makedirs(REVIEW_DIR, exist_ok=True)
        
        # Backup existing FIR_Details_Data.csv if it exists
        original_fir_path = os.path.join(FIR_DIR, "FIR_Details_Data.csv")
        backup_path = None
        if os.path.exists(original_fir_path):
            backup_path = f"{original_fir_path}.bak-before-merge-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            os.rename(original_fir_path, backup_path)
            log_info(f"Backed up existing FIR data to: {os.path.basename(backup_path)}")
            
        downloaded_firs = []
        downloaded_reviews_count = 0
        
        # We will deduplicate review files by name
        downloaded_review_names = set()
        
        for f in files:
            file_name = f["file_name"]
            file_id = f["id"]
            file_size = f["file_size"]
            
            # Identify FIR files
            if file_name.upper().startswith("FIR") and file_name.lower().endswith(".csv"):
                dest_path = os.path.join(FIR_DIR, file_name)
                log_info(f"Downloading {file_name} ({file_size} bytes)...")
                if download_file(access_token, file_id, file_name, dest_path):
                    downloaded_firs.append(dest_path)
                    
            # Identify Crime Review files
            elif ("CRIME_REVIEW" in file_name.upper() or "CRIME_REVEIW" in file_name.upper()) and file_name.lower().endswith(".csv"):
                # Avoid downloading duplicate names
                if file_name in downloaded_review_names:
                    continue
                dest_path = os.path.join(REVIEW_DIR, file_name)
                log_info(f"Downloading {file_name} ({file_size} bytes)...")
                if download_file(access_token, file_id, file_name, dest_path):
                    downloaded_review_names.add(file_name)
                    downloaded_reviews_count += 1
                    
        log_success(f"Downloaded {len(downloaded_firs)} FIR parts and {downloaded_reviews_count} Crime Review files.")
        
        # Merge the FIR files
        merge_fir_files(downloaded_firs, backup_path)
        
        # Clean up temporary downloaded parts to keep workspace clean
        for filepath in downloaded_firs:
            if os.path.exists(filepath):
                os.remove(filepath)
                
        log_success("All files downloaded and processed successfully!")
        
    except Exception as e:
        log_error(f"Execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
