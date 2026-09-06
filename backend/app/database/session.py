"""Engine + session factory -- the one place the effective database URL is decided.

`.env` discovery is delegated to app.config. This module used to recompute the path
itself as `backend/.env`, which is precisely the non-existent file app/config.py's
docstring describes fixing: two modules disagreeing about where `.env` lives is how
an operator's settings end up loaded for half the process. ENV_PATH is discovered
once, there, and reused here. (app.config imports nothing from this package, so
there is no cycle.)

The resolved URL and the dialect flag derived from it are exported so that
models.py reads the SAME decision instead of re-deriving it from os.getenv -- they
disagreed, and the disagreement was invisible until a PostGIS deployment quietly got
TEXT columns.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import ENV_PATH
from app.logging import logger

load_dotenv(ENV_PATH, override=False)

db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ksp_sentinel.db")
default_sqlite_url = f"sqlite:///{db_path}"

# DATABASE_URL alone selects the engine. SQLITE_URL is only the fallback for when it
# is unset or blank -- it used to participate in the choice, and since it always
# defaults to a sqlite URL the condition was constant-true: `DATABASE_URL=postgresql://...`
# was accepted, ignored, and the app booted against an empty local SQLite file while
# reporting itself online.
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
SQLITE_URL = (os.getenv("SQLITE_URL") or "").strip() or default_sqlite_url

# Heroku/Render-style `postgres://` is not a SQLAlchemy 2.x dialect name and fails with
# NoSuchModuleError; the scheme is the only difference.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

# A malformed URL raises here, at import, rather than at the first query.
db_url = make_url(DATABASE_URL or SQLITE_URL)

IS_SQLITE = db_url.get_backend_name() == "sqlite"
# Consumed by models.py to pick PostGIS/pgvector column types over the TEXT fallbacks.
USE_POSTGRES = db_url.get_backend_name() == "postgresql"

# SQLite's connection object is single-thread by default; FastAPI hands the same
# session out across the threadpool.
connect_args = {"check_same_thread": False} if IS_SQLITE else {}

# render_as_string(hide_password=True) -- never str(url), which prints the password.
logger.info(
    "Database engine: %s (%s)",
    db_url.render_as_string(hide_password=True),
    "DATABASE_URL" if DATABASE_URL else "SQLITE_URL fallback",
)

if IS_SQLITE and db_url.database not in (None, "", ":memory:") and not os.path.exists(db_url.database):
    # On Catalyst AppSail the .db file is excluded by backend/.catalystignore, so no
    # database is ever uploaded and create_all() builds empty tables on every cold
    # start. Say so out loud: "online but no data" is otherwise indistinguishable
    # from a query bug.
    logger.warning(
        "SQLite file %s does not exist -- starting from empty tables. On Catalyst AppSail "
        "the container filesystem is ephemeral and *.db is excluded from the deploy; set "
        "DATABASE_URL to a managed database for anything that must persist.",
        db_url.database,
    )

engine = create_engine(
    db_url,
    connect_args=connect_args,
    # AppSail containers idle between requests and the far end drops the socket; without
    # a pre-ping the first query after an idle period fails instead of reconnecting.
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
