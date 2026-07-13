import logging
import os

# Create logs directory if not exists
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/backend.log", encoding="utf-8")
    ]
)

logger = logging.getLogger("ksp-sentinel")
