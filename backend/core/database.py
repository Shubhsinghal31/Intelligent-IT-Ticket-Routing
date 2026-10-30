"""
SQLAlchemy database engine and session management.

Provides:
- Engine: connection pool to PostgreSQL
- SessionLocal: factory for DB sessions
- Base: declarative base for ORM models
- get_db(): FastAPI dependency for injecting sessions
"""

from collections.abc import Generator

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.core.config import settings


# =====================================================
# Declarative Base
# =====================================================
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


# =====================================================
# Engine — manages the connection pool
# =====================================================
def create_db_engine() -> Engine:
    """
    Create SQLAlchemy engine with connection pooling.

    Pool config:
    - pool_size: persistent connections kept open
    - max_overflow: temporary extra connections under load
    - pool_timeout: max wait for a free connection (seconds)
    - pool_pre_ping: validate connections before use (handles stale conns)
    """
    engine = create_engine(
        str(settings.DATABASE_URL),
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        echo=settings.DB_ECHO,
        future=True,  # SQLAlchemy 2.0 style
    )
    logger.info(
        f"DB engine created | host={settings.DB_HOST} | "
        f"db={settings.DB_NAME} | pool_size={settings.DB_POOL_SIZE}"
    )
    return engine


engine: Engine = create_db_engine()


# =====================================================
# Session factory
# =====================================================
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,  # Explicit commit required (safer)
    autoflush=False,  # No auto-flush on query
    expire_on_commit=False,  # Objects usable after commit
)


# =====================================================
# FastAPI dependency
# =====================================================
def get_db() -> Generator[Session, None, None]:
    """
    Yield a DB session, ensure cleanup.

    Usage in endpoints:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            return db.query(Item).all()

    The session is closed after the request completes — even on exception.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    """Ping the database; used by /health endpoint."""
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
