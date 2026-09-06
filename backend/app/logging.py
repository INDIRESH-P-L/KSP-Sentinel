"""Logging setup — imported by app.main and by a dozen modules under it.

Importing this module must never raise. It used to call `os.makedirs("logs")` and
open `logs/backend.log` at import time, relative to the process CWD. Catalyst
AppSail does not guarantee a writable CWD (and backend/.catalystignore excludes
logs/, so the directory is not even shipped), so an OSError here propagated out of
`import app.main`, run.py's pre-flight check caught it, and the deployment served
the diagnostic traceback page instead of the API for *every* route.

On AppSail stdout is the log sink, so the stream handler is unconditional and the
file handler is opt-in: LOG_TO_FILE=1, or any ENVIRONMENT other than production.
A file that cannot be opened degrades to stdout-only with a warning rather than
taking the whole app down.

Reads os.getenv directly rather than app.config.settings: app.config runs .env
discovery and can persist generated secrets on import, which is far too much to
drag into a module this widely imported.
"""
import logging
import os
import sys

_TRUTHY = {"1", "true", "yes", "on"}

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _file_logging_requested() -> bool:
    """Explicit LOG_TO_FILE wins; otherwise file logs only outside production."""
    flag = os.getenv("LOG_TO_FILE")
    if flag is not None:
        return flag.strip().lower() in _TRUTHY
    return os.getenv("ENVIRONMENT", "development").strip().lower() != "production"


_handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
_file_error = None

if _file_logging_requested():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        _handlers.append(logging.FileHandler(
            os.path.join(LOG_DIR, "backend.log"), encoding="utf-8"
        ))
    except OSError as err:
        # Read-only or missing CWD -- keep booting, stdout is still captured.
        _file_error = err

# A typo in LOG_LEVEL must not be another way to kill this import.
_level = getattr(logging, LOG_LEVEL, None)
if not isinstance(_level, int):
    _level = logging.INFO

logging.basicConfig(level=_level, format=LOG_FORMAT, handlers=_handlers)

logger = logging.getLogger("ksp-sentinel")

if _file_error is not None:
    logger.warning(
        "File logging disabled: cannot write %s (%s). Logging to stdout only.",
        LOG_DIR, _file_error,
    )
