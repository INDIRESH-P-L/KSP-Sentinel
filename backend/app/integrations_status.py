"""Integration health reporting for GET /api/health.

Why this exists
---------------
The most damaging bugs in this platform were never crashes -- they were *silent
misconfiguration*. `app/config.py` loaded a `.env` path that did not exist, so
every API key read as empty. The AI Copilot degraded to its offline fallback and
answered questions anyway; the MFA encryption key was regenerated on every boot,
quietly making every enrolled authenticator undecryptable. Nothing surfaced
either condition. Both looked like "working" from the outside.

This module answers one question -- *is this deployment actually wired up?* --
without ever returning a secret. Every credential is reported as a boolean plus a
length, never a value, so the endpoint is safe to expose to an operator and safe
to paste into a bug report.
"""
from __future__ import annotations

import os
from pathlib import Path

from app.config import ENV_PATH, settings


def _present(value: str | None) -> dict:
    """Reports whether a credential is configured, never what it is."""
    value = (value or "").strip()
    return {"configured": bool(value), "length": len(value)}


def _database_status() -> dict:
    url = settings.DATABASE_URL or settings.SQLITE_URL
    backend = url.split("://", 1)[0] if "://" in url else "unknown"
    status: dict = {"backend": backend, "reachable": False}
    try:
        from sqlalchemy import text

        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            status["reachable"] = True
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 - a health probe must never raise
        status["error"] = f"{type(exc).__name__}"
    return status


def _redis_status() -> dict:
    """Redis is optional. Without it, rate limiting and brute-force bans fall back
    to per-process memory, which is a real (single-worker-only) limitation an
    operator should be able to see rather than infer from a startup warning."""
    status: dict = {"configured": bool(settings.REDIS_URL), "reachable": False}
    try:
        import redis  # type: ignore

        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        client.ping()
        status["reachable"] = True
    except Exception as exc:  # noqa: BLE001
        status["error"] = type(exc).__name__
        status["fallback"] = "in-memory (single process only)"
    return status


def _llm_status() -> dict:
    try:
        from integrations.llm_provider import describe

        info = describe()
    except Exception as exc:  # noqa: BLE001
        return {"provider": "unknown", "available": False, "error": type(exc).__name__}

    info["free_form_answers"] = info.get("available", False)
    if not info.get("available"):
        info["degraded_to"] = "local SQL compiler (structured questions only)"
    return info


def _ml_stack_status() -> dict:
    """Which optional ML libraries are actually importable.

    backend/requirements.txt deliberately omits several of these to keep the
    AppSail image small, and the code silently falls back when they are missing
    (TF-IDF instead of sentence-transformers, numpy dot-product instead of FAISS).
    A fallback that is invisible is a fallback nobody re-calibrates thresholds for,
    so it is reported explicitly.
    """
    optional = {
        "sentence_transformers": "semantic embeddings (else: TF-IDF fallback)",
        "faiss": "vector index (else: numpy cosine fallback)",
        "sklearn": "TF-IDF + clustering",
        "networkx": "criminal-network graph metrics",
        "statsmodels": "ARIMA forecasting",
        "prophet": "Prophet forecasting",
        "xgboost": "gradient-boosted forecasting",
    }
    out: dict = {}
    for module, purpose in optional.items():
        try:
            __import__(module)
            out[module] = {"available": True, "purpose": purpose}
        except Exception:  # noqa: BLE001 - ImportError and native-load errors alike
            out[module] = {"available": False, "purpose": purpose}
    return out


def integration_status() -> dict:
    """The full report served by GET /api/health."""
    env_exists = Path(ENV_PATH).is_file()
    return {
        "status": "online",
        "service": "KSP-Sentinel-API",
        "environment": settings.ENVIRONMENT,
        "config": {
            "env_file": str(ENV_PATH),
            "env_file_found": env_exists,
            # A deployment running on a generated-but-unpersisted SECRET_KEY drops
            # every session on restart; worth seeing at a glance.
            "secret_key": _present(settings.SECRET_KEY),
            "totp_encryption_key": _present(settings.TOTP_ENCRYPTION_KEY),
            "storage_provider": settings.STORAGE_PROVIDER,
        },
        "credentials": {
            "groq": _present(settings.GROQ_API_KEY),
            "gemini": _present(settings.GEMINI_API_KEY),
            "catalyst": _present(settings.CATALYST_AUTH_TOKEN),
        },
        "llm": _llm_status(),
        "database": _database_status(),
        "redis": _redis_status(),
        "ml_stack": _ml_stack_status(),
        "workers": {
            "pid": os.getpid(),
        },
    }
