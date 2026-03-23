"""Batch operations for bulk evidence processing."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from enum import Enum

from pydantic import BaseModel


class BatchOperationType(str, Enum):
    """Types of batch operations."""
    CLASSIFY = "CLASSIFY"
    TAG = "TAG"
    UPDATE_STATUS = "UPDATE_STATUS"
    TRANSFER = "TRANSFER"
    VERIFY = "VERIFY"
    EXPORT = "EXPORT"
    DELETE_METADATA = "DELETE_METADATA"
    APPLY_RETENTION = "APPLY_RETENTION"


class BatchJob(BaseModel):
    """Batch operation job."""
    job_id: str
    operation_type: str
    evidence_ids: list[str]
    operation_params: dict
    status: str  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    created_by: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    results_summary: Optional[dict] = None
    error_message: Optional[str] = None


class BatchProcessor:
    """Handle batch operations on multiple evidence items."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_tables()

    def init_tables(self):
        """Initialize batch operation tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Batch jobs table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_jobs (
                    job_id TEXT PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    evidence_ids TEXT NOT NULL,
                    operation_params TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    results_summary TEXT,
                    error_message TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_batch_status ON batch_jobs(status);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_batch_created ON batch_jobs(created_at);
                """
            )

            # Batch operation results
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_results (
                    result_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    operation_result TEXT,
                    status TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES batch_jobs(job_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_batch_results_job ON batch_results(job_id);
                """
            )

            conn.commit()

    def create_batch_job(
        self,
        operation_type: str,
        evidence_ids: list[str],
        operation_params: dict,
        created_by: str,
    ) -> BatchJob:
        """Create a new batch job."""
        job_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        evidence_ids_json = json.dumps(evidence_ids)
        params_json = json.dumps(operation_params)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO batch_jobs
                (job_id, operation_type, evidence_ids, operation_params, status, created_by, created_at)
                VALUES (?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (job_id, operation_type, evidence_ids_json, params_json, created_by, now),
            )
            conn.commit()

        return BatchJob(
            job_id=job_id,
            operation_type=operation_type,
            evidence_ids=evidence_ids,
            operation_params=operation_params,
            status="PENDING",
            created_by=created_by,
            created_at=now,
        )

    def get_job(self, job_id: str) -> Optional[dict]:
        """Get batch job details."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM batch_jobs WHERE job_id = ?",
                (job_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        result = dict(row)
        result["evidence_ids"] = json.loads(result["evidence_ids"])
        result["operation_params"] = json.loads(result["operation_params"])
        if result["results_summary"]:
            result["results_summary"] = json.loads(result["results_summary"])

        return result

    def list_jobs(
        self,
        status: Optional[str] = None,
        operation_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List batch jobs with optional filtering."""
        query = "SELECT * FROM batch_jobs WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if operation_type:
            query += " AND operation_type = ?"
            params.append(operation_type)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        results = []
        for row in rows:
            result = dict(row)
            result["evidence_ids"] = json.loads(result["evidence_ids"])
            result["operation_params"] = json.loads(result["operation_params"])
            if result["results_summary"]:
                result["results_summary"] = json.loads(result["results_summary"])
            results.append(result)

        return results

    def update_job_status(
        self,
        job_id: str,
        status: str,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        results_summary: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update batch job status."""
        now = datetime.now(tz=timezone.utc).isoformat()
        started_at = started_at or now
        results_json = json.dumps(results_summary) if results_summary else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE batch_jobs
                SET status = ?, started_at = ?, completed_at = ?, results_summary = ?, error_message = ?
                WHERE job_id = ?
                """,
                (status, started_at, completed_at, results_json, error_message, job_id),
            )
            conn.commit()

        return True

    def record_result(
        self,
        job_id: str,
        evidence_id: str,
        operation_result: Optional[dict] = None,
        status: str = "SUCCESS",
        error_message: Optional[str] = None,
    ) -> str:
        """Record individual operation result in batch job."""
        result_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        result_json = json.dumps(operation_result) if operation_result else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO batch_results
                (result_id, job_id, evidence_id, operation_result, status, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (result_id, job_id, evidence_id, result_json, status, error_message, now),
            )
            conn.commit()

        return result_id

    def get_job_results(self, job_id: str) -> list[dict]:
        """Get all results for a batch job."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM batch_results
                WHERE job_id = ?
                ORDER BY created_at ASC
                """,
                (job_id,),
            )
            rows = cursor.fetchall()

        results = []
        for row in rows:
            result = dict(row)
            if result["operation_result"]:
                result["operation_result"] = json.loads(result["operation_result"])
            results.append(result)

        return results

    def get_job_summary(self, job_id: str) -> dict:
        """Get summary statistics for a batch job."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM batch_results
                WHERE job_id = ?
                GROUP BY status
                """,
                (job_id,),
            )
            summary = {row[0]: row[1] for row in cursor.fetchall()}

        total = sum(summary.values())
        return {
            "total_items": total,
            "successful": summary.get("SUCCESS", 0),
            "failed": summary.get("FAILURE", 0),
            "partial": summary.get("PARTIAL", 0),
            "success_rate": (summary.get("SUCCESS", 0) / total * 100) if total > 0 else 0,
        }

    def get_failed_items(self, job_id: str) -> list[dict]:
        """Get all failed items in a batch job."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM batch_results
                WHERE job_id = ? AND (status = 'FAILURE' OR status = 'PARTIAL')
                ORDER BY created_at DESC
                """,
                (job_id,),
            )
            rows = cursor.fetchall()

        results = []
        for row in rows:
            result = dict(row)
            if result["operation_result"]:
                result["operation_result"] = json.loads(result["operation_result"])
            results.append(result)

        return results

    def get_active_jobs(self) -> list[dict]:
        """Get all in-progress jobs."""
        return self.list_jobs(status="IN_PROGRESS")

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """Delete completed jobs older than N days."""
        from datetime import timedelta

        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM batch_jobs
                WHERE status IN ('COMPLETED', 'FAILED') AND completed_at < ?
                """,
                (cutoff,),
            )
            deleted = cursor.rowcount

            # Cascade delete results
            conn.execute(
                """
                DELETE FROM batch_results
                WHERE job_id NOT IN (SELECT job_id FROM batch_jobs)
                """
            )
            conn.commit()

        return deleted
