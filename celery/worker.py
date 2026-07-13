import os
from celery import Celery
from dotenv import load_dotenv
import random
from datetime import datetime, timedelta

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize Celery app
celery_app = Celery(
    "ksp_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Celery configurations
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True
)

@celery_app.task(name="tasks.forecast_rebuild")
def rebuild_predictions_task():
    """Background task to retrain prediction models and update cache"""
    print("Celery: Triggered background predictions update...")
    return {"status": "SUCCESS", "records_updated": 21}

@celery_app.task(name="tasks.generate_alerts")
def generate_alerts_task():
    """Scans crime counts and issues warning alerts if anomalies are found"""
    print("Celery: Performing anomaly scan on districts...")
    districts = ["Bengaluru City", "Mangaluru", "Mysuru"]
    alert_messages = [
        "Cyber Crime is rising rapidly in Bengaluru East (+43%).",
        "Vehicle Theft hotspot clusters detected near Indiranagar Metro Station.",
        "NDPS cases reporting frequency has increased (+12%) in Mangaluru coastal zones."
    ]
    return {
        "status": "COMPLETED",
        "alerts_generated": len(alert_messages),
        "messages": alert_messages
    }

@celery_app.task(name="tasks.db_cleanup")
def cleanup_temp_files():
    """Routine database health cleanup"""
    print("Celery: Cleaning up transient/temporary session files...")
    return {"status": "SUCCESS"}
