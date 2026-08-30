"""Application settings — single source of truth for configuration and secrets.

`.env` discovery
----------------
The env file lives at the REPOSITORY ROOT (next to catalyst.json), not inside
backend/. Earlier revisions hardcoded `backend/../.env`, which resolves to
`backend/.env` -- a file that does not exist -- so nothing in `.env` was ever
loaded: API keys read as empty, SECRET_KEY silently stayed on its insecure
built-in default, and TOTP_ENCRYPTION_KEY was regenerated on every boot
(permanently stranding every enrolled MFA user).

`ENV_PATH` below is resolved by walking up from this file until a `.env` is
found, and it is exported so that every module which needs to *write* a
generated secret back (see app/core/mfa.py) appends to the same file this module
reads. One path, discovered once.
"""
import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings
from dotenv import load_dotenv


def _discover_env_path() -> Path:
    """Walks up from this file looking for an existing `.env`.

    Returns the first one found. If none exists anywhere up the tree, returns the
    repository-root candidate so a first-run generated secret is written where the
    next boot will find it.
    """
    here = Path(__file__).resolve()
    # app/config.py -> app -> backend -> <repo root> -> ...
    for parent in here.parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return here.parents[2] / ".env"


ENV_PATH: Path = _discover_env_path()
load_dotenv(ENV_PATH, override=False)


def persist_secret(name: str, value: str) -> bool:
    """Appends `name=value` to the discovered .env so a generated secret survives a
    restart. Returns True on success.

    Secrets regenerated on every boot are worse than useless: a rotating SECRET_KEY
    invalidates every session on each restart, and a rotating TOTP_ENCRYPTION_KEY
    makes every already-encrypted MFA secret permanently undecryptable.
    """
    try:
        existing = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.is_file() else ""
        # Never write the same key twice -- python-dotenv keeps the FIRST occurrence,
        # so a duplicate line would be silently ignored and look like data loss.
        for line in existing.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{name}=") and stripped != f"{name}=":
                return True
        prefix = "" if (existing.endswith("\n") or not existing) else "\n"
        with ENV_PATH.open("a", encoding="utf-8") as fh:
            fh.write(f"{prefix}{name}={value}\n")
        os.environ[name] = value
        return True
    except OSError:
        return False


def _resolve_secret_key() -> str:
    """SECRET_KEY signs every JWT and keys the complainant-phone HMAC.

    A hardcoded default is a forgeable-admin-token vulnerability the moment the
    source is readable, so there is no default: an unset key is generated once and
    persisted. If persistence fails (read-only filesystem) the process falls back to
    an ephemeral per-boot key -- sessions drop on restart, which is annoying rather
    than unsafe.
    """
    existing = os.getenv("SECRET_KEY", "").strip()
    if existing:
        return existing
    generated = secrets.token_urlsafe(48)
    persist_secret("SECRET_KEY", generated)
    return generated


