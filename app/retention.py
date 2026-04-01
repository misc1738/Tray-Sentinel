"""Data retention policies and evidence lifecycle management."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from enum import Enum

from pydantic import BaseModel


class RetentionAction(str, Enum):
    """Retention policy actions."""
    RETAIN = "RETAIN"
    ARCHIVE = "ARCHIVE"
    EXPORT = "EXPORT"
    DELETE = "DELETE"
    LEGAL_HOLD = "LEGAL_HOLD"


class RetentionPolicy(BaseModel):
    """Evidence retention policy."""
    policy_id: str
    policy_name: str
    case_type: str
    retention_years: int
    action: str
    description: Optional[str] = None
    active: bool
    created_at: str


class RetentionSchedule(BaseModel):
    """Retention schedule for evidence."""
    schedule_id: str
    evidence_id: str
    policy_id: str
    retention_deadline: str
    action_to_take: str
    status: str  # PENDING, EXECUTED, CANCELLED
    executed_at: Optional[str] = None


class RetentionManager:
    """Manage data retention policies and schedules."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_tables()

    def init_tables(self):
        """Initialize retention management tables."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                # Retention policies
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS retention_policies (
                        policy_id TEXT PRIMARY KEY,
                        policy_name TEXT NOT NULL UNIQUE,
                        case_type TEXT,
                        retention_years INTEGER NOT NULL,
                        action TEXT NOT NULL,
                        description TEXT,
                        active BOOLEAN DEFAULT 1,
                        created_at TEXT NOT NULL
                    )
                    """
                )
            except sqlite3.OperationalError:
                # Table may already exist with different structure, try to add missing columns
                try:
                    conn.execute("ALTER TABLE retention_policies ADD COLUMN active BOOLEAN DEFAULT 1")
                except:
                    pass
            
            try:
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_retention_active ON retention_policies(active);
                    """
                )
            except:
                pass

            try:
                # Retention schedules
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS retention_schedules (
                        schedule_id TEXT PRIMARY KEY,
                        evidence_id TEXT NOT NULL,
                        policy_id TEXT NOT NULL,
                        case_id TEXT,
                        retention_deadline TEXT NOT NULL,
                        action_to_take TEXT NOT NULL,
                        status TEXT DEFAULT 'PENDING',
                        scheduled_by TEXT,
                        executed_at TEXT,
                        execution_details TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(policy_id) REFERENCES retention_policies(policy_id),
                        FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
                    )
                    """
                )
            except:
                pass
            
            try:
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_schedule_status ON retention_schedules(status);
                    """
                )
            except:
                pass
            
            try:
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_schedule_deadline ON retention_schedules(retention_deadline);
                    """
                )
            except:
                pass

            # Legal holds
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS legal_holds (
                    hold_id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL,
                    case_id TEXT,
                    hold_reason TEXT,
                    requested_by TEXT NOT NULL,
                    litigation_id TEXT,
                    expires_at TEXT,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_hold_status ON legal_holds(status);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_hold_evidence ON legal_holds(evidence_id);
                """
            )

            conn.commit()

    def create_policy(
        self,
        policy_name: str,
        case_type: str,
        retention_years: int,
        action: str,
        description: Optional[str] = None,
    ) -> RetentionPolicy:
        """Create a retention policy."""
        policy_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO retention_policies
                (policy_id, policy_name, case_type, retention_years, action, description, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (policy_id, policy_name, case_type, retention_years, action, description, now),
            )
            conn.commit()

        return RetentionPolicy(
            policy_id=policy_id,
            policy_name=policy_name,
            case_type=case_type,
            retention_years=retention_years,
            action=action,
            description=description,
            active=True,
            created_at=now,
        )

    def get_policies(self, case_type: Optional[str] = None, active_only: bool = True) -> list[RetentionPolicy]:
        """Get retention policies."""
        query = "SELECT * FROM retention_policies WHERE 1=1"
        params = []

        if active_only:
            query += " AND active = 1"

        if case_type:
            query += " AND (case_type = ? OR case_type IS NULL)"
            params.append(case_type)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [
            RetentionPolicy(
                policy_id=row["policy_id"],
                policy_name=row["policy_name"],
                case_type=row["case_type"],
                retention_years=row["retention_years"],
                action=row["action"],
                description=row["description"],
                active=bool(row["active"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def schedule_retention(
        self,
        evidence_id: str,
        policy_id: str,
        case_id: Optional[str] = None,
        scheduled_by: Optional[str] = None,
    ) -> RetentionSchedule:
        """Schedule evidence for retention action."""
        schedule_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        # Get policy details
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT retention_years, action FROM retention_policies WHERE policy_id = ?",
                (policy_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Policy not found")

            retention_years, action = row
            deadline = (datetime.now(tz=timezone.utc) + timedelta(days=365 * retention_years)).isoformat()

            conn.execute(
                """
                INSERT INTO retention_schedules
                (schedule_id, evidence_id, policy_id, case_id, retention_deadline,
                 action_to_take, scheduled_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (schedule_id, evidence_id, policy_id, case_id, deadline, action, scheduled_by, now),
            )
            conn.commit()

        return RetentionSchedule(
            schedule_id=schedule_id,
            evidence_id=evidence_id,
            policy_id=policy_id,
            retention_deadline=deadline,
            action_to_take=action,
            status="PENDING",
        )

    def get_pending_actions(self) -> list[dict]:
        """Get retention actions due or overdue."""
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM retention_schedules
                WHERE status = 'PENDING' AND retention_deadline <= ?
                ORDER BY retention_deadline ASC
                """,
                (now,),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def execute_retention_action(
        self,
        schedule_id: str,
        execution_details: Optional[dict] = None,
    ) -> bool:
        """Mark retention action as executed."""
        now = datetime.now(tz=timezone.utc).isoformat()
        details_json = json.dumps(execution_details) if execution_details else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE retention_schedules
                SET status = 'EXECUTED', executed_at = ?, execution_details = ?
                WHERE schedule_id = ?
                """,
                (now, details_json, schedule_id),
            )
            conn.commit()

        return True

    def place_legal_hold(
        self,
        evidence_id: str,
        requested_by: str,
        case_id: Optional[str] = None,
        litigation_id: Optional[str] = None,
        hold_reason: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> dict:
        """Place a legal hold on evidence."""
        hold_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO legal_holds
                (hold_id, evidence_id, case_id, hold_reason, requested_by, litigation_id, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (hold_id, evidence_id, case_id, hold_reason, requested_by, litigation_id, expires_at, now),
            )
            conn.commit()

        return {
            "hold_id": hold_id,
            "evidence_id": evidence_id,
            "status": "ACTIVE",
            "created_at": now,
            "expires_at": expires_at,
        }

    def get_legal_holds(self, evidence_id: Optional[str] = None) -> list[dict]:
        """Get active legal holds."""
        query = "SELECT * FROM legal_holds WHERE status = 'ACTIVE'"
        params = []

        if evidence_id:
            query += " AND evidence_id = ?"
            params.append(evidence_id)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def release_legal_hold(self, hold_id: str) -> bool:
        """Release a legal hold."""
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE legal_holds
                SET status = 'RELEASED', expires_at = ?
                WHERE hold_id = ?
                """,
                (now, hold_id),
            )
            conn.commit()

        return True

    def get_retention_report(self) -> dict:
        """Get retention status report."""
        with sqlite3.connect(self.db_path) as conn:
            # Pending actions
            cursor = conn.execute(
                "SELECT COUNT(*) FROM retention_schedules WHERE status = 'PENDING'"
            )
            pending = cursor.fetchone()[0]

            # Evidence on legal hold
            cursor = conn.execute(
                "SELECT COUNT(DISTINCT evidence_id) FROM legal_holds WHERE status = 'ACTIVE'"
            )
            on_hold = cursor.fetchone()[0]

            # Executed actions
            cursor = conn.execute(
                "SELECT COUNT(*) FROM retention_schedules WHERE status = 'EXECUTED'"
            )
            executed = cursor.fetchone()[0]

            # Actions by type
            cursor = conn.execute(
                """
                SELECT action_to_take, COUNT(*) as count
                FROM retention_schedules
                WHERE status = 'PENDING'
                GROUP BY action_to_take
                """
            )
            by_action = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "pending_actions": pending,
            "evidence_on_hold": on_hold,
            "executed_actions": executed,
            "actions_by_type": by_action,
        }
