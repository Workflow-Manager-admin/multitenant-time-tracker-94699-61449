"""
Database connection management for the multitenant time tracker.

Provides database engine, session management, and connection utilities.
"""
import os
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from .models import Base

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./time_tracker.db")
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///./test_time_tracker.db")

# Create engines
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    poolclass=StaticPool if "sqlite" in DATABASE_URL else None,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

test_engine = create_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=StaticPool if "sqlite" in TEST_DATABASE_URL else None,
    connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {}
)

# Create session factories
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# Enable foreign key constraints for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite connections."""
    if "sqlite" in str(dbapi_connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def create_test_tables():
    """Create all test database tables."""
    Base.metadata.create_all(bind=test_engine)


def drop_test_tables():
    """Drop all test database tables."""
    Base.metadata.drop_all(bind=test_engine)


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session.
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# PUBLIC_INTERFACE
def get_test_db() -> Generator[Session, None, None]:
    """
    Dependency to get test database session.
    
    Yields:
        Session: SQLAlchemy test database session
    """
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


class DatabaseManager:
    """Database management utilities."""
    
    @staticmethod
    def init_db():
        """Initialize the database with tables."""
        create_tables()
    
    @staticmethod
    def init_test_db():
        """Initialize the test database with tables."""
        create_test_tables()
    
    @staticmethod
    def reset_test_db():
        """Reset test database by dropping and recreating tables."""
        drop_test_tables()
        create_test_tables()