class Settings(BaseSettings):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    SECRET_KEY: str = _resolve_secret_key()
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ksp_sentinel.db")
    SQLITE_URL: str = os.getenv("SQLITE_URL", "sqlite:///./ksp_sentinel.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # --- AI Copilot LLM provider -------------------------------------------
    # "auto" picks whichever key is present (Groq first, then Gemini); set an
    # explicit name to pin one. Everything routes through
    # integrations/llm_provider.py -- swapping providers is config, not code.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")   # auto|groq|gemini|ollama|none

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "") or os.getenv("GROK_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    # Historical alias. The grok_* routers were written against this name while
    # POSTing to api.groq.com -- it is the same Groq credential, spelled two ways.
    # Either variable populates both so an existing .env keeps working.
    GROK_API_KEY: str = os.getenv("GROK_API_KEY", "") or os.getenv("GROQ_API_KEY", "")

    # Local inference; no key, nothing leaves the machine.
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")
    
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "local")
    CATALYST_FOLDER_ID: str = os.getenv("CATALYST_FOLDER_ID", "48446000000036421")
    CATALYST_AUTH_TOKEN: str = os.getenv("CATALYST_AUTH_TOKEN", "")
    CATALYST_ORG_ID: str = os.getenv("CATALYST_ORG_ID", "60078436924")
    CATALYST_STRATUS_BUCKET: str = os.getenv("CATALYST_STRATUS_BUCKET", "sentinel-migration-bucket")
    CATALYST_PROJECT_ID: str = os.getenv("CATALYST_PROJECT_ID", "48446000000013048")
    CATALYST_ENVIRONMENT: str = os.getenv("CATALYST_ENVIRONMENT", "Development")
    CATALYST_API_BASE: str = os.getenv("CATALYST_API_BASE", "https://api.catalyst.zoho.in")

    # Fernet key encrypting TOTP secrets at rest (backend/app/core/mfa.py). Left blank
    # here on purpose -- generated once and persisted to .env on first startup rather
    # than hardcoded, since a hardcoded key defeats the point of encrypting the column.
    TOTP_ENCRYPTION_KEY: str = os.getenv("TOTP_ENCRYPTION_KEY", "")

    # 5-minute window between password verification and OTP submission.
    PRE_AUTH_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("PRE_AUTH_TOKEN_EXPIRE_MINUTES", "5"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # ── Investigation Intelligence thresholds (NEW_FEATURES.md) ──────────────
    # All tunable without a code change so an operator can trade recall against
    # noise per deployment.
    # Feature 3: a draft FIR scoring at/above this against an existing case is
    # surfaced as a *possible* duplicate for a human to judge -- never auto-rejected.
    DUPLICATE_SIMILARITY_THRESHOLD: float = float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.85"))
    # The 0.85 above is calibrated for real sentence-transformer embeddings. When
    # those aren't installed the encoder silently falls back to TF-IDF (see
    # embeddings/sentence_transformer.py), whose cosine scores sit on a different,
    # corpus-dependent scale -- a paraphrased re-filing measured ~0.77 there where a
    # transformer would score >0.9. Applying 0.85 to TF-IDF would miss real duplicates,
    # so the fallback gets its own default and the active backend is reported in the
    # response. Re-calibrate both against your own corpus before trusting them.
    DUPLICATE_SIMILARITY_THRESHOLD_TFIDF: float = float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD_TFIDF", "0.75"))
    DUPLICATE_SEARCH_TOP_K: int = int(os.getenv("DUPLICATE_SEARCH_TOP_K", "25"))
    # Corroborating (not gating) proximity signals reported alongside each match.
    DUPLICATE_NEARBY_KM: float = float(os.getenv("DUPLICATE_NEARBY_KM", "2.0"))
    DUPLICATE_NEARBY_DAYS: int = int(os.getenv("DUPLICATE_NEARBY_DAYS", "7"))

    # Feature 1: cross-district modus-operandi pattern matching.
    MO_MATCH_THRESHOLD: float = float(os.getenv("MO_MATCH_THRESHOLD", "0.75"))
    # Per-field weights for the agreement score. entry_method and weapon carry the most
    # signal (a forced rear-door entry with an iron rod is a signature); time_of_day is
    # weakest -- only four possible values, so agreement there is largely chance.
    MO_WEIGHT_ENTRY_METHOD: float = float(os.getenv("MO_WEIGHT_ENTRY_METHOD", "0.30"))
    MO_WEIGHT_WEAPON: float = float(os.getenv("MO_WEIGHT_WEAPON", "0.30"))
    MO_WEIGHT_TARGET_TYPE: float = float(os.getenv("MO_WEIGHT_TARGET_TYPE", "0.25"))
    MO_WEIGHT_TIME_PATTERN: float = float(os.getenv("MO_WEIGHT_TIME_PATTERN", "0.15"))
    # A pair must have at least this many *mutually populated* MO fields before a score
    # is trusted. Without it, two cases whose only shared populated field is
    # time_of_day="night" would score a perfect 1.0 on a single coincidence.
    MO_MATCH_MIN_COMPARABLE_FIELDS: int = int(os.getenv("MO_MATCH_MIN_COMPARABLE_FIELDS", "3"))
    # Safety cap on the O(n^2) pair scan for an on-demand run.
    MO_MATCH_MAX_FIRS: int = int(os.getenv("MO_MATCH_MAX_FIRS", "5000"))

    # Feature 2: IPC/BNS section suggestion (retrieval over reference descriptions).
    SECTION_SUGGESTION_TOP_K: int = int(os.getenv("SECTION_SUGGESTION_TOP_K", "3"))
    SECTION_SUGGESTION_MIN_CONFIDENCE: float = float(os.getenv("SECTION_SUGGESTION_MIN_CONFIDENCE", "0.05"))
    # Relative floor, as a fraction of the top hit's score. An absolute floor alone
    # can't separate signal from noise here because the absolute scale shifts with the
    # embedding backend and corpus -- but the *gap* to the best match is meaningful on
    # any scale. Without this, a chain-snatching complaint returns "causing death by
    # negligence" as its third suggestion at 0.087 purely to fill the top-3 slot, which
    # is exactly the kind of output that destroys an officer's trust in the tool.
    SECTION_SUGGESTION_RELATIVE_FLOOR: float = float(os.getenv("SECTION_SUGGESTION_RELATIVE_FLOOR", "0.20"))

    # ── Feature 3: case timeline nudges ─────────────────────────────────────
    # A case with no investigation activity for this long is surfaced to its
    # supervisor. Counted from investigations.last_updated, or from the FIR's own
    # date_reported when no investigation row exists at all (never assigned is a
    # staler state than assigned-but-quiet, not a reason to stay silent).
    NUDGE_STALENESS_DAYS: int = int(os.getenv("NUDGE_STALENESS_DAYS", "14"))
    # How far ahead a deadline is flagged.
    NUDGE_DEADLINE_WINDOW_DAYS: int = int(os.getenv("NUDGE_DEADLINE_WINDOW_DAYS", "7"))
    # Statutory chargesheet window. The schema stores when a chargesheet WAS filed,
    # never when it is due, so the deadline is derived as date_reported + this many
    # days. 60 mirrors CrPC 167(2)(a)(ii) / BNSS 187 for offences punishable with
    # under ten years; raise it to 90 for the graver bracket if a deployment needs it.
    NUDGE_CHARGESHEET_DEADLINE_DAYS: int = int(os.getenv("NUDGE_CHARGESHEET_DEADLINE_DAYS", "60"))
    # Cap on how many FIRs one scan walks.
    NUDGE_MAX_CASES: int = int(os.getenv("NUDGE_MAX_CASES", "20000"))

    # ── Feature 2: officer-safety location risk ─────────────────────────────
    SAFETY_DEFAULT_RADIUS_M: int = int(os.getenv("SAFETY_DEFAULT_RADIUS_M", "300"))
    SAFETY_MAX_RADIUS_M: int = int(os.getenv("SAFETY_MAX_RADIUS_M", "5000"))
    # Per-incident-type danger weights. An assault on an officer at this spot says more
    # about approaching it than a record of verbal resistance does.
    SAFETY_WEIGHT_ASSAULT: float = float(os.getenv("SAFETY_WEIGHT_ASSAULT", "2.0"))
    SAFETY_WEIGHT_WEAPON: float = float(os.getenv("SAFETY_WEIGHT_WEAPON", "1.5"))
    SAFETY_WEIGHT_RESISTANCE: float = float(os.getenv("SAFETY_WEIGHT_RESISTANCE", "1.0"))
    # severity is 1-5; divided by this so a "typical" 3 contributes a factor of 1.0.
    SAFETY_SEVERITY_PIVOT: float = float(os.getenv("SAFETY_SEVERITY_PIVOT", "3.0"))
    # Recency decay bands in months. A confrontation five years ago is a much weaker
    # predictor of what an officer walks into today than one last month, but it is not
    # nothing -- hence a floor rather than a hard cutoff.
    SAFETY_RECENCY_RECENT_MONTHS: int = int(os.getenv("SAFETY_RECENCY_RECENT_MONTHS", "6"))
    SAFETY_RECENCY_MID_MONTHS: int = int(os.getenv("SAFETY_RECENCY_MID_MONTHS", "12"))
    SAFETY_RECENCY_OLD_MONTHS: int = int(os.getenv("SAFETY_RECENCY_OLD_MONTHS", "24"))
    SAFETY_RECENCY_FACTOR_MID: float = float(os.getenv("SAFETY_RECENCY_FACTOR_MID", "0.7"))
    SAFETY_RECENCY_FACTOR_OLD: float = float(os.getenv("SAFETY_RECENCY_FACTOR_OLD", "0.4"))
    SAFETY_RECENCY_FACTOR_ANCIENT: float = float(os.getenv("SAFETY_RECENCY_FACTOR_ANCIENT", "0.2"))
    # Band cut-offs. Tuned so ONE recent, maximum-severity assault on an officer alone
    # reaches "high" -- under-calling that to avoid alarm would be the wrong failure.
    SAFETY_BAND_LOW: float = float(os.getenv("SAFETY_BAND_LOW", "1.5"))
    SAFETY_BAND_MEDIUM: float = float(os.getenv("SAFETY_BAND_MEDIUM", "3.0"))

    # ── Feature 5: public FIR status check + messaging ──────────────────────
    # Only "stub" is implemented. Selecting any other value logs a warning and every
    # send returns simulated=True -- see integrations/messaging_bot.py.
    MESSAGING_PROVIDER: str = os.getenv("MESSAGING_PROVIDER", "stub")
    # Tighter than the district-safety limit: this route takes user input and is the
    # one place an attacker could try to enumerate FIR numbers.
    FIR_STATUS_RATE_LIMIT: str = os.getenv("FIR_STATUS_RATE_LIMIT", "10/minute")

    class Config:
        env_file = str(ENV_PATH)
        extra = "ignore"

settings = Settings()
