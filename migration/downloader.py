import os
import io
from utils import logger
from config import BUCKET_NAME, TEMP_DIR

class StratusDownloader:
    def __init__(self, catalyst_app):
        self.app = catalyst_app
        self.bucket = None
        
    def _get_bucket(self):
        if not self.bucket:
            try:
                self.bucket = self.app.stratus().bucket(BUCKET_NAME)
            except Exception as e:
                logger.error(f"Failed to access Stratus bucket '{BUCKET_NAME}': {e}")
                raise
        return self.bucket

    def list_csv_files(self) -> list[str]:
        """Lists all CSV files in the configured Stratus bucket."""
        try:
            bucket = self._get_bucket()
            # Catalyst SDK list_files typically returns a list of file details
            files = bucket.get_object_details()
            # Handle different versions of the SDK response
            if isinstance(files, dict) and "data" in files:
                files = files["data"]
                
            csv_files = []
            for f in files:
                fname = f.get("file_name") if isinstance(f, dict) else getattr(f, "file_name", None)
                if not fname:
                    fname = f.get("name") if isinstance(f, dict) else getattr(f, "name", None)
                if fname and str(fname).endswith(".csv"):
                    csv_files.append(str(fname))
            return csv_files
        except Exception as e:
            logger.error(f"Failed to list files in bucket: {e}")
            raise

    def download_file(self, filename: str) -> str:
        """Downloads a file to the temporary directory and returns the local path."""
        logger.info(f"Downloading {filename}...")
        try:

            bucket = self._get_bucket()
            obj = bucket.get_object(filename)
            content = obj.content if hasattr(obj, "content") else (obj.read() if hasattr(obj, "read") else obj)
            local_path = os.path.join(TEMP_DIR, filename)
            
            if not content:
                raise Exception(f"File {filename} is empty or could not be read.")

            with open(local_path, 'wb') as f:
                f.write(content)
            
            return local_path
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            raise

    def delete_temp(self, local_path: str):
        """Safely removes a temporary file."""
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
                logger.info(f"Deleted temporary file: {local_path}")
        except Exception as e:
            logger.warning(f"Failed to delete {local_path}: {e}")
