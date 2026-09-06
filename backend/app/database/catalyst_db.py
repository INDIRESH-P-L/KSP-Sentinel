"""ZCQL / Data Store access via the Zoho Catalyst Python SDK.

zcatalyst_sdk.initialize() takes no credentials of its own: it reads the auth context
the Catalyst runtime puts on the thread, which exists inside a deployed AppSail (or
`catalyst serve`) and nowhere else -- the same constraint documented in
app/api/admin_seed.py. So there is nothing to configure here, and nothing to hardcode;
outside that runtime initialization simply fails, and it must fail visibly.
"""
import zcatalyst_sdk

from app.logging import logger


class CatalystDatabase:
    def __init__(self):
        try:
            # No credentials are passed: the SDK picks up the runtime's auth context.
            self.app = zcatalyst_sdk.initialize()
        except Exception as e:
            # Deliberately not swallowed. Storing app=None and reporting a bare
            # "SDK not initialized" at the first query threw away the actual cause
            # (missing runtime context, wrong DC, expired credential) and made every
            # caller's error message useless. The one caller
            # (api/export.py::sync_to_catalyst) already wraps construction and reports
            # this message to the operator.
            logger.error(f"Failed to initialize Zoho Catalyst SDK for database: {e}")
            raise RuntimeError(f"Catalyst SDK initialization failed: {e}") from e
        logger.info("Zoho Catalyst SDK initialized for Data Store / ZCQL.")

    def execute_query(self, zcq_query: str):
        """
        Executes a ZCQL (Zoho Catalyst Query Language) query against the Cloud Data Store.
        """
        try:
            return self.app.zcql().execute_query(zcq_query)
        except Exception as e:
            logger.error(f"ZCQL Query failed: {e}")
            raise

    def get_table(self, table_name: str):
        """
        Retrieves a Table instance to perform standard CRUD operations.
        """
        try:
            return self.app.data_store().table(table_name)
        except Exception as e:
            logger.error(f"Failed to fetch table {table_name}: {e}")
            raise
