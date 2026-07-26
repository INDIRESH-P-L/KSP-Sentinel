import os
import sys

# Add backend directory to path to use existing auth logic
backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, backend_path)

from app.config import settings
from app.filestore_crime_data import _get_catalyst_app
from app.logging import logger

def upload_missing_datasets():
    print("Initializing SDK...")
    app = _get_catalyst_app()
    if not app:
        print("Failed to initialize Catalyst SDK.")
        return
        
    bucket_name = getattr(settings, "CATALYST_STRATUS_BUCKET", "sentinel-migration-bucket")
    bucket = app.stratus().bucket(bucket_name)
    print(f"Connected to bucket: {bucket_name}")
    
    # Folders to check for datasets
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dirs = [
        os.path.join(base_dir, "datasets", "raw"),
        base_dir
    ]
    
    csv_files = {}
    for d in target_dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith(".csv"):
                    if f not in csv_files:
                        csv_files[f] = os.path.join(d, f)
                        
    for filename, filepath in csv_files.items():
        print(f"Checking {filename}...")
        
        # Check if exists
        exists = False
        try:
            # We just need to check metadata, but get_object is fine for checking existence
            bucket.get_object(filename)
            exists = True
        except Exception:
            try:
                bucket.get_object(f"archive/{filename}")
                exists = True
            except Exception:
                exists = False
                
        if exists:
            print(f"  -> '{filename}' already exists in Stratus. Skipping.")
        else:
            print(f"  -> '{filename}' not found in Stratus. Uploading...")
            try:
                with open(filepath, "rb") as file_obj:
                    # Upload
                    content = file_obj.read()
                    
                    # Direct HTTP PUT as SDK might have response parsing issues
                    import requests
                    from zcatalyst_sdk._thread_util import ZCThreadUtil
                    from zcatalyst_sdk import _constants as APIConstants
                    thread = ZCThreadUtil()
                    token = thread.get_value(APIConstants.ADMIN_CRED) or getattr(settings, "CATALYST_AUTH_TOKEN", "")
                    
                    if not token:
                        print(f"  -> Failed to upload '{filename}': No auth token found for HTTP fallback")
                        continue
                        
                    url = f"https://{bucket_name}-development.zohostratus.in/{filename}"
                    headers = {
                        'Authorization': f'Zoho-oauthtoken {token}',
                        'Catalyst-org': '60078436924',
                        'Environment': 'Development',
                        'Content-Type': 'text/csv'
                    }
                    r = requests.put(url, headers=headers, data=content)
                    if r.status_code in [200, 201, 202, 204]:
                        print(f"  -> Successfully uploaded '{filename}'. Status: {r.status_code}")
                    else:
                        print(f"  -> Failed to upload '{filename}'. HTTP {r.status_code}: {r.text}")
            except Exception as e:
                print(f"  -> Failed to upload '{filename}': {e}")

if __name__ == "__main__":
    upload_missing_datasets()
