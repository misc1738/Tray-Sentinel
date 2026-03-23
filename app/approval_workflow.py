"""Approval workflows for multi-step authorization."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from enum import Enum

from pydantic import BaseModel


class ApprovalStatus(str, Enum):
    """Workflow approval status."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class WorkflowAction(BaseModel):
    """Workflow action request."""
    action_id: str
    workflow_id: str
    action_type: str
    resource_id: str
    requested_by: str
    status: str
    approvals_required: int
    approvals_received: int
    requested_at: str
    resolved_at: Optional[str] = None


class ApprovalStep(BaseModel):
    """Single approval step."""
    approval_id: str
    action_id: str
    approver_user_id: str
    approver_org_id: str
    status: str
    comment: Optional[str] = None
    approved_at: Optional[str] = None


class ApprovalWorkflow:
    """Manage multi-step approval workflows."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_tables()

    def init_tables(self):
        """Initialize workflow approval tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Workflow definitions
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_templates (
                    template_id TEXT PRIMARY KEY,
                    template_name TEXT NOT NULL UNIQUE,
                    action_type TEXT NOT NULL,
                    approvals_required INTEGER DEFAULT 1,
                    approver_roles TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_action ON workflow_templates(action_type);
                """
            )

            # Workflow instances
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_actions (
                    action_id TEXT PRIMARY KEY,
                    workflow_id TEXT,
                    template_id TEXT,
                    action_type TEXT NOT NULL,
                    resource_type TEXT,
                    resource_id TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    requested_org_id TEXT,
                    request_data TEXT,
                    status TEXT DEFAULT 'PENDING',
                    approvals_required INTEGER DEFAULT 1,
                    approvals_received INTEGER DEFAULT 0,
                    requested_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolution_reason TEXT,
                    FOREIGN KEY(template_id) REFERENCES workflow_templates(template_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_status ON workflow_actions(status);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_resource ON workflow_actions(resource_type, resource_id);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_requested ON workflow_actions(requested_at);
                """
            )

            # Individual approvals
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    action_id TEXT NOT NULL,
                    approver_user_id TEXT NOT NULL,
                    approver_org_id TEXT,
                    status TEXT NOT NULL,
                    comment TEXT,
                    approved_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(action_id) REFERENCES workflow_actions(action_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_approvals_action ON approvals(action_id);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_approvals_approver ON approvals(approver_user_id);
                """
            )

            conn.commit()

    def create_template(
        self,
        template_name: str,
        action_type: str,
        approvals_required: int = 1,
        approver_roles: list[str] = None,
    ) -> dict:
        """Create a workflow template."""
        template_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        roles_json = json.dumps(approver_roles or [])

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO workflow_templates
                (template_id, template_name, action_type, approvals_required, approver_roles, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (template_id, template_name, action_type, approvals_required, roles_json, now),
            )
            conn.commit()

        return {
            "template_id": template_id,
            "template_name": template_name,
            "action_type": action_type,
            "approvals_required": approvals_required,
            "approver_roles": approver_roles or [],
            "created_at": now,
        }

    def get_templates(self, action_type: Optional[str] = None) -> list[dict]:
        """Get workflow templates."""
        query = "SELECT * FROM workflow_templates WHERE 1=1"
        params = []

        if action_type:
            query += " AND action_type = ?"
            params.append(action_type)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        results = []
        for row in rows:
            result = dict(row)
            result["approver_roles"] = json.loads(result["approver_roles"])
            results.append(result)

        return results

    def request_approval(
        self,
        action_type: str,
        resource_type: str,
        resource_id: str,
        requested_by: str,
        requested_org_id: str,
        request_data: Optional[dict] = None,
        template_id: Optional[str] = None,
    ) -> WorkflowAction:
        """Create approval request."""
        action_id = str(uuid.uuid4())
        workflow_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        request_json = json.dumps(request_data or {})

        # If no template, use defaults
        approvals_required = 1
        if template_id:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT approvals_required FROM workflow_templates WHERE template_id = ?",
                    (template_id,),
                )
                row = cursor.fetchone()
                if row:
                    approvals_required = row[0]

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO workflow_actions
                (action_id, workflow_id, template_id, action_type, resource_type, resource_id,
                 requested_by, requested_org_id, request_data, status, approvals_required, requested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (action_id, workflow_id, template_id, action_type, resource_type, resource_id,
                 requested_by, requested_org_id, request_json, approvals_required, now),
            )
            conn.commit()

        return WorkflowAction(
            action_id=action_id,
            workflow_id=workflow_id,
            action_type=action_type,
            resource_id=resource_id,
            requested_by=requested_by,
            status="PENDING",
            approvals_required=approvals_required,
            approvals_received=0,
            requested_at=now,
        )

    def get_pending_actions(self, approver_user_id: Optional[str] = None) -> list[dict]:
        """Get pending approval actions."""
        query = "SELECT * FROM workflow_actions WHERE status = 'PENDING'"
        params = []

        if approver_user_id:
            query += """
                AND action_id IN (
                    SELECT action_id FROM approvals
                    WHERE approver_user_id = ? AND status = 'PENDING'
                )
            """
            params.append(approver_user_id)

        query += " ORDER BY requested_at ASC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        results = []
        for row in rows:
            result = dict(row)
            result["request_data"] = json.loads(result["request_data"]) if result["request_data"] else {}
            results.append(result)

        return results

    def submit_approval(
        self,
        action_id: str,
        approver_user_id: str,
        approver_org_id: str,
        approved: bool,
        comment: Optional[str] = None,
    ) -> ApprovalStep:
        """Submit approval decision."""
        approval_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        status = "APPROVED" if approved else "REJECTED"
        approved_at = now if approved else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO approvals
                (approval_id, action_id, approver_user_id, approver_org_id, status, comment, approved_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (approval_id, action_id, approver_user_id, approver_org_id, status, comment, approved_at, now),
            )

            # Update action if approved
            if approved:
                cursor = conn.execute(
                    """
                    UPDATE workflow_actions
                    SET approvals_received = approvals_received + 1
                    WHERE action_id = ?
                    """,
                    (action_id,),
                )

                # Check if all approvals completed
                cursor = conn.execute(
                    "SELECT approvals_required, approvals_received FROM workflow_actions WHERE action_id = ?",
                    (action_id,),
                )
                row = cursor.fetchone()
                if row and row[1] >= row[0]:
                    conn.execute(
                        """
                        UPDATE workflow_actions
                        SET status = 'APPROVED', resolved_at = ?
                        WHERE action_id = ?
                        """,
                        (now, action_id),
                    )
            else:
                # Reject entire workflow
                conn.execute(
                    """
                    UPDATE workflow_actions
                    SET status = 'REJECTED', resolved_at = ?, resolution_reason = ?
                    WHERE action_id = ?
                    """,
                    (now, comment, action_id),
                )

            conn.commit()

        return ApprovalStep(
            approval_id=approval_id,
            action_id=action_id,
            approver_user_id=approver_user_id,
            approver_org_id=approver_org_id,
            status=status,
            comment=comment,
            approved_at=approved_at,
        )

    def get_action_approvals(self, action_id: str) -> list[ApprovalStep]:
        """Get all approvals for an action."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM approvals WHERE action_id = ? ORDER BY created_at ASC",
                (action_id,),
            )
            rows = cursor.fetchall()

        return [
            ApprovalStep(
                approval_id=row["approval_id"],
                action_id=row["action_id"],
                approver_user_id=row["approver_user_id"],
                approver_org_id=row["approver_org_id"],
                status=row["status"],
                comment=row["comment"],
                approved_at=row["approved_at"],
            )
            for row in rows
        ]

    def get_workflow_history(self, resource_id: str, resource_type: Optional[str] = None) -> list[dict]:
        """Get workflow history for a resource."""
        query = """
            SELECT * FROM workflow_actions
            WHERE resource_id = ?
        """
        params = [resource_id]

        if resource_type:
            query += " AND resource_type = ?"
            params.append(resource_type)

        query += " ORDER BY requested_at DESC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        results = []
        for row in rows:
            result = dict(row)
            result["request_data"] = json.loads(result["request_data"]) if result["request_data"] else {}
            results.append(result)

        return results

    def get_approval_statistics(self) -> dict:
        """Get approval workflow statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Count by status
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM workflow_actions
                GROUP BY status
                """
            )
            status_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # Average approval time
            cursor = conn.execute(
                """
                SELECT AVG(CAST(
                    (julianday(resolved_at) - julianday(requested_at)) * 24 AS FLOAT
                )) as avg_hours
                FROM workflow_actions
                WHERE resolved_at IS NOT NULL
                """
            )
            avg_hours = cursor.fetchone()[0] or 0

            # Approval rate
            cursor = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END) as approved,
                    COUNT(*) as total
                FROM workflow_actions
                WHERE resolved_at IS NOT NULL
                """
            )
            approved, total = cursor.fetchone()
            approval_rate = (approved / total * 100) if total > 0 else 0

        return {
            "status_counts": status_counts,
            "avg_approval_time_hours": round(avg_hours, 2),
            "approval_rate_percent": round(approval_rate, 2),
        }
