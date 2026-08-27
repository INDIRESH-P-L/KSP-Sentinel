import os
import sys
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
import random
from datetime import datetime, timedelta

load_dotenv()

# The backend package lives one level up; add it so scheduled tasks can reuse the
# same service functions the API calls rather than reimplementing them.
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _anchor_sqlite_to_backend():
    """Pin a relative SQLite path to backend/ instead of the worker's own cwd.

    app/database/session.py defaults to "sqlite:///./ksp_sentinel.db" -- a path
    relative to wherever the process happens to start. The API starts in backend/,
    but a Celery worker typically does not, and SQLite silently CREATES a missing
    file rather than erroring. The scheduled job would then run happily against a
    brand-new empty database and report "0 matches" forever.

    Resolved here, before anything imports the session module, and only when the
    configured URL is actually relative -- an explicit absolute path or a Postgres
    DSN is left untouched.
    """
    prefix = "sqlite:///"
    for var in ("SQLITE_URL", "DATABASE_URL"):
        url = os.getenv(var)
        if url is None:
            url = "sqlite:///./ksp_sentinel.db"      # mirrors the session.py default
        if not url.startswith(prefix):
            continue                                  # Postgres or similar; leave alone
        path = url[len(prefix):]
        if os.path.isabs(path) or (len(path) > 1 and path[1] == ":"):
            continue                                  # already absolute (POSIX or Windows)
        resolved = os.path.normpath(os.path.join(BACKEND_DIR, path.lstrip("./\\")))
        os.environ[var] = prefix + resolved.replace("\\", "/")


_anchor_sqlite_to_backend()


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)

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

# ---------------------------------------------------------------------------
# Beat schedule (NEW_FEATURES.md, Feature 1)
#
# Only the MO-matching job is scheduled here. The three tasks below it predate
# this and are left unscheduled on purpose -- turning on someone else's alerting
# and cleanup jobs is not a side effect this change should have.
#
# Cadence is nightly and off-peak because the job is O(n^2) over FIRs carrying MO
# tags (capped by MO_MATCH_MAX_FIRS) and rewrites the whole mo_pattern_matches
# table on each run. The timezone above is already Asia/Kolkata, so these are IST.
# ---------------------------------------------------------------------------
MO_MATCH_SCHEDULE_ENABLED = os.getenv("MO_MATCH_SCHEDULE_ENABLED", "1").lower() not in ("0", "false", "no")
MO_MATCH_SCHEDULE_HOUR = _env_int("MO_MATCH_SCHEDULE_HOUR", 2)
MO_MATCH_SCHEDULE_MINUTE = _env_int("MO_MATCH_SCHEDULE_MINUTE", 30)

if MO_MATCH_SCHEDULE_ENABLED:
    celery_app.conf.beat_schedule = {
        "cross-district-mo-matching": {
            "task": "tasks.mo_matching",
            "schedule": crontab(hour=MO_MATCH_SCHEDULE_HOUR, minute=MO_MATCH_SCHEDULE_MINUTE),
            "options": {"expires": 60 * 60},  # drop a run rather than stack it behind a slow one
        },
    }

NUDGE_SCAN_ENABLED = os.getenv("NUDGE_SCAN_ENABLED", "1").lower() not in ("0", "false", "no")
NUDGE_SCAN_HOUR = _env_int("NUDGE_SCAN_HOUR", 6)
NUDGE_SCAN_MINUTE = _env_int("NUDGE_SCAN_MINUTE", 0)

if NUDGE_SCAN_ENABLED:
    # 06:00 IST: early enough that the queue is ready before the working day, and well
    # clear of the 02:30 MO job so the two never contend for the same DB.
    celery_app.conf.beat_schedule.setdefault("daily-case-nudge-scan", {
        "task": "tasks.nudge_scan",
        "schedule": crontab(hour=NUDGE_SCAN_HOUR, minute=NUDGE_SCAN_MINUTE),
        "options": {"expires": 60 * 60},
    })


@celery_app.task(name="tasks.nudge_scan", bind=True)
def nudge_scan_task(self, staleness_days=None, window_days=None):
    """Daily case-timeline nudge scan.

    Calls the same run_nudge_scan() as POST /api/nudges/scan, so the scheduled and
    manual paths cannot drift. Backend imports are deferred for the same reason as the
    MO task: a missing backend should fail this task, not stop the worker booting.
    """
    try:
        from app.database.session import SessionLocal
        from app.services.nudges import run_nudge_scan
    except Exception as exc:
        return {"status": "FAILED", "stage": "import", "error": f"{type(exc).__name__}: {exc}"}

    db = SessionLocal()
    try:
        summary = run_nudge_scan(db, staleness_days=staleness_days, window_days=window_days)
        print(f"Celery: nudge scan complete -- {summary['created']} raised, "
              f"{summary['auto_resolved']} auto-resolved across {summary['cases_scanned']} case(s).")
        return {"status": "SUCCESS", **summary}
    except Exception as exc:
        db.rollback()
        print(f"Celery: nudge scan FAILED -- {type(exc).__name__}: {exc}")
        return {"status": "FAILED", "stage": "run", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        db.close()


@celery_app.task(name="tasks.mo_matching", bind=True)
def mo_matching_task(self, threshold=None, replace=True):
    """Rebuilds cross-district modus-operandi matches (mo_pattern_matches).

    Calls the exact same service function as POST /api/intelligence/mo-matches/run,
    so the scheduled and on-demand paths can never drift apart.

    The backend imports are deliberately deferred to call time: a worker whose
    backend dependencies are missing should fail this one task with a clear error,
    not refuse to boot and take the other tasks down with it.
    """
    try:
        from app.database.session import SessionLocal
        from app.services.mo_matching import run_mo_matching
    except Exception as exc:
        return {"status": "FAILED", "stage": "import",
                "error": f"{type(exc).__name__}: {exc}",
                "hint": "Worker cannot import the backend package; check BACKEND_DIR on sys.path."}

    db = SessionLocal()
    try:
        summary = run_mo_matching(db, threshold=threshold, replace=replace)
        print(f"Celery: MO matching complete -- {summary['matches_detected']} match(es) "
              f"from {summary['cross_district_pairs_examined']} cross-district pairs.")
        return {"status": "SUCCESS", **summary}
    except Exception as exc:
        db.rollback()
        print(f"Celery: MO matching FAILED -- {type(exc).__name__}: {exc}")
        return {"status": "FAILED", "stage": "run", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        db.close()

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
