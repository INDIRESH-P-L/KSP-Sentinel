"""Re-enroll (or repair) an account's authenticator-app MFA.

Why this exists
---------------
Every console account -- including the auto-seeded `admin` -- is created with MFA
enabled and a one-time TOTP secret that is printed only once (to the API response or
the startup log). If nobody scanned that secret into an authenticator app, the login's
"authenticator code" step can never be satisfied and the account is locked out. Nothing
is emailed anywhere: the 6-digit code comes from the user's own authenticator app.

This script issues a *fresh* TOTP secret for a given username and prints it, its
otpauth:// URI, and a scannable ASCII QR code. Scan it into Google Authenticator /
Authy / Microsoft Authenticator, then log in normally -- the app will show the code.

Usage (from the backend directory so it picks up the same .env / DB):
    cd backend
    python scripts/reenroll_admin_mfa.py            # defaults to username "admin"
    python scripts/reenroll_admin_mfa.py --username sp_admin
"""
import argparse
import os
import sys

# Make `app...` importable exactly like the backend does.
# This file lives at backend/scripts/, so the backend package root is one level up.
# It previously computed `<here>/../backend`, which resolves to backend/backend --
# a directory that does not exist -- so importing `app...` failed outright. (A
# drifted duplicate of this script lives at the repository-root scripts/, where
# that original expression WAS correct; see the cleanup notes in the audit report.)
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

from app.database.session import SessionLocal, engine  # noqa: E402
from app.database.models import Base, User  # noqa: E402
from app.core import mfa  # noqa: E402


def _print_qr(otpauth_uri: str) -> None:
    """Prints a terminal-scannable QR if `qrcode` is installed; otherwise skips it.
    The otpauth:// URI printed above is enough to enroll manually either way."""
    try:
        import qrcode
    except ImportError:
        print("\n(Install `qrcode` for a scannable QR here:  pip install qrcode )")
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(otpauth_uri)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-enroll an account's authenticator MFA.")
    parser.add_argument("--username", default="admin", help="Account username (default: admin)")
    args = parser.parse_args()

    # Safe on an existing DB: only creates tables that don't exist yet.
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.username).first()
        if not user:
            print(f"ERROR: no account with username '{args.username}'. "
                  f"Start the backend once to auto-seed the default 'admin' account, "
                  f"or create the user via the admin panel first.")
            return 1

        plaintext_secret = mfa.generate_totp_secret()
        user.totp_secret = mfa.encrypt_secret(plaintext_secret)
        user.mfa_enabled = True
        # Clear anti-replay watermark so codes from the freshly enrolled secret are accepted.
        user.last_totp_step = None
        db.commit()

        otpauth_uri = mfa.provisioning_uri(plaintext_secret, user.username)

        print("\n" + "=" * 60)
        print(f"  MFA re-enrolled for '{user.username}' (role: {user.role})")
        print("=" * 60)
        print(f"\n  Manual entry secret : {plaintext_secret}")
        print(f"  otpauth URI         : {otpauth_uri}")
        print("\n  Scan this QR in Google Authenticator / Authy:")
        _print_qr(otpauth_uri)
        print("\n  Then log in and enter the 6-digit code the app shows.")
        print("  (Password is unchanged. Default seeded admin password is 'admin123'.)\n")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
