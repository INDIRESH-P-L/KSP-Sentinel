"""Idempotent additive schema migration.

`Base.metadata.create_all()` creates missing TABLES but never alters an existing one,
so a column added to a model after a database already exists is simply absent at
runtime — the ORM emits it in every SELECT and SQLite answers "no such column",
turning the whole feature into a 500.

This script closes that gap for the additive changes this codebase has accumulated.
Every step checks before it acts, so running it repeatedly is safe and running it on a
fresh database is a no-op.

    cd backend
    python scripts/migrate_schema.py            # apply
    python scripts/migrate_schema.py --dry-run  # report only

Note: this is deliberately additive only. It never drops or retypes a column, because
doing so on SQLite means a full table rebuild and this system holds evidence records
whose loss is not recoverable.
"""
import argparse
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import inspect, text  # noqa: E402

from app.database.models import Base  # noqa: E402
from app.database.session import SessionLocal, engine  # noqa: E402

# (table, column, DDL type). Additive only.
COLUMNS: list[tuple[str, str, str]] = [
    # Chain-of-custody: the from/to pair for a transfer previously lived only inside
    # the free-text `detail`, where the caller's optional note overwrote it.
    ("evidence_access_log", "custodian_before", "VARCHAR(100)"),
    ("evidence_access_log", "custodian_after", "VARCHAR(100)"),
]

# (table, index name, DDL). Indexes on columns that every list endpoint filters by.
INDEXES: list[tuple[str, str, str]] = [
    ("evidence_access_log", "ix_evidence_access_log_custodian_after",
     "CREATE INDEX ix_evidence_access_log_custodian_after "
     "ON evidence_access_log (custodian_after)"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply additive schema changes.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without writing.")
    args = parser.parse_args()

    # Creates any table that does not exist yet; never touches existing ones.
    if not args.dry_run:
        Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    applied, skipped, missing_tables = [], [], []

    with engine.begin() as conn:
        for table, column, ddl_type in COLUMNS:
            if table not in existing_tables:
                missing_tables.append(table)
                continue
            columns = {c["name"] for c in inspector.get_columns(table)}
            if column in columns:
                skipped.append(f"{table}.{column}")
                continue
            statement = f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"
            print(f"  + {statement}")
            if not args.dry_run:
                conn.execute(text(statement))
            applied.append(f"{table}.{column}")

        if not args.dry_run:
            # Re-inspect: the indexes below reference columns just added.
            inspector = inspect(engine)
            for table, index_name, ddl in INDEXES:
                if table not in existing_tables:
                    continue
                names = {i["name"] for i in inspector.get_indexes(table)}
                if index_name in names:
                    skipped.append(index_name)
                    continue
                print(f"  + {ddl}")
                conn.execute(text(ddl))
                applied.append(index_name)

    print()
    print(f"Applied : {len(applied)}   {', '.join(applied) or '-'}")
    print(f"Already present: {len(skipped)}")
    if missing_tables:
        print(f"Tables not present yet (will be created by create_all): "
              f"{', '.join(sorted(set(missing_tables)))}")
    if args.dry_run:
        print("\n(dry run — nothing was written)")
        return 0

    # Prove the ORM can now read what it declares.
    db = SessionLocal()
    try:
        from app.database.models import EvidenceAccessLog

        db.query(EvidenceAccessLog.custodian_before,
                 EvidenceAccessLog.custodian_after).limit(1).all()
        print("Verified: evidence custody columns are readable through the ORM.")
    except Exception as exc:  # noqa: BLE001
        print(f"VERIFICATION FAILED: {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
