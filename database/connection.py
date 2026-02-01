"""
Minimal database connection helpers for SmartGrid Sentinel MVP.
Uses SQLAlchemy with SQLite for fast local runs; can be switched to Postgres via DATABASE_URL env.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./smartgrid.db')

# SQLite needs check_same_thread flag
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Return a DB session (use in scripts)."""
    return SessionLocal()


def init_db():
    """Create database tables based on models metadata."""
    try:
        from .models import Base
        Base.metadata.create_all(bind=engine)
        print("Database initialized")
    except Exception as e:
        print(f"Failed to initialize DB: {e}")

