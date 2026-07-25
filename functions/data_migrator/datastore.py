import time
from utils import logger
from config import MAX_RETRIES, RETRY_DELAY_SECONDS

class DatastoreManager:
    def __init__(self, catalyst_app):
        self.app = catalyst_app

    def get_table(self, table_name: str):
        try:
            return self.app.datastore().table(table_name)
        except Exception as e:
            logger.error(f"Failed to access Data Store table '{table_name}': {e}")
            raise

    def bulk_insert(self, table_name: str, records: list[dict]):
        """Inserts a list of dictionaries into the Catalyst Data Store with retry logic."""
        if not records:
            return

        table = self.get_table(table_name)
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Catalyst Python SDK insert_rows handles multiple records
                response = table.insert_rows(records)
                logger.info(f"Imported {len(records)} rows into {table_name}")
                return response
            except Exception as e:
                logger.warning(f"Batch insert failed on attempt {attempt}/{MAX_RETRIES} for {table_name}: {e}")
                if attempt == MAX_RETRIES:
                    logger.error(f"Max retries reached for inserting into {table_name}. Failing chunk.")
                    raise
                time.sleep(RETRY_DELAY_SECONDS)
