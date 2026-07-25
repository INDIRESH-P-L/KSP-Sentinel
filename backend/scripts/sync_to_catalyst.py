import os
import sqlite3
import sys
import tempfile
import csv
import subprocess
from datetime import datetime, date

# Color logging helpers
def log_info(msg):
    print(f"\033[94m[INFO]\033[0m {msg}")

def log_success(msg):
    print(f"\033[92m[SUCCESS]\033[0m {msg}")

def log_warn(msg):
    print(f"\033[93m[WARN]\033[0m {msg}")

def log_error(msg):
    print(f"\033[91m[ERROR]\033[0m {msg}", file=sys.stderr)

# Table sync order to satisfy foreign key constraints
SYNC_TABLES = [
    {
        "name": "districts",
        "booleans": [],
        "datetimes": []
    },
    {
        "name": "taluks",
        "booleans": [],
        "datetimes": []
    },
    {
        "name": "police_stations",
        "booleans": [],
        "datetimes": []
    },
    {
        "name": "crime_categories",
        "booleans": [],
        "datetimes": []
    },
    {
        "name": "crime_subcategories",
        "booleans": [],
        "datetimes": []
    },
    {
        "name": "fir_cases",
        "booleans": [],
        "datetimes": ["date_reported", "date_occurred"]
    },
    {
        "name": "accused",
        "booleans": ["repeat_offender", "history_sheet"],
        "datetimes": []
    },
    {
        "name": "fir_accused",
        "booleans": [],
        "datetimes": []
    },
    {
        "name": "arrests",
        "booleans": [],
        "datetimes": ["arrest_date"]
    },
    {
        "name": "investigations",
        "booleans": [],
        "datetimes": ["last_updated"]
    },
    {
        "name": "chargesheets",
        "booleans": [],
        "datetimes": ["filed_date"]
    },
    {
        "name": "convictions",
        "booleans": [],
        "datetimes": ["conviction_date"]
    },
    {
        "name": "officers",
        "booleans": [],
        "datetimes": []
    },
    {
        "name": "crime_review_monthly",
        "booleans": [],
        "datetimes": ["created_at"]
    },
    {
        "name": "crime_review_yearly",
        "booleans": [],
        "datetimes": []
    },
    {
        "name": "crime_statistics",
        "booleans": [],
        "datetimes": []
    }
]

def clean_value(col, val, booleans, datetimes):
    """
    Sanitizes values to match Catalyst's Datastore CSV requirements.
    """
    if val is None:
        return ""
        
    if col in booleans:
        return "true" if bool(val) else "false"
        
    if col in datetimes:
        try:
            if isinstance(val, str):
                # Clean fractional seconds if any
                clean_val = val.split(".")[0]
                dt = datetime.strptime(clean_val, "%Y-%m-%d %H:%M:%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(val, (datetime, date)):
                return val.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(val)
            
    # For datetimes that might not be declared in the list but match by name
    if (col.endswith("_date") or col.startswith("date_") or col == "created_at") and isinstance(val, str):
        try:
            clean_val = val.split(".")[0]
            dt = datetime.strptime(clean_val, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return val

    return str(val)

def main():
    db_path = "ksp_sentinel.db"
    if not os.path.exists(db_path):
        log_error(f"SQLite database '{db_path}' not found. Please run baseline seeding first.")
        sys.exit(1)

    # Connect to local SQLite DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    log_info("Starting data migration using Catalyst CLI...")

    # Temp directory inside workspace to hold files (per CLI rules)
    temp_dir = os.path.join(os.getcwd(), "datasets", "exports", "temp_sync")
    os.makedirs(temp_dir, exist_ok=True)

    for table_config in SYNC_TABLES:
        table_name = table_config["name"]
        booleans = table_config["booleans"]
        datetimes = table_config["datetimes"]

        # Check if table exists in local SQLite
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if not cursor.fetchone():
            log_warn(f"Table '{table_name}' does not exist in local SQLite. Skipping.")
            continue

        # Get local row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_rows = cursor.fetchone()[0]
        if total_rows == 0:
            log_info(f"Table '{table_name}' is empty. Skipping.")
            continue

        log_info(f"Preparing CSV for table '{table_name}' ({total_rows} rows)...")

        # Fetch column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        colnames = [info[1] for info in cursor.fetchall()]

        # Query all rows
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        # Write clean rows to temp CSV file
        csv_file_path = os.path.join(temp_dir, f"{table_name}.csv")
        with open(csv_file_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(colnames)
            for row in rows:
                cleaned_row = [clean_value(col, val, booleans, datetimes) for col, val in zip(colnames, row)]
                writer.writerow(cleaned_row)

        # Write clean Catalyst import configuration JSON
        config_file_path = os.path.join(temp_dir, f"{table_name}_config.json")
        import json
        config_data = {
            "table_identifier": table_name,
            "operation": "insert"
        }
        with open(config_file_path, "w", encoding="utf-8") as jsonfile:
            json.dump(config_data, jsonfile)

        log_info(f"Executing: catalyst ds:import {table_name}.csv --config {table_name}_config.json")
        try:
            # Spawn CLI ds:import command with config parameter and auto-confirm stdin input
            result = subprocess.run(
                ["catalyst", "ds:import", csv_file_path, "--config", config_file_path],
                input="yes\n",
                capture_output=True,
                text=True,
                check=True
            )
            log_success(f"Successfully synced table '{table_name}' to Catalyst Cloud Datastore!")
            if result.stdout:
                print(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            log_error(f"Failed to sync table '{table_name}'!")
            if e.stderr:
                print(e.stderr.strip(), file=sys.stderr)
            if e.stdout:
                print(e.stdout.strip())


        # Clean up temp CSV and JSON config files
        if os.path.exists(csv_file_path):
            os.remove(csv_file_path)
        if os.path.exists(config_file_path):
            os.remove(config_file_path)


    # Clean up temp directory
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass

    conn.close()
    log_success("Data migration process completed!")

if __name__ == "__main__":
    main()
