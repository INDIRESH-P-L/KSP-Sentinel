"""Role hierarchy, RBAC dependencies, and district/station data scoping.

Roles are ranked (higher number = more operational trust), NOT a simple allow-list --
`require_role("Superintendent")` means "Superintendent or above", so a new role can be
inserted into the hierarchy without updating every call site.

Admin is intentionally NOT "above" Superintendent here: Admin manages accounts, it does
not automatically see crime data (separation of duties, see deny_admin_from_crime_data
below). Treat Admin as an orthogonal management role, not the top of the operational
ladder.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy import or_
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.dependencies import get_current_user, oauth2_scheme

# Higher number = more operational access to crime data. Admin is deliberately
# excluded from this ladder -- see deny_admin_from_crime_data.
ROLE_RANK = {
    "analyst": 1,
    "investigator": 2,
    "superintendent": 3,
}


def require_role(min_role: str):
    """FastAPI dependency factory: 403s unless the caller's role outranks min_role
    on the operational ladder above. Admin never satisfies this (not on the ladder)."""
    min_rank = ROLE_RANK.get(min_role.lower())
    if min_rank is None:
        raise ValueError(f"Unknown role '{min_role}' in require_role()")

    def _dependency(current_user: dict = Depends(get_current_user)):
        user_rank = ROLE_RANK.get(str(current_user.get("role", "")).lower())
        if user_rank is None or user_rank < min_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role} clearance or higher",
            )
        return current_user

    return _dependency


def require_token_role(min_role: str):
    """Like require_role(), but additionally demands a REAL bearer token.

    get_current_user() deliberately falls back to a permissive "Investigator" identity
    when no token is presented ("Permissive default for sandbox local development"), so
    require_role("investigator") lets an anonymous request straight through -- it only
    filters Analysts. That is fine for browsing endpoints in a sandbox, but not for
    routes that stream bulk data out of the system.

    This factory checks the raw token first and 401s when it is absent, then applies the
    same rank comparison. Kept as a separate helper rather than tightening
    get_current_user, which would change authentication behaviour for every endpoint in
    the app and break the offline demo-login path.
    """
    min_rank = ROLE_RANK.get(min_role.lower())
    if min_rank is None:
        raise ValueError(f"Unknown role '{min_role}' in require_token_role()")

    def _dependency(token: str = Depends(oauth2_scheme),
                    current_user: dict = Depends(get_current_user)):
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for this endpoint",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_rank = ROLE_RANK.get(str(current_user.get("role", "")).lower())
        if user_rank is None or user_rank < min_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role} clearance or higher",
            )
        return current_user

    return _dependency


def deny_admin_from_crime_data(current_user: dict = Depends(get_current_user)):
    """Separation of duties: an Admin account manages *accounts*, not crime data.
    Applied to crime-data endpoints alongside get_current_user so a leaked/misused
    Admin token can't be used to browse FIRs, victims, or the criminal network."""
    if str(current_user.get("role", "")).lower() == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts do not have crime-data access (separation of duties). "
                   "Use an Analyst/Investigator/Superintendent account.",
        )
    return current_user


def scope_to_user_district(current_user: dict = Depends(get_current_user)):
    """Returns the district_id an Analyst/Investigator should be restricted to, or
    None if the query should be unscoped (Superintendent/Admin, or an
    Analyst/Investigator account with no district assigned yet).

    Deliberately permissive on None: most accounts in this system today (the legacy
    demo-password fallback, and any DB account an admin hasn't assigned a district to
    yet) have no district_id. Treating "no district on file" as "show nothing" would
    silently empty out the entire app for those accounts instead of restricting them
    -- a functional regression, not a security win. Scoping only activates once an
    admin has actually assigned a district to that user.
    """
    role = str(current_user.get("role", "")).lower()
    if role in ("analyst", "investigator"):
        return current_user.get("district_id")
    return None


def apply_district_scope(query, district_column, district_id: int | None):
    """Applies the district filter from scope_to_user_district to a SQLAlchemy query,
    if a restriction is actually in effect."""
    if district_id is None:
        return query
    return query.filter(district_column == district_id)
