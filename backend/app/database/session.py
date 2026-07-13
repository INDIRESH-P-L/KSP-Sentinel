import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Read DB configuration. Default to SQLite if Postgres url is unavailable/empty.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ksp_sentinel.db")
SQLITE_URL = os.getenv("SQLITE_URL", "sqlite:///./ksp_sentinel.db")

# If SQLITE_URL is used, we need check_same_thread=False
connect_args = {}
if DATABASE_URL.startswith("sqlite") or SQLITE_URL.startswith("sqlite"):
    db_url = SQLITE_URL
    connect_args = {"check_same_thread": False}
else:
    db_url = DATABASE_URL

engine = create_engine(db_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
