"""Organization and team management."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class Organization(BaseModel):
    """Organization entity."""
    org_id: str
    org_name: str
    description: Optional[str] = None
    jurisdiction: Optional[str] = None
    contact_email: Optional[str] = None
    active: bool
    created_at: str


class Team(BaseModel):
    """Team within organization."""
    team_id: str
    org_id: str
    team_name: str
    description: Optional[str] = None
    members: list[str]
    created_at: str


class Department(BaseModel):
    """Department for organization structure."""
    dept_id: str
    org_id: str
    dept_name: str
    director: Optional[str] = None
    description: Optional[str] = None
    created_at: str


class OrganizationManager:
    """Manage organizations, teams, and departments."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_tables()

    def init_tables(self):
        """Initialize organization tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Organizations
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    org_id TEXT PRIMARY KEY,
                    org_name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    jurisdiction TEXT,
                    contact_email TEXT,
                    active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_org_active ON organizations(active);
                """
            )

            # Departments
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS departments (
                    dept_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    dept_name TEXT NOT NULL,
                    director TEXT,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(org_id) REFERENCES organizations(org_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_dept_org ON departments(org_id);
                """
            )

            # Teams
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS teams (
                    team_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    dept_id TEXT,
                    team_name TEXT NOT NULL,
                    description TEXT,
                    members TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(org_id) REFERENCES organizations(org_id),
                    FOREIGN KEY(dept_id) REFERENCES departments(dept_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_team_org ON teams(org_id);
                """
            )

            # User-Organization membership
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_organizations (
                    membership_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    org_id TEXT NOT NULL,
                    team_id TEXT,
                    dept_id TEXT,
                    role TEXT,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(org_id) REFERENCES organizations(org_id),
                    FOREIGN KEY(team_id) REFERENCES teams(team_id),
                    FOREIGN KEY(dept_id) REFERENCES departments(dept_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_user_org ON user_organizations(user_id, org_id);
                """
            )

            # Inter-organization relationships
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS org_partnerships (
                    partnership_id TEXT PRIMARY KEY,
                    org_a_id TEXT NOT NULL,
                    org_b_id TEXT NOT NULL,
                    relationship_type TEXT,
                    active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(org_a_id) REFERENCES organizations(org_id),
                    FOREIGN KEY(org_b_id) REFERENCES organizations(org_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_partnership_active ON org_partnerships(active);
                """
            )

            conn.commit()

    def create_organization(
        self,
        org_name: str,
        description: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        contact_email: Optional[str] = None,
    ) -> Organization:
        """Create a new organization."""
        org_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO organizations (org_id, org_name, description, jurisdiction, contact_email, active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (org_id, org_name, description, jurisdiction, contact_email, now),
            )
            conn.commit()

        return Organization(
            org_id=org_id,
            org_name=org_name,
            description=description,
            jurisdiction=jurisdiction,
            contact_email=contact_email,
            active=True,
            created_at=now,
        )

    def get_organization(self, org_id: str) -> Optional[Organization]:
        """Get organization details."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM organizations WHERE org_id = ?",
                (org_id,),
            )
            row = cursor.fetchone()

        return Organization(**row) if row else None

    def get_organizations(self, active_only: bool = True) -> list[Organization]:
        """Get all organizations."""
        query = "SELECT * FROM organizations"
        if active_only:
            query += " WHERE active = 1"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query)
            rows = cursor.fetchall()

        return [Organization(**row) for row in rows]

    def create_department(
        self,
        org_id: str,
        dept_name: str,
        director: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Department:
        """Create a department."""
        dept_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO departments (dept_id, org_id, dept_name, director, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (dept_id, org_id, dept_name, director, description, now),
            )
            conn.commit()

        return Department(
            dept_id=dept_id,
            org_id=org_id,
            dept_name=dept_name,
            director=director,
            description=description,
            created_at=now,
        )

    def get_departments(self, org_id: str) -> list[Department]:
        """Get departments for organization."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM departments WHERE org_id = ? ORDER BY dept_name",
                (org_id,),
            )
            rows = cursor.fetchall()

        return [Department(**row) for row in rows]

    def create_team(
        self,
        org_id: str,
        team_name: str,
        members: list[str],
        dept_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Team:
        """Create a team."""
        team_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        members_json = json.dumps(members)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO teams (team_id, org_id, dept_id, team_name, description, members, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (team_id, org_id, dept_id, team_name, description, members_json, now),
            )
            conn.commit()

        return Team(
            team_id=team_id,
            org_id=org_id,
            team_name=team_name,
            description=description,
            members=members,
            created_at=now,
        )

    def get_teams(self, org_id: str) -> list[Team]:
        """Get teams for organization."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM teams WHERE org_id = ? ORDER BY team_name",
                (org_id,),
            )
            rows = cursor.fetchall()

        teams = []
        for row in rows:
            team_dict = dict(row)
            team_dict["members"] = json.loads(team_dict["members"]) if team_dict["members"] else []
            teams.append(Team(**team_dict))

        return teams

    def add_team_member(self, team_id: str, user_id: str) -> bool:
        """Add user to team."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT members FROM teams WHERE team_id = ?", (team_id,))
            row = cursor.fetchone()
            if not row:
                return False

            members = json.loads(row[0]) if row[0] else []
            if user_id not in members:
                members.append(user_id)
                conn.execute(
                    "UPDATE teams SET members = ? WHERE team_id = ?",
                    (json.dumps(members), team_id),
                )
                conn.commit()

        return True

    def add_user_to_organization(
        self,
        user_id: str,
        org_id: str,
        role: str,
        team_id: Optional[str] = None,
        dept_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> dict:
        """Add user to organization."""
        membership_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_organizations
                (membership_id, user_id, org_id, team_id, dept_id, role, is_admin, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (membership_id, user_id, org_id, team_id, dept_id, role, int(is_admin), now),
            )
            conn.commit()

        return {
            "membership_id": membership_id,
            "user_id": user_id,
            "org_id": org_id,
            "role": role,
            "is_admin": is_admin,
            "created_at": now,
        }

    def get_user_organizations(self, user_id: str) -> list[dict]:
        """Get all organizations for a user."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT uo.*, o.org_name FROM user_organizations uo
                JOIN organizations o ON uo.org_id = o.org_id
                WHERE uo.user_id = ? AND o.active = 1
                """,
                (user_id,),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def create_partnership(
        self,
        org_a_id: str,
        org_b_id: str,
        relationship_type: str,
    ) -> dict:
        """Create partnership between organizations."""
        partnership_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO org_partnerships
                (partnership_id, org_a_id, org_b_id, relationship_type, active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (partnership_id, org_a_id, org_b_id, relationship_type, now),
            )
            conn.commit()

        return {
            "partnership_id": partnership_id,
            "org_a_id": org_a_id,
            "org_b_id": org_b_id,
            "relationship_type": relationship_type,
            "active": True,
            "created_at": now,
        }

    def get_organization_statistics(self, org_id: str) -> dict:
        """Get organization statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Member count
            cursor = conn.execute(
                "SELECT COUNT(DISTINCT user_id) FROM user_organizations WHERE org_id = ?",
                (org_id,),
            )
            members = cursor.fetchone()[0]

            # Team count
            cursor = conn.execute(
                "SELECT COUNT(*) FROM teams WHERE org_id = ?",
                (org_id,),
            )
            teams = cursor.fetchone()[0]

            # Department count
            cursor = conn.execute(
                "SELECT COUNT(*) FROM departments WHERE org_id = ?",
                (org_id,),
            )
            departments = cursor.fetchone()[0]

            # Case count
            cursor = conn.execute(
                """
                SELECT COUNT(DISTINCT case_id) FROM evidence
                WHERE evidence_id IN (
                    SELECT DISTINCT evidence_id FROM ledger WHERE actor_org_id = ?
                )
                """,
                (org_id,),
            )
            cases = cursor.fetchone()[0]

        return {
            "org_id": org_id,
            "member_count": members,
            "team_count": teams,
            "department_count": departments,
            "case_count": cases,
        }
