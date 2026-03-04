"""
Compatibility wrapper for old app.py
Redirects to new backend structure
"""
from backend.app.database import init_db, get_db, SessionLocal, engine

__all__ = ["init_db", "get_db", "SessionLocal", "engine"]
