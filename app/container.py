"""
Dependency Injection Container for Tracey's Sentinel
Centralizes service initialization and lifecycle management.
"""
from pathlib import Path
from typing import Optional

from app.analytics import AnalyticsEngine
from app.approval_workflow import ApprovalWorkflow
from app.audit_logger import AuditLogger
from app.batch_processor import BatchProcessor
from app.classifier import EvidenceClassifier
from app.compliance import ComplianceTracker
from app.config import get_settings, Settings
from app.evidence_crypto import EvidenceCipher
from app.ledger import Ledger
from app.metrics import MetricsCollector
from app.monitoring import SecurityMonitor
from app.organization import OrganizationManager
from app.rate_limiter import RateLimitStore
from app.reporting import build_case_audit_summary, build_court_report
from app.retention import RetentionManager
from app.search import SearchEngine
from app.storage import EvidenceStore
from app.webhooks import WebhookManager


class ServiceContainer:
    """
    Centralized dependency injection container for all services.
    Singleton pattern - one instance per application lifecycle.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._initialized = False
        self._instances = {}
    
    def _get_or_create(self, key: str, factory):
        """Lazy-load a singleton service."""
        if key not in self._instances:
            self._instances[key] = factory()
        return self._instances[key]
    
    @property
    def settings_obj(self) -> Settings:
        """Get settings."""
        return self.settings
    
    @property
    def store(self) -> EvidenceStore:
        """Get evidence storage."""
        return self._get_or_create("store", lambda: EvidenceStore(self.settings.db_path))
    
    @property
    def ledger(self) -> Ledger:
        """Get ledger."""
        return self._get_or_create(
            "ledger",
            lambda: Ledger(self.settings.ledger_path, base_dir=self.settings.base_dir)
        )
    
    @property
    def evidence_cipher(self) -> EvidenceCipher:
        """Get evidence encryption cipher."""
        return self._get_or_create(
            "evidence_cipher",
            lambda: EvidenceCipher(key_path=self.settings.evidence_key_path)
        )
    
    @property
    def compliance_tracker(self) -> ComplianceTracker:
        """Get compliance tracker."""
        return self._get_or_create(
            "compliance_tracker",
            lambda: ComplianceTracker(self.settings.db_path)
        )
    
    @property
    def security_monitor(self) -> SecurityMonitor:
        """Get security monitor."""
        return self._get_or_create(
            "security_monitor",
            lambda: SecurityMonitor(self.settings.db_path)
        )
    
    @property
    def audit_logger(self) -> AuditLogger:
        """Get audit logger."""
        return self._get_or_create(
            "audit_logger",
            lambda: AuditLogger(self.settings.db_path)
        )
    
    @property
    def search_engine(self) -> SearchEngine:
        """Get search engine."""
        return self._get_or_create(
            "search_engine",
            lambda: SearchEngine(self.settings.db_path)
        )
    
    @property
    def metrics_collector(self) -> MetricsCollector:
        """Get metrics collector."""
        return self._get_or_create(
            "metrics_collector",
            lambda: MetricsCollector(self.settings.db_path)
        )
    
    @property
    def rate_limit_store(self) -> RateLimitStore:
        """Get rate limiter."""
        return self._get_or_create(
            "rate_limit_store",
            lambda: RateLimitStore(self.settings.db_path)
        )
    
    @property
    def webhook_manager(self) -> WebhookManager:
        """Get webhook manager."""
        return self._get_or_create(
            "webhook_manager",
            lambda: WebhookManager(self.settings.db_path)
        )
    
    @property
    def classifier(self) -> EvidenceClassifier:
        """Get evidence classifier."""
        return self._get_or_create(
            "classifier",
            lambda: EvidenceClassifier(self.settings.db_path)
        )
    
    @property
    def batch_processor(self) -> BatchProcessor:
        """Get batch processor."""
        return self._get_or_create(
            "batch_processor",
            lambda: BatchProcessor(self.settings.db_path)
        )
    
    @property
    def approval_workflow(self) -> ApprovalWorkflow:
        """Get approval workflow."""
        return self._get_or_create(
            "approval_workflow",
            lambda: ApprovalWorkflow(self.settings.db_path)
        )
    
    @property
    def analytics_engine(self) -> AnalyticsEngine:
        """Get analytics engine."""
        return self._get_or_create(
            "analytics_engine",
            lambda: AnalyticsEngine(self.settings.db_path)
        )
    
    @property
    def retention_manager(self) -> RetentionManager:
        """Get retention manager."""
        return self._get_or_create(
            "retention_manager",
            lambda: RetentionManager(self.settings.db_path)
        )
    
    @property
    def organization_manager(self) -> OrganizationManager:
        """Get organization manager."""
        return self._get_or_create(
            "organization_manager",
            lambda: OrganizationManager(self.settings.db_path)
        )
    
    def initialize(self):
        """Initialize all critical services (call once at app startup)."""
        if self._initialized:
            return
        
        self.store.init()
        self._initialized = True
    
    def shutdown(self):
        """Cleanup all services (call at app shutdown)."""
        # Close DB connections if applicable
        self._instances.clear()
        self._initialized = False


# Global container instance
_container: Optional[ServiceContainer] = None


def get_container(settings: Optional[Settings] = None) -> ServiceContainer:
    """Get or create the global service container."""
    global _container
    if _container is None:
        _container = ServiceContainer(settings)
    return _container


def reset_container():
    """Reset the container (useful for testing)."""
    global _container
    if _container:
        _container.shutdown()
    _container = None
