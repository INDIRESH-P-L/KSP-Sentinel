import os
import zcatalyst_sdk

# Hardcode CATALYST_AUTH to avoid Windows spawning stripping quotes
os.environ["CATALYST_AUTH"] = '{"client_id": "1000.D5IIHDXSPN2MII26AD0V61I6RMVSNM", "client_secret": "02ee875ecfc50573e5cc8d62916ad3077be20d0f42", "refresh_token": "1000.b33eae44d0bddb9fdc914bdfc96871b9.6f4a777c0e20ee1756cbe7cbee3cefe0"}'

# Initialize Catalyst SDK
try:
    catalyst_app = zcatalyst_sdk.initialize()
except Exception as e:
    pass

# Stratus Configuration
BUCKET_NAME = os.getenv("CATALYST_STRATUS_BUCKET", "sentinel-migration-bucket")
TEMP_DIR = os.path.join(os.path.dirname(__file__), "tmp")

# Data Processing
CHUNK_SIZE = int(os.getenv("MIGRATION_CHUNK_SIZE", 5000))

# Resilience
MAX_RETRIES = int(os.getenv("MIGRATION_MAX_RETRIES", 3))
RETRY_DELAY_SECONDS = int(os.getenv("MIGRATION_RETRY_DELAY", 5))

# State Management
STATE_FILE = os.path.join(os.path.dirname(__file__), "migration_state.json")

# Create temp dir if it doesn't exist
os.makedirs(TEMP_DIR, exist_ok=True)
