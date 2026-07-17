import zcatalyst_sdk
from backend.app.logging import logger

class CatalystDatabase:
    def __init__(self):
        self.app = None
        try:
            # Initialize Zoho Catalyst Python SDK
            self.app = zcatalyst_sdk.initialize()
            logger.info("Zoho Catalyst SDK initialized for Data Store / ZCQL.")
        except Exception as e:
            logger.error(f"Failed to initialize Zoho Catalyst SDK for database: {e}")

    def execute_query(self, zcq_query: str):
        """
        Executes a ZCQL (Zoho Catalyst Query Language) query against the Cloud Data Store.
        """
        if not self.app:
            raise RuntimeError("Catalyst SDK not initialized")
        try:
            return self.app.zcql().execute_query(zcq_query)
        except Exception as e:
            logger.error(f"ZCQL Query failed: {e}")
            raise

    def get_table(self, table_name: str):
        """
        Retrieves a Table instance to perform standard CRUD operations.
        """
        if not self.app:
            raise RuntimeError("Catalyst SDK not initialized")
        try:
            return self.app.data_store().table(table_name)
        except Exception as e:
            logger.error(f"Failed to fetch table {table_name}: {e}")
            raise
