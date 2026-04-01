"""Data retention policy enforcement for compliance and storage optimization."""
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass


class RetentionPolicy(str, Enum):
    """Predefined retention policies for different evidence types."""
    PERMANENT = "permanent"          # Never delete
    EXTENDED = "extended"            # 10 years (statute of limitations + appeal period)
    STANDARD = "standard"            # 7 years
    SHORT_TERM = "short_term"       # 2 years
    TEMPORARY = "temporary"          # 90 days


@dataclass
class PolicyConfig:
    """Configuration for retention policy."""
    name: str
    retention_days: int
    description: str


POLICY_DEFAULTS = {
    RetentionPolicy.PERMANENT: PolicyConfig(
        name="Permanent Retention",
        retention_days=3650,  # ~10 years (never auto-delete)
        description="Critical cases, landmark precedents"
    ),
    RetentionPolicy.EXTENDED: PolicyConfig(
        name="Extended Retention",
        retention_days=3650,  # 10 years
        description="Sexual assault, murder, financial crimes"
    ),
    RetentionPolicy.STANDARD: PolicyConfig(
        name="Standard Retention",
        retention_days=2555,  # 7 years
        description="Most felonies, serious misdemeanors"
    ),
    RetentionPolicy.SHORT_TERM: PolicyConfig(
        name="Short-term Retention",
        retention_days=730,  # 2 years
        description="Minor traffic, DUI, small drug cases"
    ),
    RetentionPolicy.TEMPORARY: PolicyConfig(
        name="Temporary Retention",
        retention_days=90,  # 90 days
        description="Interview recordings, drafts, test evidence"
    ),
}


