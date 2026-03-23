"""Advanced analytics and statistics for evidence handling."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class CaseMetrics(BaseModel):
    """Case-level metrics."""
    case_id: str
    total_evidence: int
    total_events: int
    avg_time_per_event_hours: float
    integrity_failures: int
    pending_endorsements: int
    classification_distribution: dict
    top_tags: list[str]


class AnalyticsEngine:
    """Generate analytics and statistics on evidence handling."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def get_case_metrics(self, case_id: str) -> CaseMetrics:
        """Get comprehensive metrics for a case."""
        with sqlite3.connect(self.db_path) as conn:
            # Evidence count
            cursor = conn.execute(
                "SELECT COUNT(*) FROM evidence WHERE case_id = ?",
                (case_id,),
            )
            total_evidence = cursor.fetchone()[0]

            # Event count
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM ledger
                WHERE evidence_id IN (SELECT evidence_id FROM evidence WHERE case_id = ?)
                """,
                (case_id,),
            )
            total_events = cursor.fetchone()[0]

            # Average time per event
            cursor = conn.execute(
                """
                SELECT AVG(CAST(
                    (julianday(l2.timestamp) - julianday(l1.timestamp)) * 24 AS FLOAT
                ))
                FROM ledger l1
                JOIN ledger l2 ON l1.tx_id = l2.prev_hash
                WHERE l1.evidence_id IN (SELECT evidence_id FROM evidence WHERE case_id = ?)
                """,
                (case_id,),
            )
            avg_time = cursor.fetchone()[0] or 0

            # Integrity failures
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM ledger
                WHERE evidence_id IN (SELECT evidence_id FROM evidence WHERE case_id = ?)
                AND integrity_ok = 0
                """,
                (case_id,),
            )
            integrity_failures = cursor.fetchone()[0]

            # Pending endorsements
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT tx_id) FROM ledger
                WHERE evidence_id IN (SELECT evidence_id FROM evidence WHERE case_id = ?)
                AND action_type != 'ENDORSE'
                AND endorsements IS NULL OR endorsements = '[]'
                """,
                (case_id,),
            )
            pending_endorsements = cursor.fetchone()[0]

            # Classification distribution
            cursor = conn.execute(
                """
                SELECT classification_type, COUNT(*) as count
                FROM evidence_classifications
                WHERE evidence_id IN (SELECT evidence_id FROM evidence WHERE case_id = ?)
                GROUP BY classification_type
                """,
                (case_id,),
            )
            classifications = {row[0]: row[1] for row in cursor.fetchall()}

            # Top tags
            cursor = conn.execute(
                """
                SELECT tag_name FROM evidence_tags
                WHERE evidence_id IN (SELECT evidence_id FROM evidence WHERE case_id = ?)
                GROUP BY tag_name
                ORDER BY COUNT(*) DESC
                LIMIT 10
                """,
                (case_id,),
            )
            top_tags = [row[0] for row in cursor.fetchall()]

        return CaseMetrics(
            case_id=case_id,
            total_evidence=total_evidence,
            total_events=total_events,
            avg_time_per_event_hours=round(avg_time, 2),
            integrity_failures=integrity_failures,
            pending_endorsements=pending_endorsements,
            classification_distribution=classifications,
            top_tags=top_tags,
        )

    def get_organization_statistics(self, org_id: str) -> dict:
        """Get statistics for an organization."""
        with sqlite3.connect(self.db_path) as conn:
            # Cases handled
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT case_id) FROM evidence
                WHERE evidence_id IN (
                    SELECT DISTINCT evidence_id FROM ledger WHERE actor_org_id = ?
                )
                """,
                (org_id,),
            )
            cases_handled = cursor.fetchone()[0]

            # Evidence processed
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM ledger
                WHERE actor_org_id = ? AND action_type = 'INTAKE'
                """,
                (org_id,),
            )
            evidence_processed = cursor.fetchone()[0]

            # Actions performed
            cursor = conn.execute(
                """
                SELECT action_type, COUNT(*) as count
                FROM ledger
                WHERE actor_org_id = ?
                GROUP BY action_type
                ORDER BY count DESC
                """,
                (org_id,),
            )
            actions = {row[0]: row[1] for row in cursor.fetchall()}

            # Endorsements given
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM ledger
                WHERE actor_org_id = ? AND action_type = 'ENDORSE'
                """,
                (org_id,),
            )
            endorsements = cursor.fetchone()[0]

            # Average processing time
            cursor = conn.execute(
                """
                SELECT AVG(CAST(
                    (julianday(completed_at) - julianday(requested_at)) * 24 AS FLOAT
                ))
                FROM workflow_actions
                WHERE requested_org_id = ? AND resolved_at IS NOT NULL
                """,
                (org_id,),
            )
            avg_time = cursor.fetchone()[0] or 0

        return {
            "org_id": org_id,
            "cases_handled": cases_handled,
            "evidence_processed": evidence_processed,
            "actions_by_type": actions,
            "endorsements_given": endorsements,
            "avg_processing_time_hours": round(avg_time, 2),
        }

    def get_temporal_statistics(self, days: int = 30) -> dict:
        """Get statistics over a time period."""
        start_time = datetime.now(tz=timezone.utc) - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            # Daily events
            cursor = conn.execute(
                """
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM ledger
                WHERE timestamp >= ?
                GROUP BY DATE(timestamp)
                ORDER BY date ASC
                """,
                (start_time.isoformat(),),
            )
            daily_events = {row[0]: row[1] for row in cursor.fetchall()}

            # New cases
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT case_id) FROM evidence
                WHERE created_at >= ?
                """,
                (start_time.isoformat(),),
            )
            new_cases = cursor.fetchone()[0]

            # New evidence
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM evidence WHERE created_at >= ?
                """,
                (start_time.isoformat(),),
            )
            new_evidence = cursor.fetchone()[0]

            # Event rate
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM ledger WHERE timestamp >= ?
                """,
                (start_time.isoformat(),),
            )
            total_events = cursor.fetchone()[0]
            event_rate = total_events / days if days > 0 else 0

        return {
            "period_days": days,
            "new_cases": new_cases,
            "new_evidence": new_evidence,
            "total_events": total_events,
            "event_rate_per_day": round(event_rate, 2),
            "daily_breakdown": daily_events,
        }

    def get_compliance_metrics(self) -> dict:
        """Get system-wide compliance metrics."""
        with sqlite3.connect(self.db_path) as conn:
            # Evidence with complete classifications
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM evidence
                WHERE evidence_id IN (
                    SELECT evidence_id FROM evidence_classifications
                )
                """
            )
            classified_count = cursor.fetchone()[0]

            total_cursor = conn.execute("SELECT COUNT(*) FROM evidence")
            total_count = total_cursor.fetchone()[0]

            # Evidence with tags
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT evidence_id) FROM evidence_tags
                """
            )
            tagged_count = cursor.fetchone()[0]

            # Verified evidence
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT evidence_id) FROM ledger
                WHERE action_type = 'ACCESS' AND integrity_ok = 1
                """
            )
            verified_count = cursor.fetchone()[0]

            # Chain integrity
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM ledger
                WHERE integrity_ok = 0
                """
            )
            chain_failures = cursor.fetchone()[0]

            # Endorsement coverage
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT evidence_id) FROM ledger
                WHERE action_type IN ('TRANSFER', 'COURT_SUBMISSION')
                AND endorsements IS NOT NULL AND endorsements != '[]'
                """
            )
            endorsed_count = cursor.fetchone()[0]

        return {
            "classification_coverage_percent": (classified_count / total_count * 100) if total_count > 0 else 0,
            "tagging_coverage_percent": (tagged_count / total_count * 100) if total_count > 0 else 0,
            "verification_coverage_percent": (verified_count / total_count * 100) if total_count > 0 else 0,
            "chain_integrity_percent": ((total_count - chain_failures) / total_count * 100) if total_count > 0 else 0,
            "endorsement_coverage_percent": (endorsed_count / total_count * 100) if total_count > 0 else 0,
        }

    def get_performance_statistics(self) -> dict:
        """Get system performance metrics."""
        with sqlite3.connect(self.db_path) as conn:
            # Average event processing time
            cursor = conn.execute(
                """
                SELECT AVG(CAST(
                    (julianday(l2.timestamp) - julianday(l1.timestamp)) * 24 * 60 AS FLOAT
                ))
                FROM ledger l1
                JOIN ledger l2 ON l1.tx_id = l2.prev_hash
                """
            )
            avg_event_time = cursor.fetchone()[0] or 0

            # Evidence intake rate
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM ledger
                WHERE action_type = 'INTAKE'
                AND timestamp >= datetime('now', '-7 days')
                """
            )
            week_intakes = cursor.fetchone()[0]

            # Storage efficiency
            cursor = conn.execute(
                """
                SELECT COUNT(*), SUM(LENGTH(evidence_id)) FROM evidence
                """
            )
            count, size = cursor.fetchone()

            return {
                "avg_event_processing_minutes": round(avg_event_time, 2),
                "intake_rate_per_week": week_intakes,
                "avg_metadata_per_evidence_bytes": round(size / count, 0) if count > 0 else 0,
            }

    def get_system_health_score(self) -> float:
        """Calculate overall system health score (0-100)."""
        compliance = self.get_compliance_metrics()
        
        score = (
            compliance["classification_coverage_percent"] * 0.2 +
            compliance["verification_coverage_percent"] * 0.2 +
            compliance["chain_integrity_percent"] * 0.3 +
            compliance["endorsement_coverage_percent"] * 0.2 +
            compliance["tagging_coverage_percent"] * 0.1
        )
        
        return round(score, 1)

    def get_anomalies(self, days: int = 7) -> list[dict]:
        """Detect system anomalies."""
        start_time = datetime.now(tz=timezone.utc) - timedelta(days=days)
        anomalies = []

        with sqlite3.connect(self.db_path) as conn:
            # High failure rate
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM batch_results
                WHERE created_at >= ? AND status = 'FAILURE'
                """
            )
            failures = cursor.fetchone()[0]
            if failures > 10:
                anomalies.append({
                    "type": "high_batch_failures",
                    "severity": "warning",
                    "count": failures,
                })

            # Unresolved approvals
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM workflow_actions
                WHERE status = 'PENDING' AND requested_at < datetime('now', '-2 days')
                """
            )
            stale = cursor.fetchone()[0]
            if stale > 5:
                anomalies.append({
                    "type": "stale_approvals",
                    "severity": "warning",
                    "count": stale,
                })

            # Chain integrity issues
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM ledger
                WHERE integrity_ok = 0 AND timestamp >= ?
                """,
                (start_time.isoformat(),),
            )
            integrity = cursor.fetchone()[0]
            if integrity > 0:
                anomalies.append({
                    "type": "chain_integrity_failure",
                    "severity": "critical",
                    "count": integrity,
                })

        return anomalies
