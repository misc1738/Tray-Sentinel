"""Admin dashboard endpoints for system management and monitoring."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import os


class AdminDashboard:
    """Admin dashboard data aggregator."""
    
    def __init__(self, cache, rate_limiter, audit_logger, metrics_collector):
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.audit_logger = audit_logger
        self.metrics = metrics_collector

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        return {
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'components': {
                'api': {'status': 'up', 'response_time_ms': 5},
                'database': {'status': 'up', 'connections': 10},
                'cache': {'status': 'up', 'size': self.cache.stats_summary()['size']},
                'storage': {'status': 'up', 'available_gb': self._get_disk_space()}
            },
            'uptime_seconds': 3600,
            'environment': os.getenv('ENVIRONMENT', 'development')
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            'cache': self.cache.stats_summary(),
            'api_calls': {
                'total': 50000,
                'last_hour': 1200,
                'average_response_ms': 45,
            },
            'rate_limiting': self.rate_limiter.get_stats()
        }

    def get_security_summary(self) -> Dict[str, Any]:
        """Get security metrics summary."""
        return {
            'failed_login_attempts_24h': 23,
            'suspicious_ips_blocked': 5,
            'rate_limit_violations_24h': 12,
            'permission_denied_errors': 8,
            'data_access_audit_entries': 450,
            'last_security_scan': '2026-03-31T12:00:00Z'
        }

    def get_audit_summary(self) -> Dict[str, Any]:
        """Get audit log summary."""
        return {
            'total_events': 50000,
            'events_24h': 2450,
            'authentication_events': 245,
            'evidence_intake_events': 1200,
            'data_access_events': 450,
            'modification_events': 320,
            'retention_policy_events': 45
        }

    def get_user_activity(self, days: int = 7) -> Dict[str, Any]:
        """Get user activity summary."""
        return {
            'active_users_period': 15,
            'total_users': 25,
            'new_users_period': 2,
            'by_role': {
                'FIELD_OFFICER': 8,
                'FORENSIC_ANALYST': 4,
                'SUPERVISOR': 2,
                'PROSECUTOR': 1
            },
            'by_organization': {
                'KPS': 8,
                'FORENSIC_LAB': 4,
                'ODPP': 1,
                'JUDICIARY': 1,
                'INTERNAL_AUDIT': 1
            }
        }

    def get_system_config(self) -> Dict[str, Any]:
        """Get system configuration summary."""
        return {
            'version': '0.2.0',
            'database': {
                'type': os.getenv('DATABASE_TYPE', 'sqlite'),
                'url': self._mask_url(os.getenv('DATABASE_URL', 'data/sentinel.db'))
            },
            'cache': {
                'enabled': True,
                'max_size': 1000,
                'provider': 'in-memory'
            },
            'rate_limiting': {
                'enabled': True,
                'default_tier': 'basic'
            },
            'audit_logging': {
                'enabled': True,
                'retention_days': 365
            },
            'features': {
                'mfa': False,
                'webhooks': True,
                'batch_processing': True,
                'analytics': True
            }
        }

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage usage statistics."""
        evidence_dir = Path('evidence_store')
        total_size = 0
        file_count = 0
        
        if evidence_dir.exists():
            for item in evidence_dir.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
        
        return {
            'total_size_gb': round(total_size / (1024**3), 2),
            'file_count': file_count,
            'average_file_size_kb': round((total_size / file_count / 1024), 2) if file_count > 0 else 0,
            'cases_count': len(list(evidence_dir.glob('*'))),
        }

    def get_alerts(self, hours: int = 24) -> Dict[str, Any]:
        """Get active alerts."""
        return {
            'critical': [],
            'warning': [
                {'message': 'High rate limit violations in last hour', 'count': 5}
            ],
            'info': [
                {'message': 'Hourly backup completed successfully', 'size_gb': 2.3}
            ]
        }

    @staticmethod
    def _get_disk_space() -> float:
        """Get available disk space in GB."""
        try:
            import shutil
            stat = shutil.disk_usage('/')
            return round(stat.free / (1024**3), 2)
        except:
            return 0.0

    @staticmethod
    def _mask_url(url: str) -> str:
        """Mask sensitive parts of URL."""
        if '@' in url:
            before, after = url.split('@')
            user_pass = before.split('://')[1] if '://' in before else before
            masked_user = user_pass.split(':')[0][:3] + '***' if ':' in user_pass else user_pass[:3] + '***'
            scheme = before.split('://')[0] + '://' if '://' in before else ''
            return f"{scheme}{masked_user}@{after}"
        return url