class DataRetentionManager:
    """Manage data retention and compliance purging."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.policies: Dict[str, PolicyConfig] = {}
        self._init_policies()
        self._init_db()

    def _init_policies(self) -> None:
        """Initialize default retention policies."""
        for policy_type, config in POLICY_DEFAULTS.items():
            self.policies[policy_type] = config

    def _init_db(self) -> None:
        """Initialize retention tracking table."""
        with sqlite3.connect(self.db_path) as conn:
            # Try to drop old table if it exists with wrong schema
            try:
                conn.execute("DROP TABLE IF EXISTS data_retention_cases")
            except:
                pass
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS data_retention_cases (
                    case_id TEXT PRIMARY KEY,
                    retention_policy TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    manual_override BOOLEAN DEFAULT 0,
                    override_reason TEXT,
                    last_accessed REAL
                )
            """)
            
            try:
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_data_retention_expires 
                    ON data_retention_cases(expires_at)
                """)
            except:
                # Index may already exist, silently skip
                pass
            
            conn.commit()

    def set_retention_policy(self, case_id: str, policy: RetentionPolicy, 
                           override_reason: Optional[str] = None) -> Dict[str, Any]:
        """Set retention policy for a case."""
        config = POLICY_DEFAULTS.get(policy)
        if not config:
            return {
                'success': False,
                'error': f'Unknown policy: {policy}',
                'message': f'Retention policy "{policy}" not found'
            }
        
        now = datetime.now(timezone.utc).timestamp()
        expires_at = now + (config.retention_days * 86400)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO data_retention_cases
                (case_id, retention_policy, created_at, expires_at, 
                 manual_override, override_reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (case_id, policy, now, expires_at, 
                 1 if override_reason else 0, override_reason))
            conn.commit()
        
        expires_date = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        
        return {
            'success': True,
            'case_id': case_id,
            'policy': policy,
            'policy_name': config.name,
            'retention_days': config.retention_days,
            'expires_at': expires_date.isoformat(),
            'message': f'Retention policy set to {config.name} ({config.retention_days} days)'
        }

    def get_retention_policy(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get retention policy for a case."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("""
                SELECT retention_policy, created_at, expires_at, 
                       manual_override, override_reason
                FROM data_retention_cases
                WHERE case_id = ?
            """, (case_id,))
            row = cur.fetchone()
        
        if not row:
            return None
        
        policy_name, created_at, expires_at, override, reason = row
        config = POLICY_DEFAULTS.get(policy_name)
        
        return {
            'case_id': case_id,
            'policy': policy_name,
            'policy_name': config.name if config else policy_name,
            'created_at': datetime.fromtimestamp(created_at, tz=timezone.utc).isoformat(),
            'expires_at': datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
            'manual_override': bool(override),
            'override_reason': reason,
            'days_until_expiry': max(0, round((expires_at - datetime.now(timezone.utc).timestamp()) / 86400, 1))
        }

    def identify_eligible_for_deletion(self, dry_run: bool = True) -> Dict[str, Any]:
        """Identify evidence eligible for deletion based on retention policies."""
        now = datetime.now(timezone.utc).timestamp()
        
        with sqlite3.connect(self.db_path) as conn:
            # Find expired cases
            cur = conn.execute("""
                SELECT rp.case_id, rp.retention_policy, rp.expires_at,
                       COUNT(e.id) as evidence_count,
                       SUM(COALESCE(CAST(e.metadata AS INT), 0)) as total_size
                FROM data_retention_cases rp
                LEFT JOIN evidence e ON e.case_id = rp.case_id
                WHERE rp.expires_at <= ? AND rp.manual_override = 0
                GROUP BY rp.case_id
            """, (now,))
            
            eligible_cases = []
            total_evidence = 0
            
            for row in cur.fetchall():
                case_id, policy, expires_at, evidence_count, total_size = row
                evidence_count = evidence_count or 0
                total_size = total_size or 0
                total_evidence += evidence_count
                
                eligible_cases.append({
                    'case_id': case_id,
                    'policy': policy,
                    'expired_at': datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
                    'evidence_count': evidence_count,
                    'estimated_size_bytes': total_size
                })
        
        return {
            'dry_run': dry_run,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'eligible_cases_count': len(eligible_cases),
            'eligible_cases': eligible_cases,
            'eligible_evidence_count': total_evidence,
            'message': f'Found {len(eligible_cases)} cases eligible for deletion'
        }

    def purge_expired_evidence(self, execute: bool = False) -> Dict[str, Any]:
        """Purge expired evidence from system."""
        now = datetime.now(timezone.utc).timestamp()
        results = {
            'executed': execute,
            'deleted_cases': 0,
            'deleted_evidence': 0,
            'freed_space_bytes': 0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        with sqlite3.connect(self.db_path) as conn:
            # Find cases that should be purged
            cur = conn.execute("""
                SELECT case_id FROM data_retention_cases
                WHERE expires_at <= ? AND manual_override = 0
            """, (now,))
            
            cases_to_purge = [row[0] for row in cur.fetchall()]
            
            if execute and cases_to_purge:
                try:
                    for case_id in cases_to_purge:
                        # Get evidence to delete
                        cur = conn.execute("""
                            SELECT COUNT(*) FROM evidence WHERE case_id = ?
                        """, (case_id,))
                        evidence_count = cur.fetchone()[0]
                        
                        # Delete evidence records
                        conn.execute("DELETE FROM evidence WHERE case_id = ?", (case_id,))
                        
                        # Delete case audits
                        conn.execute("DELETE FROM case_audits WHERE case_id = ?", (case_id,))
                        
                        # Delete retention policy
                        conn.execute("DELETE FROM data_retention_cases WHERE case_id = ?", (case_id,))
                        
                        results['deleted_cases'] += 1
                        results['deleted_evidence'] += evidence_count
                    
                    conn.commit()
                    results['success'] = True
                    results['message'] = f'Purged {results["deleted_cases"]} cases'
                
                except Exception as e:
                    results['success'] = False
                    results['error'] = str(e)
                    results['message'] = f'Purge failed: {e}'
            else:
                results['success'] = True
                results['dry_run'] = not execute
                results['message'] = f'Would purge {len(cases_to_purge)} cases' if not execute else 'No cases to purge'
        
        return results

    def get_retention_report(self) -> Dict[str, Any]:
        """Generate retention policy report."""
        with sqlite3.connect(self.db_path) as conn:
            # Count cases by policy
            cur = conn.execute("""
                SELECT retention_policy, COUNT(*) as count
                FROM data_retention_cases
                GROUP BY retention_policy
            """)
            
            by_policy = {row[0]: row[1] for row in cur.fetchall()}
            
            # Find soon-to-expire cases (within 6 months)
            six_months_later = datetime.now(timezone.utc).timestamp() + (180 * 86400)
            cur = conn.execute("""
                SELECT case_id, retention_policy, expires_at
                FROM data_retention_cases
                WHERE expires_at <= ? AND expires_at > ?
                ORDER BY expires_at ASC
                LIMIT 20
            """, (six_months_later, datetime.now(timezone.utc).timestamp()))
            
            upcoming_expiry = []
            for case_id, policy, expires_at in cur.fetchall():
                days_left = round((expires_at - datetime.now(timezone.utc).timestamp()) / 86400, 1)
                upcoming_expiry.append({
                    'case_id': case_id,
                    'policy': policy,
                    'expires_at': datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
                    'days_until_expiry': days_left
                })
        
        return {
            'report_date': datetime.now(timezone.utc).isoformat(),
            'cases_by_policy': by_policy,
            'total_cases_with_policies': sum(by_policy.values()),
            'upcoming_expiry_count': len(upcoming_expiry),
            'upcoming_expiry_cases': upcoming_expiry
        }

    def extend_retention(self, case_id: str, new_policy: RetentionPolicy, 
                        reason: str) -> Dict[str, Any]:
        """Extend retention for a case with audit trail."""
        result = self.set_retention_policy(
            case_id, 
            new_policy,
            override_reason=f"Extended by admin: {reason}"
        )
        
        if result['success']:
            # Log the extension
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE data_retention_cases
                    SET manual_override = 1, override_reason = ?
                    WHERE case_id = ?
                """, (f"Extended: {reason}", case_id))
                conn.commit()
        
        return result

    def get_policy_names(self) -> Dict[str, str]:
        """Get human-readable names for all policies."""
        return {
            policy: config.name 
            for policy, config in self.policies.items()
        }
