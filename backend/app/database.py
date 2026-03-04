"""
Database configuration and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from app.config import settings
from app.models.base import Base

engine_kwargs = {
    "echo": settings.DEBUG,
}

# SQLite-specific configuration
if "sqlite" in settings.DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Connection pooling for PostgreSQL/MySQL
    engine_kwargs["pool_size"] = 10  # Number of connections to maintain
    engine_kwargs["max_overflow"] = 20  # Additional connections when pool is full
    engine_kwargs["pool_pre_ping"] = True  # Verify connections before using

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print(f"✓ Database initialized: {settings.DATABASE_URL}")


def get_db():
    """Dependency for FastAPI to get DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for database session"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
