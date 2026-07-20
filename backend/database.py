"""
PostgreSQL database connection and session management.

This module provides database connection pooling, session management,
and base configuration for the BiasLens application database.
"""

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, pool
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://biaslens:biaslens@localhost:5432/biaslens"
)

# Connection pool settings
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=True,  # Verify connections before using them
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    future=True,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

# Base class for declarative models
Base = declarative_base()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Set database-specific connection parameters.
    Currently handles SQLite pragmas for local development.
    """
    cursor = dbapi_conn.cursor()
    # Enable foreign key constraints for SQLite
    if "sqlite" in DATABASE_URL:
        cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@event.listens_for(Engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log connection checkout events for debugging connection pool issues."""
    logger.debug(f"Connection checked out from pool: {connection_record.info}")


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session for FastAPI endpoints.
    
    Yields:
        Session: SQLAlchemy database session
        
    Example:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database session error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions outside of FastAPI dependency injection.
    
    Yields:
        Session: SQLAlchemy database session
        
    Example:
        with get_db_context() as db:
            user = db.query(User).first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database transaction failed: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database by creating all tables defined in models.
    Should be called on application startup or during migrations.
    """
    try:
        # Import all models here to ensure they're registered with Base
        from backend.models import (
            analysis,
            job_description,
            organization,
            screening_pattern,
            user,
        )
        
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


def close_db() -> None:
    """
    Close all database connections and dispose of the connection pool.
    Should be called on application shutdown.
    """
    try:
        engine.dispose()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connections: {str(e)}")


def check_db_connection() -> bool:
    """
    Verify database connectivity.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("Database connection check successful")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {str(e)}")
        return False


def get_db_info() -> dict:
    """
    Get information about the current database connection and pool status.
    
    Returns:
        dict: Database connection information including pool statistics
    """
    pool_status = engine.pool.status()
    
    return {
        "url": DATABASE_URL.split("@")[-1],  # Hide credentials
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW,
        "pool_timeout": POOL_TIMEOUT,
        "pool_status": pool_status,
        "dialect": engine.dialect.name,
        "driver": engine.driver,
    }


class DatabaseHealthCheck:
    """
    Health check utility for monitoring database connection status.
    Used by application health endpoints.
    """
    
    @staticmethod
    def check() -> dict:
        """
        Perform comprehensive database health check.
        
        Returns:
            dict: Health check results with status and details
        """
        try:
            with engine.connect() as conn:
                result = conn.execute("SELECT 1")
                result.fetchone()
            
            pool_status = engine.pool.status()
            
            return {
                "status": "healthy",
                "database": "connected",
                "pool": pool_status,
                "details": get_db_info(),
            }
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
            }