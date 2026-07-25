import os
import sys
import requests

# Add backend directory to path
backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, backend_path)

from app.config import settings

def test_catalyst_connectivity():
    print("=" * 60)
    print("ZOHO CATALYST DEEP CONNECTIVITY DIAGNOSTIC")
    print("=" * 60)
    
    project_id = getattr(settings, "CATALYST_PROJECT_ID", "48446000000013048")
    org_id = getattr(settings, "CATALYST_ORG_ID", "60078436924")
    token = getattr(settings, "CATALYST_AUTH_TOKEN", "")
    stratus_bucket = getattr(settings, "CATALYST_STRATUS_BUCKET", "sentinel-migration-bucket")
    domain = getattr(settings, "CATALYST_PROJECT_DOMAIN", "https://ksp-sentinel-60078436924.development.catalystserverless.in")
    
    print(f"[-] Project ID    : {project_id}")
    print(f"[-] Org ID        : {org_id}")
    print(f"[-] Stratus Bucket: {stratus_bucket}")
    print(f"[-] Project Domain: {domain}")
    print(f"[-] Auth Token    : {'Present (' + token[:10] + '...)' if token else 'Not set (using CLI credentials)'}")
    print("-" * 60)

    # 1. Ping Catalyst Domain Endpoint
    print("[1] Testing Catalyst Domain Health Endpoint...")
    try:
        res = requests.get(domain, timeout=5)
        print(f"   [Domain Status]: HTTP {res.status_code} ({res.reason})")
    except Exception as e:
        print(f"   [Domain Connection Note]: {e}")

    # 2. Test Stratus Storage Endpoint
    print("\n[2] Testing Zoho Stratus Storage Endpoint...")
    stratus_url = f"https://sentinel-migration-bucket-development.zohostratus.in/archive/FIR1.csv"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}" if token else "",
        "Catalyst-org": org_id,
        "Environment": "Development"
    }
    try:
        res = requests.head(stratus_url, headers=headers, timeout=5)
        print(f"   [Stratus Bucket URL]: {stratus_url}")
        print(f"   [Stratus Status]    : HTTP {res.status_code}")
        print(f"   [Content-Type]      : {res.headers.get('Content-Type', 'N/A')}")
        print(f"   [Content-Length]    : {res.headers.get('Content-Length', 'N/A')} bytes")
    except Exception as e:
        print(f"   [Stratus Error]     : {e}")

    # 3. Test Zoho Catalyst SDK / AppSail Runtime
    print("\n[3] Testing Zoho Catalyst Python SDK Handshake...")
    try:
        from app.filestore_crime_data import _get_catalyst_app
        app = _get_catalyst_app()
        print("   [SDK Handshake]: SUCCESS - zcatalyst_sdk initialized cleanly!")
    except Exception as e:
        print(f"   [SDK Handshake]: Note - Running in standalone local server mode (SDK fallback active: {e})")

    print("\n" + "=" * 60)
    print("CONNECTIVITY DIAGNOSTIC COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_catalyst_connectivity()
