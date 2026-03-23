"""Advanced audit logging with query and filtering capabilities."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from enum import Enum

from pydantic import BaseModel


class AuditEventType(str, Enum):
    """Types of auditableevents."""
    EVIDENCE_INTAKE = "EVIDENCE_INTAKE"
    CUSTODY_ACTION = "CUSTODY_ACTION"
    ENDORSEMENT = "ENDORSEMENT"
    VERIFICATION = "VERIFICATION"
    REPORT_GENERATION = "REPORT_GENERATION"
    ACCESS_CONTROL = "ACCESS_CONTROL"
    SYSTEM_CONFIG = "SYSTEM_CONFIG"
    COMPLIANCE_ASSESSMENT = "COMPLIANCE_ASSESSMENT"
    SECURITY_INCIDENT = "SECURITY_INCIDENT"


class AuditLogEntry(BaseModel):
    """Audit log entry model."""
    audit_id: str
    event_type: str
    actor_user_id: str
    actor_org_id: str
    resource_type: str
    resource_id: str
    action: str
    details: dict
    status: str  # SUCCESS, FAILURE, PARTIAL
    timestamp: str
    ip_address: Optional[str] = None
    session_id: Optional[str] = None


class AuditLogger:
    """Advanced audit logging system."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_table()

    def init_table(self):
        """Initialize audit logging tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    audit_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    actor_user_id TEXT NOT NULL,
                    actor_org_id TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    ip_address TEXT,
                    session_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_user_id, actor_org_id);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource_type, resource_id);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_logs(status);
                """
            )
            conn.commit()

    def log_event(
        self,
        audit_id: str,
        event_type: str,
        actor_user_id: str,
        actor_org_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        details: dict = None,
        status: str = "SUCCESS",
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Log an audit event."""
        if details is None:
            details = {}

        now = datetime.now(tz=timezone.utc).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    audit_id, event_type, actor_user_id, actor_org_id,
                    resource_type, resource_id, action, details, status,
                    timestamp, ip_address, session_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    event_type,
                    actor_user_id,
                    actor_org_id,
                    resource_type,
                    resource_id,
                    action,
                    json.dumps(details),
                    status,
                    now,
                    ip_address,
                    session_id,
                    now,
                ),
            )
            conn.commit()

    def query_logs(
        self,
        event_type: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        actor_org_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Query audit logs with flexible filtering."""
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        
        if actor_user_id:
            query += " AND actor_user_id = ?"
            params.append(actor_user_id)
        
        if actor_org_id:
            query += " AND actor_org_id = ?"
            params.append(actor_org_id)
        
        if resource_type:
            query += " AND resource_type = ?"
            params.append(resource_type)
        
        if resource_id:
            query += " AND resource_id = ?"
            params.append(resource_id)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        results = []
        for row in rows:
            entry = dict(row)
            if entry.get("details"):
                entry["details"] = json.loads(entry["details"])
            results.append(entry)

        return results

    def get_actor_activity(
        self,
        actor_user_id: str,
        actor_org_id: Optional[str] = None,
        days: int = 30,
        limit: int = 50,
    ) -> list[dict]:
        """Get activity log for a specific actor."""
        start_time = datetime.now(tz=timezone.utc) - timedelta(days=days)
        return self.query_logs(
            actor_user_id=actor_user_id,
            actor_org_id=actor_org_id,
            start_time=start_time,
            limit=limit,
        )

    def get_resource_audit_trail(
        self,
        resource_type: str,
        resource_id: str,
    ) -> list[dict]:
        """Get complete audit trail for a resource."""
        return self.query_logs(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=10000,  # Get all events for this resource
        )

    def get_failed_actions(
        self,
        days: int = 7,
        limit: int = 100,
    ) -> list[dict]:
        """Get all failed or partial actions in the past N days."""
        start_time = datetime.now(tz=timezone.utc) - timedelta(days=days)
        query = """
            SELECT * FROM audit_logs
            WHERE (status = 'FAILURE' OR status = 'PARTIAL')
            AND timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, (start_time.isoformat(), limit))
            rows = cursor.fetchall()

        results = []
        for row in rows:
            entry = dict(row)
            if entry.get("details"):
                entry["details"] = json.loads(entry["details"])
            results.append(entry)

        return results

    def get_compliance_report(
        self,
        days: int = 30,
    ) -> dict:
        """Generate compliance report from audit logs."""
        start_time = datetime.now(tz=timezone.utc) - timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            # Count events by type
            cursor = conn.execute(
                """
                SELECT event_type, COUNT(*) as count, 
                       SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successes,
                       SUM(CASE WHEN status = 'FAILURE' THEN 1 ELSE 0 END) as failures,
                       SUM(CASE WHEN status = 'PARTIAL' THEN 1 ELSE 0 END) as partials
                FROM audit_logs
                WHERE timestamp >= ?
                GROUP BY event_type
                """,
                (start_time.isoformat(),),
            )
            event_summary = {row[0]: {"total": row[1], "success": row[2], "failure": row[3], "partial": row[4]} 
                           for row in cursor.fetchall()}

            # Count actions by actor org
            cursor = conn.execute(
                """
                SELECT actor_org_id, COUNT(*) as action_count
                FROM audit_logs
                WHERE timestamp >= ?
                GROUP BY actor_org_id
                ORDER BY action_count DESC
                """,
                (start_time.isoformat(),),
            )
            org_activity = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "period_days": days,
            "start_time": start_time.isoformat(),
            "event_summary": event_summary,
            "org_activity": org_activity,
        }
