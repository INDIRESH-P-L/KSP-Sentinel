import os
import zcatalyst_sdk
from backend.app.config import settings
from backend.app.logging import logger

class StorageService:
    def __init__(self):
        self.provider = settings.STORAGE_PROVIDER
        self.catalyst_app = None
        
        if self.provider == "catalyst":
            try:
                # Initialize Zoho Catalyst Python SDK
                self.catalyst_app = zcatalyst_sdk.initialize()
                logger.info("Zoho Catalyst SDK initialized successfully for cloud storage.")
            except Exception as e:
                logger.error(f"Failed to initialize Zoho Catalyst SDK for cloud storage: {e}")
                self.provider = "local" # Fallback to local
                
    def upload_file(self, file_content: bytes, filename: str) -> str:
        """
        Uploads a file to the configured storage provider.
        Returns the public URL or identifier of the stored file.
        """
        if self.provider == "catalyst" and self.catalyst_app:
            try:
                # Write content to a temporary file locally so we can upload it
                temp_path = os.path.join("/tmp", filename)
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                with open(temp_path, "wb") as f:
                    f.write(file_content)
                
                # Fetch folder ID from config
                if not settings.CATALYST_FOLDER_ID:
                    raise ValueError("CATALYST_FOLDER_ID is not configured in settings")
                folder_id = int(settings.CATALYST_FOLDER_ID)
                folder = self.catalyst_app.file_store().get_folder_instance(folder_id)
                upload_res = folder.upload_file(file_path=temp_path)
                
                # Clean up local temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
                # Extract the uploaded file ID
                file_id = upload_res.get("file_id")
                logger.info(f"File '{filename}' uploaded successfully to Zoho Catalyst File Store. ID: {file_id}")
                return str(file_id)
            except Exception as e:
                logger.error(f"Failed to upload file to Zoho Catalyst: {e}. Falling back to local storage.")
                return self._upload_local(file_content, filename)
        else:
            return self._upload_local(file_content, filename)
            
    def _upload_local(self, file_content: bytes, filename: str) -> str:
        upload_dir = os.path.join(os.getcwd(), "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            f.write(file_content)
        logger.info(f"File '{filename}' saved locally to {file_path}")
        return file_path

storage_service = StorageService()
