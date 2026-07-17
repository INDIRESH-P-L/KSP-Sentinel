"""TOTP-based MFA: secret generation, at-rest encryption, and verification.

Secrets are encrypted with Fernet (symmetric, authenticated) before being stored in
`users.totp_secret` -- a raw DB dump or backup leak alone is not enough to clone a
user's authenticator. The Fernet key itself lives outside the database (in .env),
generated once on first startup rather than hardcoded (a hardcoded key would defeat
the purpose: anyone with the source has it).
"""
import os
import time
import pyotp
from cryptography.fernet import Fernet, InvalidToken
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from backend.app.config import settings
from backend.app.logging import logger

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")


def _persist_key_to_env(key: str) -> None:
    """Appends the generated Fernet key to .env so it survives a restart. Without
    this, every process restart would generate a new key and permanently strand
    every already-encrypted TOTP secret (locking every MFA user out for good)."""
    try:
        with open(ENV_PATH, "a", encoding="utf-8") as f:
            f.write(f"\nTOTP_ENCRYPTION_KEY={key}\n")
        logger.warning(
            "Generated a new TOTP_ENCRYPTION_KEY and appended it to .env. "
            "Back this file up -- losing this key permanently locks out every MFA-enrolled account."
        )
    except OSError as e:
        logger.error(f"Could not persist TOTP_ENCRYPTION_KEY to .env ({e}). "
                     "Set TOTP_ENCRYPTION_KEY manually or secrets will be unreadable after restart.")


def _load_fernet() -> Fernet:
    key = settings.TOTP_ENCRYPTION_KEY
    if not key:
        key = Fernet.generate_key().decode()
        settings.TOTP_ENCRYPTION_KEY = key  # so the rest of this process run is consistent
        _persist_key_to_env(key)
    return Fernet(key.encode() if isinstance(key, str) else key)


_fernet = _load_fernet()


def generate_totp_secret() -> str:
    """Returns a new base32 TOTP secret (plaintext -- caller must encrypt before storing)."""
    return pyotp.random_base32()


def encrypt_secret(plaintext_secret: str) -> str:
    return _fernet.encrypt(plaintext_secret.encode()).decode()


def decrypt_secret(encrypted_secret: str) -> str:
    try:
        return _fernet.decrypt(encrypted_secret.encode()).decode()
    except InvalidToken as e:
        # Most likely cause: TOTP_ENCRYPTION_KEY changed/was regenerated since this
        # secret was encrypted (see _persist_key_to_env above for why that matters).
        raise ValueError("Could not decrypt TOTP secret -- encryption key mismatch") from e


def provisioning_uri(plaintext_secret: str, username: str) -> str:
    """otpauth:// URI for QR-code enrollment in an authenticator app."""
    return pyotp.TOTP(plaintext_secret).provisioning_uri(name=username, issuer_name="KSP Sentinel")


def verify_totp_code(plaintext_secret: str, code: str, last_used_step: int | None = None) -> int | None:
    """Returns the matched TOTP time-step on success, or None if the code is wrong OR
    is being replayed (its step is <= last_used_step). Checks a 1-step (~30s) window
    either side of "now", which is standard TOTP clock-skew tolerance.

    The caller MUST persist the returned step as the user's new last_totp_step --
    without that, the same valid code could authenticate a second request within its
    ~30-90s validity window (e.g. two concurrent verify-otp calls, or a shoulder-surfed
    code resubmitted moments later).
    """
    totp = pyotp.TOTP(plaintext_secret)
    step_seconds = totp.interval
    now_step = int(time.time()) // step_seconds

    for offset in (-1, 0, 1):
        step = now_step + offset
        if last_used_step is not None and step <= last_used_step:
            continue  # this step's code was already spent -- refuse to match it again
        if totp.verify(code, for_time=step * step_seconds, valid_window=0):
            return step
    return None
