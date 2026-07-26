import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

class Settings(BaseSettings):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "ksp_sentinel_super_secret_cryptographic_key_2026")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ksp_sentinel.db")
    SQLITE_URL: str = os.getenv("SQLITE_URL", "sqlite:///./ksp_sentinel.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROK_API_KEY: str = os.getenv("GROK_API_KEY", "")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")
    
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "local")
    CATALYST_FOLDER_ID: str = os.getenv("CATALYST_FOLDER_ID", "48446000000036421")
    CATALYST_AUTH_TOKEN: str = os.getenv("CATALYST_AUTH_TOKEN", "")
    CATALYST_ORG_ID: str = os.getenv("CATALYST_ORG_ID", "60078436924")
    CATALYST_STRATUS_BUCKET: str = os.getenv("CATALYST_STRATUS_BUCKET", "sentinel-migration-bucket")

    # Fernet key encrypting TOTP secrets at rest (backend/app/core/mfa.py). Left blank
    # here on purpose -- generated once and persisted to .env on first startup rather
    # than hardcoded, since a hardcoded key defeats the point of encrypting the column.
    TOTP_ENCRYPTION_KEY: str = os.getenv("TOTP_ENCRYPTION_KEY", "")

    # 5-minute window between password verification and OTP submission.
    PRE_AUTH_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("PRE_AUTH_TOKEN_EXPIRE_MINUTES", "5"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    class Config:
        env_file = ".env"

settings = Settings()
