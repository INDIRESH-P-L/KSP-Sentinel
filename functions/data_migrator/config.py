import os

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
