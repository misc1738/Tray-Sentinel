"""Advanced rate limiting with per-user and per-org support."""
import time
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class RateLimitTier(str, Enum):
    """Rate limit tiers for different user types."""
    BASIC = "basic"        # 100/min, 1000/hour
    STANDARD = "standard"  # 1000/min, 10000/hour
    PREMIUM = "premium"    # 10000/min, 100000/hour
    UNLIMITED = "unlimited"


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a tier."""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int


# Tier configurations
TIER_CONFIGS: Dict[RateLimitTier, RateLimitConfig] = {
    RateLimitTier.BASIC: RateLimitConfig(100, 1000, 10000),
    RateLimitTier.STANDARD: RateLimitConfig(1000, 10000, 100000),
    RateLimitTier.PREMIUM: RateLimitConfig(10000, 100000, 1000000),
    RateLimitTier.UNLIMITED: RateLimitConfig(999999, 9999999, 99999999),
}


class AdvancedRateLimiter:
    """Rate limiter with per-user and per-org support."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id INTEGER PRIMARY KEY,
                    identifier TEXT NOT NULL UNIQUE,
                    tier TEXT NOT NULL DEFAULT 'basic',
                    requests_minute INTEGER DEFAULT 0,
                    requests_hour INTEGER DEFAULT 0,
                    requests_day INTEGER DEFAULT 0,
                    last_reset_minute INTEGER,
                    last_reset_hour INTEGER,
                    last_reset_day INTEGER,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_identifier ON rate_limits(identifier)
            """)
            conn.commit()

    def _get_or_create_limit(self, identifier: str, tier: RateLimitTier) -> Dict:
        """Get or create rate limit entry."""
        now = time.time()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM rate_limits WHERE identifier = ?", (identifier,))
            row = cur.fetchone()
            
            if row:
                return dict(row)
            
            # Create new entry
            conn.execute("""
                INSERT INTO rate_limits (identifier, tier, created_at, updated_at, 
                                       last_reset_minute, last_reset_hour, last_reset_day)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (identifier, tier.value, now, now, now, now, now))
            conn.commit()
            
            cur = conn.execute("SELECT * FROM rate_limits WHERE identifier = ?", (identifier,))
            return dict(cur.fetchone())

    def check_limit(self, identifier: str, tier: RateLimitTier = RateLimitTier.BASIC) -> Tuple[bool, Dict]:
        """
        Check if request is allowed.
        
        Returns:
            (is_allowed, status_dict)
        """
        now = time.time()
        limit_entry = self._get_or_create_limit(identifier, tier)
        config = TIER_CONFIGS[RateLimitTier(limit_entry['tier'])]
        
        # Reset counters if windows expired
        minute_ago = now - 60
        hour_ago = now - 3600
        day_ago = now - 86400
        
        reset_minute = limit_entry['last_reset_minute'] < minute_ago
        reset_hour = limit_entry['last_reset_hour'] < hour_ago
        reset_day = limit_entry['last_reset_day'] < day_ago
        
        with sqlite3.connect(self.db_path) as conn:
            # Reset counters if needed
            if reset_minute:
                conn.execute("UPDATE rate_limits SET requests_minute = 0, last_reset_minute = ? WHERE identifier = ?",
                           (now, identifier))
            if reset_hour:
                conn.execute("UPDATE rate_limits SET requests_hour = 0, last_reset_hour = ? WHERE rate_limits WHERE identifier = ?",
                           (now, identifier))
            if reset_day:
                conn.execute("UPDATE rate_limits SET requests_day = 0, last_reset_day = ? WHERE identifier = ?",
                           (now, identifier))
            
            # Get current counts
            cur = conn.execute("SELECT requests_minute, requests_hour, requests_day FROM rate_limits WHERE identifier = ?",
                             (identifier,))
            counts = cur.fetchone()
            min_count, hour_count, day_count = counts if counts else (0, 0, 0)
            
            # Check limits
            minute_ok = min_count < config.requests_per_minute
            hour_ok = hour_count < config.requests_per_hour
            day_ok = day_count < config.requests_per_day
            
            allowed = minute_ok and hour_ok and day_ok
            
            if allowed:
                # Increment counters
                conn.execute("""
                    UPDATE rate_limits 
                    SET requests_minute = requests_minute + 1,
                        requests_hour = requests_hour + 1,
                        requests_day = requests_day + 1,
                        updated_at = ?
                    WHERE identifier = ?
                """, (now, identifier))
                conn.commit()
            
            status = {
                'allowed': allowed,
                'tier': limit_entry['tier'],
                'minute': {'used': min_count, 'limit': config.requests_per_minute, 'ok': minute_ok},
                'hour': {'used': hour_count, 'limit': config.requests_per_hour, 'ok': hour_ok},
                'day': {'used': day_count, 'limit': config.requests_per_day, 'ok': day_ok},
            }
            
            return allowed, status

    def set_tier(self, identifier: str, tier: RateLimitTier) -> None:
        """Set rate limit tier for an identifier."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE rate_limits SET tier = ? WHERE identifier = ?", 
                        (tier.value, identifier))
            conn.commit()

    def get_stats(self) -> Dict:
        """Get global rate limiting statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM rate_limits")
            total = cur.fetchone()[0]
            
            cur = conn.execute("SELECT tier, COUNT(*) as count FROM rate_limits GROUP BY tier")
            by_tier = {row[0]: row[1] for row in cur.fetchall()}
            
            return {
                'total_identifiers': total,
                'by_tier': by_tier
            }
