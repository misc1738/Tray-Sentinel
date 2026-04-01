from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    description TEXT NOT NULL,
    source_device TEXT,
    acquisition_method TEXT NOT NULL,
    file_name TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_file (
    evidence_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_evidence_case_id ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_sha256 ON evidence(sha256);
CREATE INDEX IF NOT EXISTS idx_evidence_created_at ON evidence(created_at);
CREATE INDEX IF NOT EXISTS idx_evidence_case_created ON evidence(case_id, created_at);
"""


@dataclass
class EvidenceRow:
    evidence_id: str
    case_id: str
    description: str
    source_device: Optional[str]
    acquisition_method: str
    file_name: str
    sha256: str
    created_at: str


class EvidenceStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            return conn
        except OSError as e:
            raise RuntimeError(f"Database connection failed: {e}")

    def init(self) -> None:
        try:
            with self._connect() as conn:
                conn.executescript(SCHEMA)
        except sqlite3.Error as e:
            raise RuntimeError(f"Database initialization failed: {e}")

    def insert_evidence(self, row: EvidenceRow, file_path: Path) -> None:
        try:
            with self._connect() as conn:
                # Use transaction for atomicity
                conn.execute(
                    """
                    INSERT INTO evidence (evidence_id, case_id, description, source_device, acquisition_method, file_name, sha256, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.evidence_id,
                        row.case_id,
                        row.description,
                        row.source_device,
                        row.acquisition_method,
                        row.file_name,
                        row.sha256,
                        row.created_at,
                    ),
                )
                conn.execute(
                    "INSERT INTO evidence_file (evidence_id, file_path) VALUES (?, ?)",
                    (row.evidence_id, str(file_path)),
                )
                conn.commit()  # Explicit commit for transaction
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Evidence insertion failed: {e}")
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error during evidence insertion: {e}")

    def get_evidence(self, evidence_id: str) -> EvidenceRow:
        try:
            with self._connect() as conn:
                cur = conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,))
                r = cur.fetchone()
                if not r:
                    raise KeyError("evidence not found")
                return EvidenceRow(**dict(r))
        except KeyError:
            raise
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving evidence: {e}")

    def get_evidence_file_path(self, evidence_id: str) -> Path:
        try:
            with self._connect() as conn:
                cur = conn.execute("SELECT file_path FROM evidence_file WHERE evidence_id = ?", (evidence_id,))
                r = cur.fetchone()
                if not r:
                    raise KeyError("evidence file not found")
                path = Path(r["file_path"])
                # Validate file still exists on disk
                if not path.exists():
                    raise FileNotFoundError(f"Evidence file not found on disk: {path}")
                return path
        except (KeyError, FileNotFoundError):
            raise
        except sqlite3.Error as e:
            raise RuntimeError(f"Database error retrieving evidence file path: {e}")

    def list_by_case(self, case_id: str) -> list[EvidenceRow]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM evidence WHERE case_id = ?", (case_id,))
            rows = cur.fetchall()
            return [EvidenceRow(**dict(r)) for r in rows]
