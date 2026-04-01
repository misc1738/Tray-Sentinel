# PostgreSQL Migration Guide

## Overview
This document provides instructions for migrating Tracey's Sentinel from SQLite (development) to PostgreSQL (production).

## Why PostgreSQL?

- **Concurrency**: Better handling of multiple simultaneous users
- **Scalability**: Handles large datasets and complex queries efficiently
- **Reliability**: ACID transactions, data integrity
- **Security**: Built-in authentication, role-based access control
- **Performance**: Connection pooling, query optimization, indexes

## Prerequisites

### Option 1: Local PostgreSQL Installation

**macOS (Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
createdb sentinel
```

**Ubuntu/Debian:**
```bash
sudo apt-get install postgresql postgresql-contrib
sudo service postgresql start
sudo -u postgres createdb sentinel
```

**Windows:**
- Download and install PostgreSQL from https://www.postgresql.org/download/windows/
- Use pgAdmin or psql for database management

### Option 2: Docker PostgreSQL

```bash
docker run --name sentinel-postgres -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=sentinel -p 5432:5432 \
  -d postgres:15-alpine
```

### Option 3: Managed Service

- AWS RDS
- Google Cloud SQL
- Azure Database for PostgreSQL
- Amazon Aurora

## Installation Steps

### 1. Install PostgreSQL Python Adapter

```bash
pip install psycopg2-binary  # or pip install psycopg2
pip install sqlalchemy alembic  # for advanced migration management
```

Or update all dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configure Database Connection

Edit `.env` and set `DATABASE_URL` to your PostgreSQL connection string:

```bash
# Example configurations
DATABASE_URL=postgresql://user:password@localhost:5432/sentinel
DATABASE_URL=postgresql://postgres:password@db.example.com/sentinel_prod
DATABASE_URL=postgresql://user@localhost/sentinel  # No password (local trust)
```

### 3. Backup SQLite Data (Important!)

```bash
# Create backup before migration
cp data/sentinel.db data/sentinel.db.backup
cp data/ledger.jsonl data/ledger.jsonl.backup
```

### 4. Export Data from SQLite

Create `scripts/export_sqlite_data.py`:

```python
import sqlite3
import json
from pathlib import Path

def export_sqlite_to_json(db_path: str, output_dir: str = "data/export"):
    """Export SQLite data to JSON for manual migration."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Export evidence table
    cursor.execute("SELECT * FROM evidence")
    with open(f"{output_dir}/evidence.json", "w") as f:
        json.dump([dict(row) for row in cursor.fetchall()], f, indent=2)
    
    # Export audit_logs table
    cursor.execute("SELECT * FROM audit_logs")
    with open(f"{output_dir}/audit_logs.json", "w") as f:
        audit_data = []
        for row in cursor.fetchall():
            r = dict(row)
            if r.get("details"):
                r["details"] = json.loads(r["details"])
            audit_data.append(r)
        json.dump(audit_data, f, indent=2)
    
    conn.close()
    print(f"Data exported to {output_dir}/")

if __name__ == "__main__":
    export_sqlite_to_json("data/sentinel.db")
```

Run: `python scripts/export_sqlite_data.py`

### 5. Run Migrations

The application will automatically run migrations on startup if you have the database module configured. To manually run migrations:

```python
from app.database import init_database_connection, run_migrations
import psycopg2

# Create connection
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    user="postgres",
    password="password",
    database="sentinel"
)

# Run migrations
run_migrations(conn)
conn.close()
```

Or use command line:
```bash
PYTHONPATH=. python -c "
from app.database import get_database_config, run_migrations
import psycopg2
config = get_database_config()
conn = psycopg2.connect(
    host=config['host'],
    port=config['port'],
    user=config['user'],
    password=config['password'],
    database=config['database']
)
run_migrations(conn)
"
```

### 6. Import Data

```python
import json
import psycopg2
from datetime import datetime, timezone

conn = psycopg2.connect("postgresql://user:password@localhost/sentinel")
cursor = conn.cursor()

# Import evidence
with open("data/export/evidence.json") as f:
    for row in json.load(f):
        cursor.execute("""
            INSERT INTO evidence (evidence_id, case_id, description, 
                source_device, acquisition_method, file_name, sha256, 
                created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row['evidence_id'], row['case_id'], row['description'],
            row['source_device'], row['acquisition_method'], row['file_name'],
            row['sha256'], row['created_at'], datetime.now(timezone.utc)
        ))

