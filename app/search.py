"""Advanced search and filtering for evidence and cases."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Literal

from pydantic import BaseModel


class SearchQuery(BaseModel):
    """Search query parameters."""
    query: Optional[str] = None
    case_id: Optional[str] = None
    evidence_id: Optional[str] = None
    status: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_org_id: Optional[str] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None
    sort_by: str = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"
    limit: int = 50
    offset: int = 0


class SearchResult(BaseModel):
    """Search result item."""
    id: str
    type: str  # "evidence" or "case"
    title: str
    description: Optional[str] = None
    case_id: Optional[str] = None
    evidence_id: Optional[str] = None
    created_at: str
    relevance_score: float = 1.0


class SearchEngine:
    """Search and filtering engine for evidence and cases."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_full_text_search()

    def init_full_text_search(self):
        """Initialize full-text search tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Enable FTS5
            conn.enable_load_extension(False)  # Don't load extensions, use built-in
            
            # Create FTS virtual table if needed
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
                        evidence_id UNINDEXED,
                        case_id UNINDEXED,
                        description,
                        file_name,
                        source_device,
                        acquisition_method,
                        content=evidence,
                        content_rowid=rowid
                    )
                    """
                )
            except:
                pass  # Table may already exist

            # Create search index table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_index (
                    index_id TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    searchable_text TEXT NOT NULL,
                    case_id TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_search_resource ON search_index(resource_type, resource_id);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_search_case ON search_index(case_id);
                """
            )
            conn.commit()

    def index_evidence(
        self,
        evidence_id: str,
        case_id: str,
        description: str,
        file_name: str,
        source_device: Optional[str] = None,
        acquisition_method: Optional[str] = None,
    ) -> None:
        """Index evidence for full-text search."""
        searchable_text = f"""
            {description}
            {file_name}
            {source_device or ''}
            {acquisition_method or ''}
        """.strip()

        index_id = f"evidence:{evidence_id}"
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO search_index
                (index_id, resource_type, resource_id, searchable_text, case_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (index_id, "evidence", evidence_id, searchable_text, case_id, now, now),
            )
            conn.commit()

    def search(self, search_query: SearchQuery) -> tuple[list[SearchResult], int]:
        """Execute advanced search with filters.
        
        Returns (results, total_count).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Build base query
            query = """
                SELECT 
                    si.index_id,
                    si.resource_type,
                    si.resource_id,
                    si.searchable_text,
                    si.case_id,
                    si.created_at
                FROM search_index si
                WHERE 1=1
            """
            params = []

            # Add search term filter
            if search_query.query:
                query += " AND searchable_text LIKE ?"
                params.append(f"%{search_query.query}%")

            # Add case_id filter
            if search_query.case_id:
                query += " AND si.case_id = ?"
                params.append(search_query.case_id)

            # Add evidence_id filter  
            if search_query.evidence_id:
                query += " AND si.resource_id = ?"
                params.append(search_query.evidence_id)

            # Add date range filters
            if search_query.created_after:
                query += " AND si.created_at >= ?"
                params.append(search_query.created_after)

            if search_query.created_before:
                query += " AND si.created_at <= ?"
                params.append(search_query.created_before)

            # Count total results
            count_query = f"SELECT COUNT(*) FROM ({query}) as cnt"
            cursor = conn.execute(count_query, params)
            total_count = cursor.fetchone()[0]

            # Add sorting and pagination (with validation to prevent SQL injection)
            # Whitelist allowed sort columns
            allowed_sort_fields = {"created_at", "updated_at", "resource_type", "resource_id", "case_id"}
            sort_field = search_query.sort_by if search_query.sort_by in allowed_sort_fields else "created_at"
            sort_dir = "DESC" if search_query.sort_order.upper() == "DESC" else "ASC"
            
            # Validate pagination limits to prevent SQL injection
            limit = max(1, min(int(search_query.limit or 50), 500))  # Clamp between 1-500
            offset = max(0, int(search_query.offset or 0))  # Ensure non-negative
            
            query += f" ORDER BY si.{sort_field} {sort_dir}"
            query += f" LIMIT ? OFFSET ?"  # Use parameterized queries
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        results = []
        for row in rows:
            result = SearchResult(
                id=row["index_id"],
                type=row["resource_type"],
                title=row["resource_id"],
                description=row["searchable_text"][:200] if row["searchable_text"] else None,
                case_id=row["case_id"],
                evidence_id=row["resource_id"] if row["resource_type"] == "evidence" else None,
                created_at=row["created_at"],
                relevance_score=1.0,
            )
            results.append(result)

        return results, total_count

    def search_by_case(self, case_id: str) -> list[dict]:
        """Get all evidence for a case."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT resource_id, searchable_text, created_at
                FROM search_index
                WHERE case_id = ? AND resource_type = 'evidence'
                ORDER BY created_at DESC
                """,
                (case_id,),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_related_evidence(
        self,
        evidence_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Find related evidence based on search index similarity."""
        with sqlite3.connect(self.db_path) as conn:
            # Get the evidence's searchable text
            cursor = conn.execute(
                "SELECT case_id FROM search_index WHERE resource_id = ?",
                (evidence_id,),
            )
            row = cursor.fetchone()
            
            if not row:
                return []

            case_id = row[0]

            # Get other evidence from the same case
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT resource_id, searchable_text, created_at
                FROM search_index
                WHERE case_id = ? AND resource_type = 'evidence'
                AND resource_id != ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (case_id, evidence_id, limit),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_statistics(self) -> dict:
        """Get search index statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 
                    resource_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT case_id) as unique_cases
                FROM search_index
                GROUP BY resource_type
                """
            )
            stats = {row[0]: {"count": row[1], "unique_cases": row[2]} 
                    for row in cursor.fetchall()}

            cursor = conn.execute("SELECT COUNT(DISTINCT case_id) FROM search_index")
            total_cases = cursor.fetchone()[0]

        return {
            "resources": stats,
            "total_cases": total_cases,
        }
