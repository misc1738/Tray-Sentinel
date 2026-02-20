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
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def insert_evidence(self, row: EvidenceRow, file_path: Path) -> None:
        with self._connect() as conn:
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

    def get_evidence(self, evidence_id: str) -> EvidenceRow:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,))
            r = cur.fetchone()
            if not r:
                raise KeyError("evidence not found")
            return EvidenceRow(**dict(r))

    def get_evidence_file_path(self, evidence_id: str) -> Path:
        with self._connect() as conn:
            cur = conn.execute("SELECT file_path FROM evidence_file WHERE evidence_id = ?", (evidence_id,))
            r = cur.fetchone()
            if not r:
                raise KeyError("evidence file not found")
            return Path(r["file_path"])

    def list_by_case(self, case_id: str) -> list[EvidenceRow]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM evidence WHERE case_id = ?", (case_id,))
            rows = cur.fetchall()
            return [EvidenceRow(**dict(r)) for r in rows]
