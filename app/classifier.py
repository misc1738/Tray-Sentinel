"""Evidence tagging, classification, and metadata management."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from enum import Enum

from pydantic import BaseModel


class ClassificationType(str, Enum):
    """Evidence classification levels."""
    DNA = "DNA"
    DIGITAL = "DIGITAL"
    FIBERS = "FIBERS"
    BIOLOGICAL = "BIOLOGICAL"
    CHEMICAL = "CHEMICAL"
    FIREARM = "FIREARM"
    TRACE = "TRACE"
    DOCUMENT = "DOCUMENT"
    AUDIO_VIDEO = "AUDIO_VIDEO"
    CONTROLLED_SUBSTANCE = "CONTROLLED_SUBSTANCE"
    TOOL_MARK = "TOOL_MARK"
    PATTERN = "PATTERN"
    OTHER = "OTHER"


class EvidenceTag(BaseModel):
    """Evidence tag/label for categorization."""
    tag_id: str
    evidence_id: str
    tag_name: str
    tag_category: str
    color: Optional[str] = None
    created_at: str


class EvidenceMetadata(BaseModel):
    """Custom metadata for evidence."""
    metadata_id: str
    evidence_id: str
    schema_id: str
    field_name: str
    field_value: str
    field_type: str
    created_at: str


class EvidenceClassifier:
    """Manage evidence classification, tagging, and metadata."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_tables()

    def init_tables(self):
        """Initialize classification tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Tags table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_tags (
                    tag_id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL,
                    tag_name TEXT NOT NULL,
                    tag_category TEXT,
                    color TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tags_evidence ON evidence_tags(evidence_id);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tags_category ON evidence_tags(tag_category);
                """
            )

            # Classification table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_classifications (
                    classification_id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL UNIQUE,
                    classification_type TEXT NOT NULL,
                    subcategory TEXT,
                    chain_of_custody_level INTEGER DEFAULT 1,
                    storage_requirements TEXT,
                    handling_restrictions TEXT,
                    assigned_by TEXT,
                    assigned_at TEXT NOT NULL,
                    FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_classification_type ON evidence_classifications(classification_type);
                """
            )

            # Custom metadata schema
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata_schemas (
                    schema_id TEXT PRIMARY KEY,
                    schema_name TEXT NOT NULL UNIQUE,
                    case_type TEXT,
                    fields TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            # Evidence metadata
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_metadata (
                    metadata_id TEXT PRIMARY KEY,
                    evidence_id TEXT NOT NULL,
                    schema_id TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    field_value TEXT,
                    field_type TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id),
                    FOREIGN KEY(schema_id) REFERENCES metadata_schemas(schema_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_metadata_evidence ON evidence_metadata(evidence_id);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_metadata_schema ON evidence_metadata(schema_id);
                """
            )

            conn.commit()

    def add_tag(
        self,
        evidence_id: str,
        tag_name: str,
        tag_category: str = "general",
        color: Optional[str] = None,
    ) -> EvidenceTag:
        """Add a tag to evidence."""
        tag_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO evidence_tags (tag_id, evidence_id, tag_name, tag_category, color, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (tag_id, evidence_id, tag_name, tag_category, color, now),
            )
            conn.commit()

        return EvidenceTag(
            tag_id=tag_id,
            evidence_id=evidence_id,
            tag_name=tag_name,
            tag_category=tag_category,
            color=color,
            created_at=now,
        )

    def get_tags(self, evidence_id: str) -> list[EvidenceTag]:
        """Get all tags for evidence."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM evidence_tags WHERE evidence_id = ? ORDER BY created_at DESC",
                (evidence_id,),
            )
            rows = cursor.fetchall()

        return [
            EvidenceTag(
                tag_id=row["tag_id"],
                evidence_id=row["evidence_id"],
                tag_name=row["tag_name"],
                tag_category=row["tag_category"],
                color=row["color"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def remove_tag(self, tag_id: str) -> bool:
        """Remove a tag."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM evidence_tags WHERE tag_id = ?", (tag_id,))
            conn.commit()
            return cursor.rowcount > 0

    def classify_evidence(
        self,
        evidence_id: str,
        classification_type: str,
        subcategory: Optional[str] = None,
        chain_of_custody_level: int = 1,
        storage_requirements: Optional[str] = None,
        handling_restrictions: Optional[str] = None,
        assigned_by: Optional[str] = None,
    ) -> dict:
        """Classify evidence by type and requirements."""
        classification_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO evidence_classifications
                (classification_id, evidence_id, classification_type, subcategory,
                 chain_of_custody_level, storage_requirements, handling_restrictions,
                 assigned_by, assigned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    classification_id,
                    evidence_id,
                    classification_type,
                    subcategory,
                    chain_of_custody_level,
                    storage_requirements,
                    handling_restrictions,
                    assigned_by,
                    now,
                ),
            )
            conn.commit()

        return {
            "classification_id": classification_id,
            "evidence_id": evidence_id,
            "classification_type": classification_type,
            "subcategory": subcategory,
            "chain_of_custody_level": chain_of_custody_level,
            "storage_requirements": storage_requirements,
            "handling_restrictions": handling_restrictions,
            "assigned_at": now,
        }

    def get_classification(self, evidence_id: str) -> Optional[dict]:
        """Get evidence classification."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM evidence_classifications WHERE evidence_id = ?",
                (evidence_id,),
            )
            row = cursor.fetchone()

        return dict(row) if row else None

    def create_metadata_schema(
        self,
        schema_name: str,
        fields: list[dict],
        case_type: Optional[str] = None,
    ) -> dict:
        """Create a custom metadata schema for case types."""
        schema_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        fields_json = json.dumps(fields)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO metadata_schemas (schema_id, schema_name, case_type, fields, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (schema_id, schema_name, case_type, fields_json, now),
            )
            conn.commit()

        return {
            "schema_id": schema_id,
            "schema_name": schema_name,
            "case_type": case_type,
            "fields": fields,
            "created_at": now,
        }

    def get_schemas(self, case_type: Optional[str] = None) -> list[dict]:
        """Get available metadata schemas."""
        query = "SELECT * FROM metadata_schemas WHERE 1=1"
        params = []

        if case_type:
            query += " AND (case_type = ? OR case_type IS NULL)"
            params.append(case_type)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                "schema_id": row["schema_id"],
                "schema_name": row["schema_name"],
                "case_type": row["case_type"],
                "fields": json.loads(row["fields"]),
                "created_at": row["created_at"],
            })

        return results

    def add_metadata(
        self,
        evidence_id: str,
        schema_id: str,
        field_name: str,
        field_value: str,
        field_type: str = "string",
    ) -> EvidenceMetadata:
        """Add custom metadata to evidence."""
        metadata_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO evidence_metadata
                (metadata_id, evidence_id, schema_id, field_name, field_value, field_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (metadata_id, evidence_id, schema_id, field_name, field_value, field_type, now),
            )
            conn.commit()

        return EvidenceMetadata(
            metadata_id=metadata_id,
            evidence_id=evidence_id,
            schema_id=schema_id,
            field_name=field_name,
            field_value=field_value,
            field_type=field_type,
            created_at=now,
        )

    def get_metadata(self, evidence_id: str, schema_id: Optional[str] = None) -> list[EvidenceMetadata]:
        """Get metadata for evidence."""
        query = "SELECT * FROM evidence_metadata WHERE evidence_id = ?"
        params = [evidence_id]

        if schema_id:
            query += " AND schema_id = ?"
            params.append(schema_id)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [
            EvidenceMetadata(
                metadata_id=row["metadata_id"],
                evidence_id=row["evidence_id"],
                schema_id=row["schema_id"],
                field_name=row["field_name"],
                field_value=row["field_value"],
                field_type=row["field_type"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_evidence_by_tag(self, tag_name: str) -> list[str]:
        """Find all evidence with a specific tag."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT evidence_id FROM evidence_tags WHERE tag_name = ?",
                (tag_name,),
            )
            return [row[0] for row in cursor.fetchall()]

    def get_evidence_by_classification(self, classification_type: str) -> list[str]:
        """Find all evidence of a specific classification."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT DISTINCT evidence_id FROM evidence_classifications WHERE classification_type = ?",
                (classification_type,),
            )
            return [row[0] for row in cursor.fetchall()]

    def get_tag_cloud(self, case_id: Optional[str] = None) -> dict:
        """Get tag statistics for visualization."""
        query = """
            SELECT tag_name, tag_category, COUNT(*) as count
            FROM evidence_tags
        """
        params = []

        if case_id:
            query += """
                WHERE evidence_id IN (
                    SELECT evidence_id FROM evidence WHERE case_id = ?
                )
            """
            params.append(case_id)

        query += " GROUP BY tag_name, tag_category ORDER BY count DESC"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        tag_cloud = {}
        for tag_name, category, count in rows:
            if category not in tag_cloud:
                tag_cloud[category] = []
            tag_cloud[category].append({"tag": tag_name, "count": count})

        return tag_cloud
