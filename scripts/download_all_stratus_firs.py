import os
import sys
import io
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

def download_fir_from_stratus(name, token, target_path):
    url = f"https://sentinel-migration-bucket-development.zohostratus.in/archive/{name}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Catalyst-org": "60078436924",
        "Environment": "Development"
    }
    log_info(f"Downloading {name} from Stratus bucket 'sentinel-migration-bucket/archive/'...")
    r = requests.get(url, headers=headers, stream=True)
    if r.status_code != 200:
        log_error(f"Failed to download {name} from Stratus: Status {r.status_code}")
        return False

    with open(target_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
    file_size = os.path.getsize(target_path)
    log_success(f"Downloaded {name} successfully ({file_size:,} bytes).")
    return True

def main():
    fir_dir = os.path.join("datasets", "raw", "fir")
    os.makedirs(fir_dir, exist_ok=True)
    
    token = get_cli_access_token()
    downloaded_files = []
    
    for n in range(1, 10):
        name = f"FIR{n}.csv"
        target_path = os.path.join(fir_dir, name)
        if download_fir_from_stratus(name, token, target_path):
            downloaded_files.append(target_path)

    log_success(f"Downloaded {len(downloaded_files)}/9 FIR files from Catalyst Stratus bucket!")

if __name__ == "__main__":
    main()
