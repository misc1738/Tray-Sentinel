"""Compliance framework tracking and management."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.models import (
    ComplianceControl,
    ComplianceDashboard,
    ComplianceFramework,
    ComplianceStatus,
)


FRAMEWORKS = {
    "ISO27001": {
        "name": "ISO 27001",
        "description": "Information Security Management",
        "total_controls": 114,
        "icon": "🔐",
    },
    "SOC2": {
        "name": "SOC 2 Type 2",
        "description": "Service Organization Control",
        "total_controls": 76,
        "icon": "✓",
    },
    "HIPAA": {
        "name": "HIPAA",
        "description": "Health Insurance Portability & Accountability",
        "total_controls": 91,
        "icon": "🏥",
    },
    "PCIDSS": {
        "name": "PCI DSS",
        "description": "Payment Card Industry Data Security Standard",
        "total_controls": 78,
        "icon": "💳",
    },
}

FRAMEWORK_CONTROLS = {
    "ISO27001": [
        ("A.5.1", "Policies for information security", "PASSING"),
        ("A.5.2", "Information security roles & responsibilities", "PASSING"),
        ("A.6.1", "Internal organization", "PASSING"),
        ("A.6.2", "Mobile device and teleworking policy", "NEEDS_CHANGES"),
        ("A.7.1", "Screening", "PASSING"),
        ("A.7.2", "Terms and conditions of employment", "PASSING"),
        ("A.7.4", "Acceptable use of assets", "FAILING"),
        ("A.7.5", "Return of assets", "PASSING"),
        ("A.8.1", "User endpoint devices", "PASSING"),
        ("A.8.2", "User access management", "PASSING"),
        ("A.8.3", "Access rights", "PASSING"),
        ("A.9.1", "Business requirements of access control", "PASSING"),
        ("A.10.1", "Cryptography policy", "PASSING"),
        ("A.11.1", "Perimeter security", "PASSING"),
        ("A.12.1", "Segregation of networks", "PASSING"),
        ("A.13.1", "Information transfer policies & procedures", "PASSING"),
        ("A.14.1", "Supplier relationships", "PASSING"),
        ("A.15.1", "Information security incident handling", "NEEDS_CHANGES"),
    ],
    "SOC2": [
        ("CC6.1", "Logical access controls", "PASSING"),
        ("CC6.2", "Management of privileged access", "PASSING"),
        ("CC7.1", "System monitoring", "PASSING"),
        ("CC7.2", "System monitoring - anomalies", "NEEDS_CHANGES"),
        ("CC7.3", "Unauthorized access", "PASSING"),
        ("CC9.1", "Logical access controls", "PASSING"),
        ("SI1.1", "Objectives for security incidents", "PASSING"),
        ("SI1.2", "Incident response team", "PASSING"),
        ("SI2.1", "Incident monitoring", "FAILING"),
        ("SI2.2", "Incident confirmation & documentation", "PASSING"),
    ],
    "HIPAA": [
        ("164.302(a)(1)", "Security management process", "PASSING"),
        ("164.302(b)(1)", "Assigned security responsibility", "PASSING"),
        ("164.304(a)(1)", "Privacy policies & procedures", "PASSING"),
        ("164.308(a)(3)", "Workforce security", "PASSING"),
        ("164.308(a)(4)", "Information access management", "PASSING"),
        ("164.312(a)(1)", "Access controls", "PASSING"),
        ("164.312(a)(2)", "Audit controls", "NEEDS_CHANGES"),
        ("164.312(b)", "Audit control enhancements", "PASSING"),
        ("164.312(c)(1)", "Encryption & decryption", "PASSING"),
        ("164.312(e)(1)", "Transmission security", "PASSING"),
    ],
    "PCIDSS": [
        ("1.1", "Firewall configuration", "PASSING"),
        ("2.1", "Default configurations", "PASSING"),
        ("3.2", "Storage of PAN", "PASSING"),
        ("4.1", "Encryption in transit", "PASSING"),
        ("6.2", "Security patches", "NEEDS_CHANGES"),
        ("8.1", "User ID assignment", "PASSING"),
        ("8.2", "Password policies", "PASSING"),
        ("8.4", "Update user passwords", "PASSING"),
        ("10.1", "Audit trail implementation", "PASSING"),
        ("10.3", "Audit trail protection", "PASSING"),
    ],
}


class ComplianceTracker:
    """Track and manage compliance with security frameworks."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_table()

    def init_table(self):
        """Initialize compliance tracking tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS compliance_assessments (
                    assessment_id TEXT PRIMARY KEY,
                    framework_id TEXT NOT NULL,
                    control_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    evidence_count INTEGER DEFAULT 0,
                    last_assessed TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(framework_id, control_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS compliance_findings (
                    finding_id TEXT PRIMARY KEY,
                    framework_id TEXT NOT NULL,
                    control_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    remediation TEXT,
                    status TEXT DEFAULT 'OPEN',
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                """
            )
            conn.commit()

    def get_frameworks(self) -> list[ComplianceFramework]:
        """Get all supported compliance frameworks."""
        return [
            ComplianceFramework(
                framework_id=fid,
                name=data["name"],
                description=data["description"],
                total_controls=data["total_controls"],
                icon=data["icon"],
            )
            for fid, data in FRAMEWORKS.items()
        ]

    def get_framework_controls(
        self, framework_id: str
    ) -> list[ComplianceControl]:
        """Get controls for a specific framework."""
        if framework_id not in FRAMEWORK_CONTROLS:
            return []

        controls = []
        for control_id, title, status in FRAMEWORK_CONTROLS[framework_id]:
            controls.append(
                ComplianceControl(
                    control_id=control_id,
                    framework_id=framework_id,
                    title=title,
                    description=f"Control {control_id} compliance assessment",
                    status=status,
                    evidence_count=0,
                    last_assessed=datetime.now(timezone.utc).isoformat(),
                )
            )
        return controls

    def get_compliance_status(self, framework_id: str) -> ComplianceStatus:
        """Calculate compliance status for a framework."""
        if framework_id not in FRAMEWORKS:
            raise ValueError(f"Unknown framework: {framework_id}")

        controls = self.get_framework_controls(framework_id)
        total = len(controls)
        passing = sum(1 for c in controls if c.status == "PASSING")
        failing = sum(1 for c in controls if c.status == "FAILING")
        needs_changes = sum(1 for c in controls if c.status == "NEEDS_CHANGES")

        compliance_pct = (passing / total * 100) if total > 0 else 0

        # Determine risk level
        if failing > 0:
            risk_level = "CRITICAL" if failing > 3 else "HIGH"
        elif needs_changes > 5:
            risk_level = "HIGH"
        elif needs_changes > 2:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return ComplianceStatus(
            framework_id=framework_id,
            name=FRAMEWORKS[framework_id]["name"],
            total_controls=total,
            passing_controls=passing,
            failing_controls=failing,
            needs_changes=needs_changes,
            compliance_percentage=round(compliance_pct, 2),
            last_updated=datetime.now(timezone.utc).isoformat(),
            risk_level=risk_level,
        )

    def get_compliance_dashboard(self) -> ComplianceDashboard:
        """Get overall compliance dashboard."""
        frameworks = list(FRAMEWORKS.keys())
        statuses = [self.get_compliance_status(fid) for fid in frameworks]

        total_controls = sum(s.total_controls for s in statuses)
        passing_controls = sum(s.passing_controls for s in statuses)
        critical_findings = sum(1 for s in statuses if s.risk_level == "CRITICAL")

        overall_compliance = (
            (passing_controls / total_controls * 100) if total_controls > 0 else 0
        )

        # Determine trend (simulated based on data distribution)
        avg_compliance = (
            sum(s.compliance_percentage for s in statuses) / len(statuses)
        )
        trend = (
            "IMPROVING"
            if avg_compliance > 75
            else ("STABLE" if avg_compliance > 60 else "DECLINING")
        )

        return ComplianceDashboard(
            generated_at=datetime.now(timezone.utc).isoformat(),
            overall_compliance=round(overall_compliance, 2),
            frameworks=statuses,
            critical_findings=critical_findings,
            passing_controls=passing_controls,
            total_controls=total_controls,
            trend=trend,
        )

    def update_control_status(
        self,
        framework_id: str,
        control_id: str,
        status: str,
        notes: Optional[str] = None,
    ):
        """Update compliance status of a control (admin function)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO compliance_assessments
                (assessment_id, framework_id, control_id, status, last_assessed, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{framework_id}_{control_id}",
                    framework_id,
                    control_id,
                    status,
                    datetime.now(timezone.utc).isoformat(),
                    notes,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def add_finding(
        self,
        framework_id: str,
        control_id: str,
        severity: str,
        description: str,
        remediation: Optional[str] = None,
    ) -> str:
        """Add a compliance finding/violation."""
        import uuid

        finding_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO compliance_findings
                (finding_id, framework_id, control_id, severity, description, remediation, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding_id,
                    framework_id,
                    control_id,
                    severity,
                    description,
                    remediation,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        return finding_id
