import sys
import time
import pandas as pd
from tqdm import tqdm
import zcatalyst_sdk

from config import CHUNK_SIZE
from mapping import CSV_TO_TABLE_MAP
from utils import logger, StateManager, clean_data
from downloader import StratusDownloader
from datastore import DatastoreManager

def init_catalyst():
    """Initializes the Catalyst Python SDK. 
    Assumes environment variables or CLI configurations are already set up.
    """
    try:
        return zcatalyst_sdk.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize Zoho Catalyst SDK: {e}")
        logger.info("Please ensure you have authenticated via zcatalyst-cli or set the required environment variables.")
        sys.exit(1)

def run_migration():
    app = init_catalyst()
    state_manager = StateManager()
    downloader = StratusDownloader(app)
    datastore = DatastoreManager(app)

    logger.info("Starting Stratus to Data Store migration utility")
    
    # List files
    try:
        csv_files = downloader.list_csv_files()
        logger.info(f"Found {len(csv_files)} CSV files in Stratus bucket.")
    except Exception as e:
        logger.error("Could not fetch file list from Stratus. Exiting.")
        sys.exit(1)

    for csv_file in csv_files:
        if state_manager.is_completed(csv_file):
            logger.info(f"Skipping {csv_file}: already completed.")
            continue

        target_table = CSV_TO_TABLE_MAP.get(csv_file)
        if not target_table:
            logger.warning(f"No table mapping found for {csv_file}. Skipping.")
            continue

        logger.info(f"Processing {csv_file} -> {target_table}")
        start_time = time.time()
        
        # Download
        try:
            local_path = downloader.download_file(csv_file)
        except Exception as e:
            logger.error(f"Skipping {csv_file} due to download failure.")
            continue

        # Process in chunks
        rows_imported = 0
        chunk_idx = 1
        has_error = False

        try:
            # chunksize returns an iterator of DataFrames
            df_iterator = pd.read_csv(local_path, chunksize=CHUNK_SIZE, iterator=True)
            for chunk in df_iterator:
                logger.info(f"Reading chunk {chunk_idx} of {csv_file}")
                records = clean_data(chunk)
                
                # Bulk Insert
                try:
                    datastore.bulk_insert(target_table, records)
                    rows_imported += len(records)
                except Exception as e:
                    logger.error(f"Failed to insert chunk {chunk_idx} into {target_table}. Aborting this file.")
                    has_error = True
                    break
                
                chunk_idx += 1
                
        except Exception as e:
            logger.error(f"Failed to read {csv_file} using Pandas: {e}")
            has_error = True

        elapsed = round(time.time() - start_time, 2)
        
        # Cleanup temp file
        downloader.delete_temp(local_path)

        if not has_error:
            state_manager.mark_completed(csv_file)
            logger.info(f"SUCCESS {csv_file} completed. Imported {rows_imported} rows in {elapsed} seconds.")
        else:
            logger.warning(f"FAILURE {csv_file} aborted after {elapsed} seconds. Rows imported before failure: {rows_imported}.")

    logger.info("Migration process finished.")

if __name__ == "__main__":
    run_migration()
