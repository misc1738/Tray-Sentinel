"""
Persistent Session Management with SQLite
"""
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict
import os


class SessionDatabase:
    """Persistent session store using SQLite"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the sessions table"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jwt_sessions (
                    user_id TEXT PRIMARY KEY,
                    refresh_token TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_activity TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)
            conn.commit()
    
    def create_session(self, user_id: str, refresh_token: str, ttl_days: int = 7) -> None:
        """Create a session entry"""
        now = datetime.now(timezone.utc).isoformat()
        expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO jwt_sessions (user_id, refresh_token, created_at, last_activity, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, refresh_token, now, now, expires_at))
            conn.commit()
    
    def get_session(self, user_id: str) -> Optional[Dict]:
        """Retrieve a session entry"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT user_id, refresh_token, created_at, last_activity, expires_at
                FROM jwt_sessions
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # Check if session hasn't expired
            expires_at = datetime.fromisoformat(row['expires_at'])
            if expires_at < datetime.now(timezone.utc):
                # Delete expired session
                self.invalidate_session(user_id)
                return None
            
            # Update last activity
            self._update_activity(user_id)
            
            return {
                "user_id": row['user_id'],
                "refresh_token": row['refresh_token'],
                "created_at": row['created_at'],
                "last_activity": row['last_activity'],
                "expires_at": row['expires_at']
            }
    
    def _update_activity(self, user_id: str) -> None:
        """Update last activity timestamp"""
        now = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE jwt_sessions
                SET last_activity = ?
                WHERE user_id = ?
            """, (now, user_id))
            conn.commit()
    
    def invalidate_session(self, user_id: str) -> None:
        """Logout: invalidate a session"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM jwt_sessions WHERE user_id = ?", (user_id,))
            conn.commit()
    
    def invalidate_all_sessions(self) -> None:
        """Admin: invalidate all sessions (e.g., after security breach)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM jwt_sessions")
            conn.commit()
    
    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions older than TTL"""
        now = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM jwt_sessions
                WHERE expires_at < ?
            """, (now,))
            conn.commit()
            return cursor.rowcount
