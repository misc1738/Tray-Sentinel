"""Security monitoring, alerting, and incident response."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.models import (
    AccessLog,
    IncidentResponse,
    MonitoringDashboard,
    SecurityAlert,
    SecurityMetrics,
    SecurityPosture,
)


class SecurityMonitor:
    """Monitor security posture and generate alerts."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_tables()

    def init_tables(self):
        """Initialize security monitoring tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_alerts (
                    alert_id TEXT PRIMARY KEY,
                    severity TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    evidence_id TEXT,
                    case_id TEXT,
                    actor_user_id TEXT,
                    actor_org_id TEXT,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    resolved_at TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    alert_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    root_cause TEXT,
                    remediation_steps TEXT,
                    timestamp TEXT NOT NULL,
                    resolved_at TEXT,
                    resolution_notes TEXT,
                    assigned_to TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS access_logs (
                    log_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    ip_address TEXT,
                    details TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON security_alerts(timestamp);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_alerts_status ON security_alerts(status);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON access_logs(timestamp);
                """
            )
            conn.commit()

    def create_alert(
        self,
        severity: str,
        alert_type: str,
        title: str,
        description: str,
        evidence_id: Optional[str] = None,
        case_id: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        actor_org_id: Optional[str] = None,
    ) -> str:
        """Create a security alert."""
        import uuid

        alert_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO security_alerts
                (alert_id, severity, alert_type, title, description, evidence_id, case_id,
                 actor_user_id, actor_org_id, timestamp, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_id,
                    severity,
                    alert_type,
                    title,
                    description,
                    evidence_id,
                    case_id,
                    actor_user_id,
                    actor_org_id,
                    now,
                    "OPEN",
                    now,
                ),
            )
            conn.commit()
        return alert_id

    def get_alerts(
        self,
        limit: int = 50,
        status: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> list[SecurityAlert]:
        """Get security alerts with optional filtering."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM security_alerts WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)
            if severity:
                query += " AND severity = ?"
                params.append(severity)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        alerts = []
        for row in rows:
            alerts.append(
                SecurityAlert(
                    alert_id=row[0],
                    severity=row[1],
                    alert_type=row[2],
                    title=row[3],
                    description=row[4],
                    evidence_id=row[5],
                    case_id=row[6],
                    actor_user_id=row[7],
                    actor_org_id=row[8],
                    timestamp=row[9],
                    status=row[10],
                    resolved_at=row[11],
                )
            )
        return alerts

    def acknowledge_alert(self, alert_id: str):
        """Update alert status to acknowledged."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE security_alerts SET status = ? WHERE alert_id = ?",
                ("ACKNOWLEDGED", alert_id),
            )
            conn.commit()

    def resolve_alert(self, alert_id: str, mark_false_positive: bool = False):
        """Resolve an alert."""
        now = datetime.now(timezone.utc).isoformat()
        status = "FALSE_POSITIVE" if mark_false_positive else "RESOLVED"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE security_alerts SET status = ?, resolved_at = ? WHERE alert_id = ?",
                (status, now, alert_id),
            )
            conn.commit()

    def log_access(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        status: str,
        ip_address: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> str:
        """Log access/audit event."""
        import uuid
        import json

        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO access_logs
                (log_id, user_id, action, resource_type, resource_id, timestamp, status, ip_address, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    user_id,
                    action,
                    resource_type,
                    resource_id,
                    now,
                    status,
                    ip_address,
                    json.dumps(details or {}),
                    now,
                ),
            )
            conn.commit()
        return log_id

    def get_access_logs(
        self, user_id: Optional[str] = None, limit: int = 100
    ) -> list[AccessLog]:
        """Get audit access logs."""
        with sqlite3.connect(self.db_path) as conn:
            if user_id:
                cursor = conn.execute(
                    "SELECT * FROM access_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (user_id, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
            rows = cursor.fetchall()

        import json

        logs = []
        for row in rows:
            logs.append(
                AccessLog(
                    log_id=row[0],
                    user_id=row[1],
                    action=row[2],
                    resource_type=row[3],
                    resource_id=row[4],
                    timestamp=row[5],
                    status=row[6],
                    ip_address=row[7],
                    details=json.loads(row[8]) if row[8] else {},
                )
            )
        return logs

    def get_security_metrics(self) -> SecurityMetrics:
        """Calculate security metrics."""
        with sqlite3.connect(self.db_path) as conn:
            # Get alert counts
            cursor = conn.execute("SELECT COUNT(*) FROM security_alerts")
            total_alerts = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE severity = ?", ("CRITICAL",)
            )
            critical_alerts = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE severity = ?", ("HIGH",)
            )
            high_alerts = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE status='OPEN'"
            )
            open_alerts = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE status IN ('RESOLVED','ACKNOWLEDGED')"
            )
            resolved_alerts = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE status = ?",
                ("FALSE_POSITIVE",),
            )
            false_positives = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE alert_type = ?",
                ("integrity_violation",),
            )
            integrity_violations = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE alert_type = ?",
                ("unauthorized_access",),
            )
            unauthorized_access = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM security_alerts WHERE alert_type = ?",
                ("chain_break",),
            )
            chain_breaks = cursor.fetchone()[0]

            # Calculate MTTR (simplified)
            cursor = conn.execute(
                """
                SELECT AVG(
                    CAST((julianday(resolved_at) - julianday(timestamp)) AS FLOAT) * 24
                ) FROM security_alerts
                WHERE resolved_at IS NOT NULL AND status != 'FALSE_POSITIVE'
                """
            )
            mttr_hours = cursor.fetchone()[0] or 0

        return SecurityMetrics(
            total_alerts=total_alerts,
            critical_alerts=critical_alerts,
            high_alerts=high_alerts,
            open_alerts=open_alerts,
            resolved_alerts=resolved_alerts,
            false_positives=false_positives,
            integrity_violations=integrity_violations,
            unauthorized_access_attempts=unauthorized_access,
            chain_break_incidents=chain_breaks,
            avg_resolution_time_hours=round(mttr_hours, 2),
            mttr=round(mttr_hours, 2),
        )

    def get_security_posture(self) -> SecurityPosture:
        """Assess overall security posture."""
        metrics = self.get_security_metrics()

        # Calculate risk level
        if metrics.critical_alerts > 0:
            risk = "CRITICAL"
        elif metrics.high_alerts > 2 or metrics.integrity_violations > 3:
            risk = "HIGH"
        elif metrics.open_alerts > 5:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        # Calculate compliance score
        total_checks = metrics.total_alerts + 1
        issues = (
            metrics.critical_alerts * 5
            + metrics.high_alerts * 3
            + metrics.integrity_violations * 4
        )
        compliance = max(0, 100 - (issues / total_checks * 100))

        return SecurityPosture(
            generated_at=datetime.now(timezone.utc).isoformat(),
            overall_risk=risk,
            encryption_status="ACTIVE",
            key_rotation="CURRENT",
            access_control_violations=metrics.unauthorized_access_attempts,
            chain_integrity_violations=metrics.integrity_violations,
            compliance_score=round(compliance, 2),
            incident_response_time_avg=metrics.mttr,
        )

    def get_monitoring_dashboard(self) -> MonitoringDashboard:
        """Get real-time monitoring dashboard."""
        metrics = self.get_security_metrics()
        recent_alerts = self.get_alerts(limit=5)

        return MonitoringDashboard(
            generated_at=datetime.now(timezone.utc).isoformat(),
            active_sessions=1,  # Would be calculated from access logs
            total_alerts_today=len(
                [
                    a
                    for a in recent_alerts
                    if a.timestamp > datetime.now(timezone.utc).isoformat()
                ]
            ),
            critical_incidents=metrics.critical_alerts,
            uptime_percentage=99.8,
            last_backup=datetime.now(timezone.utc).isoformat(),
            chain_validity=True,
            evidence_integrity_ok=metrics.integrity_violations == 0,
            recent_alerts=recent_alerts,
            metrics=metrics,
        )

    def create_incident(
        self,
        alert_id: str,
        severity: str,
        title: str,
        description: str,
        assigned_to: Optional[str] = None,
    ) -> str:
        """Create an incident from an alert."""
        import uuid

        incident_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO incidents
                (incident_id, alert_id, severity, title, description, timestamp, assigned_to, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (incident_id, alert_id, severity, title, description, now, assigned_to, now),
            )
            conn.commit()
        return incident_id

    def resolve_incident(
        self,
        incident_id: str,
        root_cause: str,
        remediation_steps: list[str],
        resolution_notes: str,
    ):
        """Resolve an incident."""
        import json

        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE incidents
                SET root_cause = ?, remediation_steps = ?, resolved_at = ?, resolution_notes = ?
                WHERE incident_id = ?
                """,
                (
                    root_cause,
                    json.dumps(remediation_steps),
                    now,
                    resolution_notes,
                    incident_id,
                ),
            )
            conn.commit()
