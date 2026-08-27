"""Domain service layer for the Investigation Intelligence features (NEW_FEATURES.md).

Kept separate from app/core/ (cross-cutting infrastructure: auth, rate limiting,
masking) — these are domain jobs that routers call, so the routes stay thin and the
logic is testable and reusable outside a request.
"""
