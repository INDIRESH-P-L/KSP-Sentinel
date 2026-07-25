# Zoho Catalyst Data Migration Utility

This utility provides a robust, production-ready pipeline to migrate CSV files stored in Zoho Catalyst Stratus directly into Catalyst Data Store tables.

## Features

- **Chunked Processing**: Processes large CSV files (>1GB) using Pandas chunks (default 5000 rows).
- **Automated Data Cleaning**: Strips whitespace, converts `NaN` / empty strings to `None` for proper JSON serialization, and formats dates automatically.
- **Resiliency**: Built-in retry mechanisms for API limits or network drops, utilizing `MAX_RETRIES` and `RETRY_DELAY`.
- **State Management**: Tracks completed files via `migration_state.json`. If the process is interrupted, running the script again will skip already completed files.
- **Detailed Logging**: Outputs statistics, including elapsed time and row counts, to both the console and a local `migration.log` file.

## Prerequisites

1. **Python 3.12+**
2. **Zoho Catalyst Python SDK** and **Pandas** (see `requirements.txt`)
3. A Catalyst project with an initialized **Data Store** and **Stratus Bucket**.

## How to Configure Catalyst

You must first have your Catalyst project set up. Ensure that:
- Your Catalyst Data Store has tables created whose schemas (columns and data types) match the headers of your CSV files.
- The `mapping.py` file is updated to reflect the exact CSV filename -> Data Store Table Name mapping.

### Authentication

The script uses standard Zoho Catalyst SDK authentication. 
Before running, you must either:
1. Have the `zcatalyst-cli` installed and be logged in via `catalyst login`.
2. Provide the necessary Catalyst environment variables (`X_ZOHO_CATALYST_ORG_ID`, etc.) if running in an automated environment.

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Edit `config.py` to match your environment:
- `BUCKET_NAME`: The name of your Stratus bucket (default: `sentinel-migration-bucket`).
- `CHUNK_SIZE`: Number of rows to process and insert per batch (default: `5000`).
- `MAX_RETRIES`: Number of times to retry a failed bulk insert chunk (default: `3`).

## Running the Migration

Simply execute the main orchestrator script:

```bash
python migrate.py
```

### Expected Output

You will see logs detailing the download of files to the `tmp/` folder, the chunks being read, and the import completion status:

```
2026-07-25 15:30:00 - INFO - Found 8 CSV files in Stratus bucket.
2026-07-25 15:30:01 - INFO - Processing fir_details.csv -> FIR_DETAILS
2026-07-25 15:30:01 - INFO - Downloading fir_details.csv...
2026-07-25 15:30:03 - INFO - Reading chunk 1 of fir_details.csv
2026-07-25 15:30:05 - INFO - Imported 5000 rows into FIR_DETAILS
...
2026-07-25 15:30:10 - INFO - Deleted temporary file: .../tmp/fir_details.csv
2026-07-25 15:30:10 - INFO - SUCCESS fir_details.csv completed. Imported 15000 rows in 9 seconds.
```

## Troubleshooting

- **Duplicate Key Errors**: If you encounter errors inserting rows, ensure your CSVs do not violate `UNIQUE` or `PRIMARY KEY` constraints configured in the Data Store.
- **Empty File Exceptions**: If a download fails or states it is empty, verify the file isn't corrupted inside Stratus.
- **Authentication Failures**: Run `catalyst login` again to refresh your session token.
