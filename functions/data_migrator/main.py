import logging
from migrate import run_migration

def handler(context, basicio):
    try:
        run_migration()
        context.log("Migration completed successfully.")
        basicio.write("Migration process finished successfully.")
    except Exception as e:
        context.log(f"Migration failed: {e}")
        basicio.write(f"Error during migration: {e}")
    finally:
        context.close()
