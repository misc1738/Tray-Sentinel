"""Rate limiting middleware and utilities."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitStore:
    """Store and manage rate limit state."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_table()

    def init_table(self):
        """Initialize rate limit tracking table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_limits (
                    limit_key TEXT PRIMARY KEY,
                    request_count INTEGER DEFAULT 0,
                    window_reset_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rate_limits_reset ON rate_limits(window_reset_at);
                """
            )
            conn.commit()

    def check_limit(
        self,
        key: str,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> bool:
        """Check if request is within rate limit.
        
        Returns True if allowed, False if limit exceeded.
        """
        now = datetime.now(tz=timezone.utc)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT request_count, window_reset_at FROM rate_limits WHERE limit_key = ?",
                (key,),
            )
            row = cursor.fetchone()

            if row is None:
                # Create new limit record
                reset_at = (now + timedelta(seconds=window_seconds)).isoformat()
                cursor.execute(
                    """
                    INSERT INTO rate_limits (limit_key, request_count, window_reset_at, last_updated)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key, 1, reset_at, now.isoformat()),
                )
                conn.commit()
                return True

            count, reset_at_str = row
            reset_at = datetime.fromisoformat(reset_at_str)

            if now >= reset_at:
                # Window has expired, reset counter
                new_reset_at = (now + timedelta(seconds=window_seconds)).isoformat()
                cursor.execute(
                    """
                    UPDATE rate_limits
                    SET request_count = 1, window_reset_at = ?, last_updated = ?
                    WHERE limit_key = ?
                    """,
                    (new_reset_at, now.isoformat(), key),
                )
                conn.commit()
                return True
            else:
                # Still in window - check if limit exceeded
                if count >= max_requests:
                    return False
                
                # Increment counter
                cursor.execute(
                    """
                    UPDATE rate_limits
                    SET request_count = ?, last_updated = ?
                    WHERE limit_key = ?
                    """,
                    (count + 1, now.isoformat(), key),
                )
                conn.commit()
                return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits per IP address."""

    def __init__(self, app, rate_limit_store: RateLimitStore):
        super().__init__(app)
        self.store = rate_limit_store
        self.exempt_paths = {"/health", "/docs", "/openapi.json"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Skip rate limiting for GET requests to keep API accessible
        if request.method == "GET":
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limit (100 requests per minute per IP)
        limit_key = f"ip:{client_ip}"
        if not self.store.check_limit(limit_key, max_requests=100, window_seconds=60):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Max 100 requests per minute.",
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = "100"
        response.headers["X-RateLimit-Window"] = "60"
        
        return response

    def cleanup(self):
        """Cleanup old rate limit records (older than 24 hours)."""
        from datetime import timedelta
        from datetime import datetime
        from datetime import timezone
        
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).isoformat()
        with sqlite3.connect(self.store.db_path) as conn:
            conn.execute(
                "DELETE FROM rate_limits WHERE last_updated < ?",
                (cutoff,),
            )
            conn.commit()