conn.commit()
cursor.close()
conn.close()
```

### 7. Update Configuration

Set environment variables:

```bash
# Production PostgreSQL
export DATABASE_URL="postgresql://user:password@prod-db.example.com:5432/sentinel"
export DB_POOL_MIN_SIZE=5
export DB_POOL_MAX_SIZE=20
export ENVIRONMENT=production
export DEBUG=false
```

### 8. Test Connection

```bash
python -c "from app.database import get_database_config; print(get_database_config())"
```

### 9. Start Application

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Connection Pooling

For production deployments, configure connection pooling in `app/container.py`:

```python
@property
def db_pool(self):
    """Get database connection pool."""
    if not hasattr(self, '_db_pool'):
        from app.database import init_database_connection
        self._db_pool = init_database_connection()
    return self._db_pool
```

## Performance Tuning

### PostgreSQL Configuration

Edit `postgresql.conf`:

```ini
# Connection settings
max_connections = 200
shared_buffers = 256MB

# Query performance
effective_cache_size = 1GB
work_mem = 10MB
maintenance_work_mem = 50MB

# Indexes
enable_indexscan = on
enable_bitmapscan = on
```

### Monitoring

Monitor performance with:

```sql
-- Connection status
SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;

-- Slow queries
SELECT query, calls, mean_exec_time FROM pg_stat_statements 
ORDER BY mean_exec_time DESC LIMIT 10;

-- Index usage
SELECT schemaname, tablename, indexname, idx_scan 
FROM pg_stat_user_indexes ORDER BY idx_scan DESC;
```

## Backup & Recovery

### Automated Backups

```bash
# Daily backup
pg_dump --username=postgres sentinel | gzip > /backups/sentinel_$(date +%Y%m%d).sql.gz

# Restore
gunzip < /backups/sentinel_20240101.sql.gz | psql --username=postgres sentinel
```

### Point-in-time Recovery

Enable WAL archiving in PostgreSQL for PITR:

```ini
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /wal_archive/%f && cp %p /wal_archive/%f'
```

## Rollback Plan

If you need to rollback to SQLite:

1. Keep SQLite backup: `data/sentinel.db.backup`
2. Export PostgreSQL data to JSON
3. Update `.env` to use SQLite path
4. Restart application

## Troubleshooting

### Connection Refused

```bash
psql -h localhost -U postgres  # Test basic connection
```

### Authentication Failed

Check PostgreSQL `pg_hba.conf` configuration:

```
# Allow local connections without password
local   all             all                                     trust
# Allow network connections with password
host    all             all             127.0.0.1/32            md5
```

### Slow Queries

Enable query logging:

```sql
ALTER DATABASE sentinel SET log_min_duration_statement = 1000;  -- Log queries > 1 second
```

## Production Checklist

- [ ] Database backup configured
- [ ] Connection pooling enabled
- [ ] Query logging configured
- [ ] Regular index maintenance scheduled
- [ ] User permissions properly set (not using superuser)
- [ ] SSL/TLS enabled for connections
- [ ] pg_stat_statements extension enabled for monitoring
- [ ] Replication configured (for high availability)
- [ ] Automated failover setup (if needed)

## References

- PostgreSQL Documentation: https://www.postgresql.org/docs/
- psycopg2 Documentation: https://www.psycopg.org/
- SQLAlchemy Documentation: https://docs.sqlalchemy.org/
