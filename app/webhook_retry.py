"""Webhook retry mechanism with exponential backoff for reliability."""
import asyncio
import sqlite3
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta


class WebhookStatus(str, Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass
class WebhookDeliveryAttempt:
    """Record of a webhook delivery attempt."""
    webhook_id: str
    event_id: str
    attempt_number: int
    status_code: Optional[int] = None
    response: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = None
    next_retry_at: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class WebhookRetryManager:
    """Manage webhook delivery with exponential backoff retry."""
    
    # Retry configuration
    MAX_ATTEMPTS = 5
    BASE_BACKOFF_SECONDS = 60  # Start with 60 seconds
    MAX_BACKOFF_SECONDS = 3600  # Max 1 hour between retries
    BACKOFF_MULTIPLIER = 2  # Double the wait time each retry
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("DROP TABLE IF EXISTS webhook_deliveries")
                conn.execute("DROP TABLE IF EXISTS webhook_attempts")
            except:
                pass
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    id INTEGER PRIMARY KEY,
                    webhook_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_data TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    attempt_number INTEGER DEFAULT 0,
                    last_attempt_at REAL,
                    next_retry_at REAL,
                    last_status_code INTEGER,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS webhook_attempts (
                    id INTEGER PRIMARY KEY,
                    webhook_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    status_code INTEGER,
                    response_body TEXT,
                    error_message TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            try:
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_webhook_status ON webhook_deliveries(webhook_id, status)
                """)
            except:
                pass
            
            try:
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_next_retry ON webhook_deliveries(next_retry_at)
                """)
            except:
                pass
            
            conn.commit()

    def schedule_delivery(self, webhook_id: str, event_id: str, event_data: Dict[str, Any]) -> None:
        """Schedule webhook delivery."""
        now = time.time()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO webhook_deliveries 
                (webhook_id, event_id, event_data, status, attempt_number, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (webhook_id, event_id, json.dumps(event_data), WebhookStatus.PENDING, 0, now, now))
            conn.commit()

    def get_pending_deliveries(self, batch_size: int = 10) -> list:
        """Get pending deliveries ready for delivery."""
        now = time.time()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT * FROM webhook_deliveries
                WHERE status IN (?, ?)
                AND (next_retry_at IS NULL OR next_retry_at <= ?)
                ORDER BY created_at ASC
                LIMIT ?
            """, (WebhookStatus.PENDING, WebhookStatus.PROCESSING, now, batch_size))
            
            return [dict(row) for row in cur.fetchall()]

    def record_attempt(self, webhook_id: str, event_id: str, 
                      status_code: Optional[int], response: Optional[str], 
                      error: Optional[str]) -> bool:
        """
        Record a delivery attempt.
        
        Returns:
            True if should retry, False if permanent failure or max attempts exceeded
        """
        now = time.time()
        
        with sqlite3.connect(self.db_path) as conn:
            # Get current delivery record
            cur = conn.execute("""
                SELECT attempt_number, status FROM webhook_deliveries
                WHERE webhook_id = ? AND event_id = ?
            """, (webhook_id, event_id))
            row = cur.fetchone()
            
            if not row:
                return False
            
            attempt_number, current_status = row
            next_attempt = attempt_number + 1
            
            # Record attempt
            conn.execute("""
                INSERT INTO webhook_attempts
                (webhook_id, event_id, attempt_number, status_code, response_body, error_message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (webhook_id, event_id, next_attempt, status_code, response, error, now))
            
            # Determine if successful
            success = status_code and 200 <= status_code < 300
            
            if success:
                # Mark as successful
                conn.execute("""
                    UPDATE webhook_deliveries
                    SET status = ?, attempt_number = ?, last_attempt_at = ?, updated_at = ?
                    WHERE webhook_id = ? AND event_id = ?
                """, (WebhookStatus.SUCCESS, next_attempt, now, now, webhook_id, event_id))
                conn.commit()
                return False
            
            # Check if should retry
            if next_attempt >= self.MAX_ATTEMPTS:
                # Permanent failure
                conn.execute("""
                    UPDATE webhook_deliveries
                    SET status = ?, attempt_number = ?, last_attempt_at = ?, 
                        last_status_code = ?, last_error = ?, updated_at = ?
                    WHERE webhook_id = ? AND event_id = ?
                """, (WebhookStatus.PERMANENT_FAILURE, next_attempt, now, 
                     status_code, error, now, webhook_id, event_id))
                conn.commit()
                return False
            
            # Schedule retry with exponential backoff
            backoff = min(
                self.BASE_BACKOFF_SECONDS * (self.BACKOFF_MULTIPLIER ** (next_attempt - 1)),
                self.MAX_BACKOFF_SECONDS
            )
            next_retry_at = now + backoff
            
            conn.execute("""
                UPDATE webhook_deliveries
                SET status = ?, attempt_number = ?, last_attempt_at = ?,
                    next_retry_at = ?, last_status_code = ?, last_error = ?, updated_at = ?
                WHERE webhook_id = ? AND event_id = ?
            """, (WebhookStatus.PENDING, next_attempt, now, next_retry_at, 
                 status_code, error, now, webhook_id, event_id))
            conn.commit()
            
            return True

    def get_delivery_history(self, webhook_id: str, event_id: str) -> list:
        """Get delivery attempts for a webhook/event."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("""
                SELECT * FROM webhook_attempts
                WHERE webhook_id = ? AND event_id = ?
                ORDER BY timestamp DESC
            """, (webhook_id, event_id))
            
            return [dict(row) for row in cur.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Get webhook delivery statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM webhook_deliveries 
                GROUP BY status
            """)
            by_status = {row[0]: row[1] for row in cur.fetchall()}
            
            cur = conn.execute("SELECT COUNT(*) FROM webhook_attempts")
            total_attempts = cur.fetchone()[0]
            
            return {
                'by_status': by_status,
                'total_attempts': total_attempts,
                'success_rate_percent': self._calculate_success_rate()
            }

    def _calculate_success_rate(self) -> float:
        """Calculate overall success rate."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("""
                SELECT COUNT(*) FROM webhook_deliveries WHERE status = ?
            """, (WebhookStatus.SUCCESS,))
            success_count = cur.fetchone()[0]
            
            cur = conn.execute("SELECT COUNT(*) FROM webhook_deliveries")
            total_count = cur.fetchone()[0]
            
            if total_count == 0:
                return 0.0
            
            return round((success_count / total_count) * 100, 2)
