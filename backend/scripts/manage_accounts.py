"""Console account administration — list, create, reset password, re-issue MFA.

Why this exists
---------------
Authentication used to have four ways around it: an anonymous request was handed a
working Investigator identity, the literal token "demo_token" was accepted as a
Superintendent, the OTP codes "000000" and "bypass" completed MFA for any account,
and any unknown username with the password "password"/"ksp123"/"admin" was issued a
real session. All four are gone.

That closes the holes, but it also means there is now exactly one way in: a real
account with a real password and (where enabled) a real authenticator. This tool is
that path. It is deliberately a local CLI -- it needs filesystem access to the
database and never listens on a socket, so it cannot itself become a way in.

Usage (run from the backend/ directory so it picks up the same .env and DB):

    python scripts/manage_accounts.py list
    python scripts/manage_accounts.py reset-password --username admin
    python scripts/manage_accounts.py reset-password --username admin --password 'S3cret!'
    python scripts/manage_accounts.py create --username sp_north --role Superintendent
    python scripts/manage_accounts.py create --username a1 --role Analyst --district-id 3 --no-mfa
    python scripts/manage_accounts.py disable --username old_officer

Roles: Admin | Superintendent | Investigator | Analyst
  Admin manages accounts and is deliberately barred from crime data
  (separation of duties -- see app/core/security.py).
"""
import argparse
import os
import secrets
import sys

# This file lives at backend/scripts/, so the backend package root is one level up.
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

from app.core import mfa  # noqa: E402
from app.database.models import Base, User  # noqa: E402
from app.database.session import SessionLocal, engine  # noqa: E402
from app.dependencies import hash_password  # noqa: E402

ROLES = ("Admin", "Superintendent", "Investigator", "Analyst")


def _banner(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def _print_enrollment(username: str, plaintext_secret: str) -> None:
    """Prints the TOTP secret and its otpauth URI.

    Shown exactly once, here, on an operator's own terminal. It is deliberately NOT
    returned by the login API: that response used to include the decrypted secret,
    which meant anyone who learned a password could read the second factor straight
    out of it.
    """
    uri = mfa.provisioning_uri(plaintext_secret, username)
    print(f"  TOTP secret : {plaintext_secret}")
    print(f"  otpauth URI : {uri}")
    try:
        import qrcode  # type: ignore

        qr = qrcode.QRCode(border=1)
        qr.add_data(uri)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except ImportError:
        print("  (pip install qrcode for a scannable QR code here)")


def cmd_list(args, db) -> int:
    users = db.query(User).order_by(User.id).all()
    if not users:
        print("No accounts exist. Create one with: manage_accounts.py create --username <name> --role <role>")
        return 0
    _banner("CONSOLE ACCOUNTS")
    print(f"  {'id':<4} {'username':<20} {'role':<16} {'active':<7} {'mfa':<5} district")
    print("  " + "-" * 68)
    for u in users:
        print(f"  {u.id:<4} {u.username:<20} {u.role:<16} "
              f"{str(bool(u.is_active)):<7} {str(bool(u.mfa_enabled)):<5} {u.district_id}")
    print()
    return 0


def cmd_reset_password(args, db) -> int:
    user = db.query(User).filter(User.username == args.username).first()
    if not user:
        print(f"ERROR: no account named {args.username!r}. Run `list` to see what exists.")
        return 1

    password = args.password or secrets.token_urlsafe(18)
    user.password_hash = hash_password(password)
    user.is_active = True
    db.commit()

    _banner(f"PASSWORD RESET — {user.username}")
    print(f"  username : {user.username}")
    print(f"  password : {password}")
    print(f"  role     : {user.role}")
    if user.mfa_enabled:
        print("\n  This account also requires an authenticator code. If you do not have")
        print("  one enrolled, re-issue it with:")
        print(f"      python scripts/manage_accounts.py reset-mfa --username {user.username}")
    print()
    return 0


def cmd_reset_mfa(args, db) -> int:
    user = db.query(User).filter(User.username == args.username).first()
    if not user:
        print(f"ERROR: no account named {args.username!r}.")
        return 1

    if args.disable:
        user.mfa_enabled = False
        user.totp_secret = None
        user.last_totp_step = None
        db.commit()
        print(f"MFA disabled for {user.username}. The account now signs in with a password only.")
        return 0

    plaintext_secret = mfa.generate_totp_secret()
    user.totp_secret = mfa.encrypt_secret(plaintext_secret)
    user.mfa_enabled = True
    # Reset the replay guard: step counters from the previous secret are meaningless
    # against a new one, and leaving a high value would reject valid fresh codes.
    user.last_totp_step = None
    db.commit()

    _banner(f"MFA RE-ISSUED — {user.username}")
    _print_enrollment(user.username, plaintext_secret)
    print()
    return 0


def cmd_create(args, db) -> int:
    if args.role not in ROLES:
        print(f"ERROR: role must be one of {', '.join(ROLES)}")
        return 1
    if db.query(User).filter(User.username == args.username).first():
        print(f"ERROR: {args.username!r} already exists. Use reset-password instead.")
        return 1

    password = args.password or secrets.token_urlsafe(18)
    use_mfa = not args.no_mfa
    plaintext_secret = mfa.generate_totp_secret() if use_mfa else None

    user = User(
        username=args.username,
        password_hash=hash_password(password),
        role=args.role,
        is_active=True,
        created_by="cli",
        district_id=args.district_id,
        station_id=args.station_id,
        can_view_sensitive=args.can_view_sensitive,
        mfa_enabled=use_mfa,
        totp_secret=mfa.encrypt_secret(plaintext_secret) if plaintext_secret else None,
    )
    db.add(user)
    db.commit()

    _banner(f"ACCOUNT CREATED — {args.username}")
    print(f"  username : {args.username}")
    print(f"  password : {password}")
    print(f"  role     : {args.role}")
    print(f"  district : {args.district_id}")
    print(f"  sensitive: {args.can_view_sensitive}")
    if plaintext_secret:
        print()
        _print_enrollment(args.username, plaintext_secret)
    print("\n  Shown once. Store it now.\n")
    return 0


def cmd_disable(args, db) -> int:
    user = db.query(User).filter(User.username == args.username).first()
    if not user:
        print(f"ERROR: no account named {args.username!r}.")
        return 1
    user.is_active = False
    db.commit()
    print(f"{user.username} deactivated. Sign-in now returns 403.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="KSP Sentinel console account administration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List every console account.")

    p = sub.add_parser("reset-password", help="Set a new password (generated unless --password).")
    p.add_argument("--username", required=True)
    p.add_argument("--password", help="Use a specific password instead of a generated one.")

    p = sub.add_parser("reset-mfa", help="Issue a fresh TOTP secret, or turn MFA off.")
    p.add_argument("--username", required=True)
    p.add_argument("--disable", action="store_true", help="Turn MFA off for this account.")

    p = sub.add_parser("create", help="Create a console account.")
    p.add_argument("--username", required=True)
    p.add_argument("--role", required=True, choices=ROLES)
    p.add_argument("--password")
    p.add_argument("--district-id", type=int, default=None)
    p.add_argument("--station-id", type=int, default=None)
    p.add_argument("--can-view-sensitive", action="store_true")
    p.add_argument("--no-mfa", action="store_true", help="Password-only sign-in.")

    p = sub.add_parser("disable", help="Deactivate an account.")
    p.add_argument("--username", required=True)

    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        return {
            "list": cmd_list,
            "reset-password": cmd_reset_password,
            "reset-mfa": cmd_reset_mfa,
            "create": cmd_create,
            "disable": cmd_disable,
        }[args.command](args, db)
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
