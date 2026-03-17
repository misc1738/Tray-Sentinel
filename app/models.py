from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


ActionType = Literal[
    "INTAKE",
    "TRANSFER",
    "ACCESS",
    "ANALYSIS",
    "STORAGE",
    "COURT_SUBMISSION",
    "ENDORSE",
]


class EvidenceIntakeRequest(BaseModel):
    case_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_device: Optional[str] = None
    acquisition_method: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    file_bytes_b64: str = Field(min_length=1)


class EvidenceResponse(BaseModel):
    evidence_id: str
    case_id: str
    description: str
    file_name: str
    sha256: str
    created_at: str


class CustodyEventRequest(BaseModel):
    evidence_id: str = Field(min_length=1)
    action_type: ActionType
    details: dict[str, Any] = Field(default_factory=dict)
    presented_sha256: Optional[str] = None
    endorse: bool = False


class CustodyEventResponse(BaseModel):
    tx_id: str
    evidence_id: str
    action_type: ActionType
    required_endorser_orgs: int = 1
    endorser_org_ids: list[str] = Field(default_factory=list)
    unique_endorser_orgs: int = 0
    actor_user_id: str
    actor_role: str
    actor_org_id: str
    timestamp: str
    presented_sha256: Optional[str]
    expected_sha256: str
    integrity_ok: bool
    endorsement_status: str
    signer_pubkey_b64: str = ""
    signature_b64: str = ""
    record_hash: str = ""
    prev_hash: str = ""


class TimelineResponse(BaseModel):
    evidence_id: str
    expected_sha256: str
    events: list[CustodyEventResponse]


class VerifyResponse(BaseModel):
    evidence_id: str
    expected_sha256: str
    actual_sha256: str
    integrity_ok: bool


class ReportResponse(BaseModel):
    evidence_id: str
    generated_at: str
    report: dict[str, Any]


class EndorseRequest(BaseModel):
    evidence_id: str = Field(min_length=1)
    tx_id: str = Field(min_length=1)


class EndorseResponse(BaseModel):
    tx_id: str
    endorsed_tx_id: str
    evidence_id: str
    endorser_user_id: str
    endorser_role: str
    endorser_org_id: str
    timestamp: str


class CaseSummary(BaseModel):
    case_id: str
    evidence_items: list[EvidenceResponse]


class EvidenceAuditItem(BaseModel):
    evidence_id: str
    file_name: str
    expected_sha256: str
    event_count: int
    last_event_at: Optional[str] = None
    integrity_failures: int
    pending_endorsements: int
    compliance_status: Literal["COMPLIANT", "ATTENTION_REQUIRED"]


class CaseAuditResponse(BaseModel):
    case_id: str
    generated_at: str
    chain_valid: bool
    chain_message: str
    evidence_count: int
    total_events: int
    integrity_failures: int
    pending_endorsements: int
    compliant_evidence_count: int
    evidence_audits: list[EvidenceAuditItem]


# ===== COMPLIANCE FRAMEWORK MODELS =====
class ComplianceFramework(BaseModel):
    """Supported compliance frameworks"""
    framework_id: str  # ISO27001, SOC2, HIPAA, PCIDSS
    name: str
    description: str
    total_controls: int
    icon: str


class ComplianceControl(BaseModel):
    """Individual control within a framework"""
    control_id: str
    framework_id: str
    title: str
    description: str
    status: Literal["PASSING", "FAILING", "NEEDS_CHANGES", "IN_REVIEW", "PENDING"]
    evidence_count: int
    last_assessed: Optional[str] = None


class ComplianceStatus(BaseModel):
    """Overall compliance posture"""
    framework_id: str
    name: str
    total_controls: int
    passing_controls: int
    failing_controls: int
    needs_changes: int
    compliance_percentage: float
    last_updated: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class ComplianceDashboard(BaseModel):
    """Aggregate compliance dashboard"""
    generated_at: str
    overall_compliance: float
    frameworks: list[ComplianceStatus]
    critical_findings: int
    passing_controls: int
    total_controls: int
    trend: Literal["IMPROVING", "STABLE", "DECLINING"]


# ===== SECURITY METRICS & MONITORING =====
class SecurityAlert(BaseModel):
    """Security alert/incident"""
    alert_id: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    alert_type: str  # integrity_violation, unauthorized_access, chain_break, etc
    title: str
    description: str
    evidence_id: Optional[str] = None
    case_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_org_id: Optional[str] = None
    timestamp: str
    status: Literal["OPEN", "ACKNOWLEDGED", "RESOLVED", "FALSE_POSITIVE"]
    resolved_at: Optional[str] = None


class SecurityMetrics(BaseModel):
    """Security KPIs and metrics"""
    total_alerts: int
    critical_alerts: int
    high_alerts: int
    open_alerts: int
    resolved_alerts: int
    false_positives: int
    integrity_violations: int
    unauthorized_access_attempts: int
    chain_break_incidents: int
    avg_resolution_time_hours: float
    mttr: float  # Mean Time To Resolution


class IncidentResponse(BaseModel):
    """Incident details"""
    incident_id: str
    alert_id: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    title: str
    description: str
    root_cause: Optional[str] = None
    remediation_steps: list[str] = []
    timestamp: str
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None
    assigned_to: Optional[str] = None


class AccessLog(BaseModel):
    """Audit log for access and operations"""
    log_id: str
    user_id: str
    action: str
    resource_type: str  # evidence, case, report, etc
    resource_id: str
    timestamp: str
    status: Literal["SUCCESS", "FAILURE", "DENIED"]
    ip_address: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class SecurityPosture(BaseModel):
    """Overall security posture"""
    generated_at: str
    overall_risk: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    encryption_status: str
    key_rotation: str
    access_control_violations: int
    chain_integrity_violations: int
    compliance_score: float
    incident_response_time_avg: float


class MonitoringDashboard(BaseModel):
    """Real-time monitoring dashboard"""
    generated_at: str
    active_sessions: int
    total_alerts_today: int
    critical_incidents: int
    uptime_percentage: float
    last_backup: str
    chain_validity: bool
    evidence_integrity_ok: bool
    recent_alerts: list[SecurityAlert]
    metrics: SecurityMetrics
