import uuid
from sqlalchemy import create_engine, String, TypeDecorator
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

class GUID(TypeDecorator):
    """Platform-independent GUID/ID type.
    Stores as VARCHAR(36) or UUID.
    """
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)

import uuid
import logging
from urllib.parse import quote_plus, unquote
from pathlib import Path
from sqlalchemy import create_engine, String, TypeDecorator
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from backend.app.core.config import settings

logger = logging.getLogger("database")

class GUID(TypeDecorator):
    """Platform-independent GUID/ID type.
    Stores as VARCHAR(36) or UUID.
    """
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)


def sanitize_database_url(raw_url: str) -> str:
    """Safely sanitize, strip quotes/whitespace, and format database URLs."""
    if not raw_url:
        return "sqlite:///./kleanmaxpro.db"

    url = str(raw_url).strip()
    # Strip any enclosing quotes (e.g., copied from .env file directly into Railway variables)
    while (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
        url = url[1:-1].strip()

    if not url:
        return "sqlite:///./kleanmaxpro.db"

    # Normalize PostgreSQL driver prefix
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]

    # Handle unescaped @ or other special chars in password if needed
    if "://" in url and "@" in url:
        prefix, rest = url.split("://", 1)
        if "@" in rest:
            auth_part, host_part = rest.rsplit("@", 1)
            if ":" in auth_part:
                user_part, pass_part = auth_part.split(":", 1)
                clean_pass = quote_plus(unquote(pass_part))
                url = f"{prefix}://{user_part}:{clean_pass}@{host_part}"

    # Handle local relative sqlite database resolution and persistent volume check
    if url.startswith("sqlite:///./") or url == "sqlite:///kleanmaxpro.db":
        db_filename = "kleanmaxpro.db"
        # Check Railway Volume mount path or /data directory for persistence across container restarts
        vol_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
        if vol_path and Path(vol_path).is_dir():
            url = f"sqlite:///{(Path(vol_path) / db_filename).as_posix()}"
        elif Path("/data").is_dir():
            url = "sqlite:////data/kleanmaxpro.db"
        elif not Path(db_filename).exists():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            root_db = project_root / db_filename
            if root_db.exists():
                url = f"sqlite:///{root_db.as_posix()}"

    return url


# Sanitize configured database URL
db_url = sanitize_database_url(settings.DATABASE_URL)
db_init_error = None

# Connection arguments
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    connect_args = {"sslmode": "require"}

engine_kwargs = {
    "connect_args": connect_args,
    "pool_pre_ping": True,
}
if not db_url.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 1800,
        "pool_timeout": 30,
    })

try:
    # Test make_url before engine creation
    make_url(db_url)
    engine = create_engine(db_url, **engine_kwargs)
except Exception as e:
    import traceback
    db_init_error = f"{type(e).__name__}: {str(e)}"
    print(f"DATABASE INITIALIZATION WARNING: Could not connect to {db_url[:20]}... Fallback to SQLite. Error: {e}")
    traceback.print_exc()
    # Safe fallback to local SQLite so the web service starts and responds to healthchecks
    db_url = "sqlite:///./kleanmaxpro.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
