"""
Exports the current SQLAlchemy schema (backend/app/database/models.py) as a JSON
description of tables/columns/keys, for use as a checklist when creating tables in the
Catalyst Data Store console. Catalyst Data Store tables are created through the console
or `catalyst datastore` CLI commands, not from an arbitrary JSON import, so this is a
migration reference document, not an automated importer -- there's no verified Catalyst
CLI command that ingests this format directly.

Usage:
    python scripts/export_catalyst_datastore_schema.py > catalyst/datastore_schema.json
"""
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from backend.app.database import models

# Best-effort mapping from SQLAlchemy column types to Data Store's column types.
# Verify against the actual "Add Column" type dropdown in the Data Store console --
# this mapping isn't sourced from official Catalyst docs, just the closest reasonable
# match by name.
TYPE_MAP = {
    "INTEGER": "BIGINT",
    "VARCHAR": "VARCHAR",
    "TEXT": "TEXT",
    "FLOAT": "DECIMAL",
    "DATETIME": "DATETIME",
    "DATE": "DATETIME",
    "BOOLEAN": "BOOLEAN",
}


def export_schema():
    tables = []
    for table in models.Base.metadata.sorted_tables:
        columns = []
        for col in table.columns:
            type_name = type(col.type).__name__.upper()
            columns.append({
                "name": col.name,
                "sqlalchemy_type": str(col.type),
                "suggested_datastore_type": TYPE_MAP.get(type_name, "VARCHAR"),
                "primary_key": col.primary_key,
                "nullable": col.nullable,
                "foreign_key": [str(fk.target_fullname) for fk in col.foreign_keys] or None,
                "unique": col.unique or False,
            })
        tables.append({"table_name": table.name, "columns": columns})

    return {
        "note": "Reference for manually creating tables in the Catalyst Data Store console "
                "(console.catalyst.zoho.com -> Data Store -> Create Table). Not an automated import format.",
        "tables": tables,
    }


if __name__ == "__main__":
    print(json.dumps(export_schema(), indent=2))
