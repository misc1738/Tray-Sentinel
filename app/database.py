"""
PostgreSQL production database adapter.
Replaces SQLite for scalable, concurrent access in production environments.

Usage:
    Set DATABASE_URL to PostgreSQL connection string in .env
    Example: DATABASE_URL=postgresql://user:password@localhost/sentinel
"""
import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Detect if PostgreSQL should be used
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:data/sentinel.db")
USE_POSTGRESQL = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")


def get_database_config() -> dict:
    """
    Get database configuration based on DATABASE_URL environment variable.
    
    Returns:
        Dict with database type and connection parameters
    """
    db_url = DATABASE_URL
    
    if USE_POSTGRESQL:
        # Parse PostgreSQL connection string
        # Format: postgresql://user:password@host:port/database
        try:
            import psycopg2
            from urllib.parse import urlparse
            
            parsed = urlparse(db_url)
            return {
                "type": "postgresql",
                "driver": "psycopg2",
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 5432,
                "user": parsed.username or "postgres",
                "password": parsed.password or "",
                "database": parsed.path.lstrip("/") or "sentinel",
            }
        except ImportError:
            logger.error("psycopg2 not installed but PostgreSQL URL detected. Install with: pip install psycopg2-binary")
            raise
    else:
        # SQLite (default)
        db_path = db_url.replace("sqlite:", "").replace("sqlite://", "")
        return {
            "type": "sqlite",
            "path": Path(db_path),
        }


def init_database_connection():
    """
    Initialize database connection pool based on configuration.
    Should be called once at application startup.
    """
    config = get_database_config()
    
    if config["type"] == "postgresql":
        logger.info(
            f"Initializing PostgreSQL connection to {config['host']}:{config['port']}/{config['database']}"
        )
        # In a real implementation, use psycopg2.pool.SimpleConnectionPool or asyncpg
        return init_postgresql_pool(config)
    else:
        logger.info(f"Using SQLite database at {config['path']}")
        return None


def init_postgresql_pool(config: dict):
    """
    Initialize PostgreSQL connection pool.
    
    Returns:
        Connection pool (psycopg2.pool or similar)
    """
    try:
        import psycopg2.pool
        
        pool = psycopg2.pool.SimpleConnectionPool(
            1,  # min connections
            10,  # max connections
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
        )
        logger.info("PostgreSQL connection pool initialized")
        return pool
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL pool: {e}")
        raise


# Migration information
POSTGRESQL_SCHEMA_MIGRATIONS = {
    "001_initial_schema": """
        -- Initial schema for Tracey's Sentinel on PostgreSQL
        
        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            description TEXT NOT NULL,
            source_device TEXT,
            acquisition_method TEXT NOT NULL,
            file_name TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS evidence_file (
            evidence_id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            file_size BIGINT,
            encrypted BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS audit_logs (
            audit_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            actor_user_id TEXT NOT NULL,
            actor_org_id TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            action TEXT NOT NULL,
            details JSONB,
            status TEXT NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            ip_address TEXT,
            session_id TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS rate_limits (
            limit_key TEXT PRIMARY KEY,
            request_count INTEGER DEFAULT 0,
            window_reset_at TIMESTAMP WITH TIME ZONE NOT NULL,
            last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS metrics (
            metric_id TEXT PRIMARY KEY,
            metric_name TEXT NOT NULL,
            value DOUBLE PRECISION NOT NULL,
            unit TEXT,
            tags JSONB,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS api_performance (
            performance_id TEXT PRIMARY KEY,
            endpoint TEXT NOT NULL,
            method TEXT NOT NULL,
            response_time_ms DOUBLE PRECISION NOT NULL,
            status_code INTEGER NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS webhooks (
            webhook_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            event_types TEXT[] NOT NULL,
            url TEXT NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            delivery_id TEXT PRIMARY KEY,
            webhook_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            response_code INTEGER,
            payload JSONB,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            FOREIGN KEY (webhook_id) REFERENCES webhooks(webhook_id) ON DELETE CASCADE
        );
    """,
    "002_create_indexes": """
        -- Performance indexes for common queries
        
        -- Evidence queries
        CREATE INDEX IF NOT EXISTS idx_evidence_case_id ON evidence(case_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_sha256 ON evidence(sha256);
        CREATE INDEX IF NOT EXISTS idx_evidence_created_at ON evidence(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_evidence_case_created ON evidence(case_id, created_at DESC);
        
        -- Audit queries
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_user_id, actor_org_id);
        CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource_type, resource_id);
        CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type);
        CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_logs(status);
        
        -- Metrics queries
        CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
        
        -- API performance queries
        CREATE INDEX IF NOT EXISTS idx_api_endpoint ON api_performance(endpoint);
        CREATE INDEX IF NOT EXISTS idx_api_timestamp ON api_performance(timestamp DESC);
        
        -- Rate limit cleanup
        CREATE INDEX IF NOT EXISTS idx_rate_limits_reset ON rate_limits(window_reset_at);
    """,
}


def run_migrations(connection):
    """
    Run all pending migrations on the database.
    
    Args:
        connection: Database connection object
    """
    logger.info("Running database migrations...")
    
    try:
        cursor = connection.cursor()
        
        # Create migrations table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                executed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()
        
        # Run each migration
        for migration_name, migration_sql in POSTGRESQL_SCHEMA_MIGRATIONS.items():
            cursor.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (migration_name,))
            if cursor.fetchone():
                logger.info(f"Migration {migration_name} already applied, skipping")
                continue
            
            logger.info(f"Applying migration {migration_name}...")
            cursor.execute(migration_sql)
            cursor.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (migration_name,)
            )
            connection.commit()
            logger.info(f"Migration {migration_name} completed")
        
        cursor.close()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        connection.rollback()
        raise
