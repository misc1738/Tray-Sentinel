"""Performance metrics collection and analysis."""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: str
    metric_name: str
    value: float
    unit: str
    tags: dict


class MetricsCollector:
    """Collect and analyze performance metrics."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_tables()

    def init_tables(self):
        """Initialize metrics tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    metric_id TEXT PRIMARY KEY,
                    metric_name TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT,
                    tags TEXT,
                    timestamp TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_performance (
                    performance_id TEXT PRIMARY KEY,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    response_time_ms REAL NOT NULL,
                    status_code INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_api_endpoint ON api_performance(endpoint);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_api_timestamp ON api_performance(timestamp);
                """
            )
            conn.commit()

    def record_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "",
        tags: Optional[dict] = None,
        metric_id: Optional[str] = None,
    ) -> str:
        """Record a metric data point."""
        import uuid
        
        metric_id = metric_id or str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        import json
        tags_json = json.dumps(tags or {})

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO metrics
                (metric_id, metric_name, value, unit, tags, timestamp, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (metric_id, metric_name, value, unit, tags_json, now, now),
            )
            conn.commit()

        return metric_id

    def record_api_call(
        self,
        endpoint: str,
        method: str,
        response_time_ms: float,
        status_code: int,
        performance_id: Optional[str] = None,
    ) -> str:
        """Record API call performance."""
        import uuid
        
        performance_id = performance_id or str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO api_performance
                (performance_id, endpoint, method, response_time_ms, status_code, timestamp, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (performance_id, endpoint, method, response_time_ms, status_code, now, now),
            )
            conn.commit()

        return performance_id

    def get_metric_history(
        self,
        metric_name: str,
        hours: int = 24,
        limit: int = 1000,
    ) -> list[MetricPoint]:
        """Get metric history for specified time range."""
        start_time = datetime.now(tz=timezone.utc) - timedelta(hours=hours)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM metrics
                WHERE metric_name = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (metric_name, start_time.isoformat(), limit),
            )
            rows = cursor.fetchall()

        import json
        results = []
        for row in rows:
            results.append(
                MetricPoint(
                    timestamp=row["timestamp"],
                    metric_name=row["metric_name"],
                    value=row["value"],
                    unit=row["unit"] or "",
                    tags=json.loads(row["tags"]) if row["tags"] else {},
                )
            )

        return results

    def get_api_statistics(
        self,
        hours: int = 24,
    ) -> dict:
        """Get API performance statistics."""
        start_time = datetime.now(tz=timezone.utc) - timedelta(hours=hours)

        with sqlite3.connect(self.db_path) as conn:
            # Overall statistics
            cursor = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_requests,
                    AVG(response_time_ms) as avg_response_time,
                    MIN(response_time_ms) as min_response_time,
                    MAX(response_time_ms) as max_response_time,
                    SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count
                FROM api_performance
                WHERE timestamp >= ?
                """,
                (start_time.isoformat(),),
            )
            overall = cursor.fetchone()

            # By endpoint
            cursor = conn.execute(
                """
                SELECT 
                    endpoint,
                    method,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time,
                    MAX(response_time_ms) as max_response_time,
                    SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors
                FROM api_performance
                WHERE timestamp >= ?
                GROUP BY endpoint, method
                ORDER BY request_count DESC
                """,
                (start_time.isoformat(),),
            )
            by_endpoint = []
            for row in cursor.fetchall():
                by_endpoint.append({
                    "endpoint": row[0],
                    "method": row[1],
                    "request_count": row[2],
                    "avg_response_time_ms": round(row[3] or 0, 2),
                    "max_response_time_ms": row[4],
                    "errors": row[5],
                })

            # By status code
            cursor = conn.execute(
                """
                SELECT status_code, COUNT(*) as count
                FROM api_performance
                WHERE timestamp >= ?
                GROUP BY status_code
                ORDER BY status_code
                """,
                (start_time.isoformat(),),
            )
            by_status = {str(row[0]): row[1] for row in cursor.fetchall()}

        return {
            "period_hours": hours,
            "total_requests": overall[0],
            "avg_response_time_ms": round(overall[1] or 0, 2),
            "min_response_time_ms": overall[2],
            "max_response_time_ms": overall[3],
            "error_count": overall[4] or 0,
            "by_endpoint": by_endpoint,
            "by_status_code": by_status,
        }

    def get_slow_endpoints(
        self,
        hours: int = 24,
        threshold_ms: float = 500,
        limit: int = 20,
    ) -> list[dict]:
        """Get endpoints with slow response times."""
        start_time = datetime.now(tz=timezone.utc) - timedelta(hours=hours)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT 
                    endpoint,
                    method,
                    response_time_ms,
                    status_code,
                    timestamp
                FROM api_performance
                WHERE timestamp >= ? AND response_time_ms > ?
                ORDER BY response_time_ms DESC
                LIMIT ?
                """,
                (start_time.isoformat(), threshold_ms, limit),
            )
            rows = cursor.fetchall()

        return [
            {
                "endpoint": row["endpoint"],
                "method": row["method"],
                "response_time_ms": row["response_time_ms"],
                "status_code": row["status_code"],
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def cleanup_old_metrics(self, days: int = 30) -> int:
        """Delete metrics older than N days."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM metrics WHERE timestamp < ?",
                (cutoff.isoformat(),),
            )
            metrics_deleted = cursor.rowcount

            cursor = conn.execute(
                "DELETE FROM api_performance WHERE timestamp < ?",
                (cutoff.isoformat(),),
            )
            api_deleted = cursor.rowcount

            conn.commit()

        return metrics_deleted + api_deleted

    def get_health_summary(self) -> dict:
        """Get system health summary."""
        stats = self.get_api_statistics(hours=1)
        total = stats.get("total_requests", 0)
        errors = stats.get("error_count", 0)
        error_rate = (errors / total * 100) if total > 0 else 0

        return {
            "status": "healthy" if error_rate < 5 else "warning" if error_rate < 10 else "unhealthy",
            "error_rate_percent": round(error_rate, 2),
            "requests_past_hour": total,
            "avg_response_time_ms": stats.get("avg_response_time_ms", 0),
        }


class PerformanceTimer:
    """Context manager for timing operations."""

    def __init__(self, metrics: MetricsCollector, metric_name: str):
        self.metrics = metrics
        self.metric_name = metric_name
        self.start_time = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.time() - self.start_time) * 1000
        self.metrics.record_metric(
            metric_name=self.metric_name,
            value=elapsed_ms,
            unit="ms",
        )
