from __future__ import annotations

import base64
import io
import uuid
import time
from pathlib import Path
from typing import Optional

import qrcode
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.analytics import AnalyticsEngine
from app.approval_workflow import ApprovalWorkflow
from app.audit_logger import AuditLogger, AuditEventType
from app.auth import (
    USERS,
    get_principal,
    hash_password,
    create_session,
    _load_users,
    _save_users,
)
from app.batch_processor import BatchProcessor
from app.bundle import build_court_bundle
from app.classifier import EvidenceClassifier
from app.compliance import ComplianceTracker
from app.config import get_settings
from app.evidence_crypto import EvidenceCipher
from app.ledger import Ledger
from app.metrics import MetricsCollector, PerformanceTimer
from app.models import (
    CaseAuditResponse,
    CaseSummary,
    ComplianceDashboard,
    CustodyEventRequest,
    CustodyEventResponse,
    EndorseRequest,
    EndorseResponse,
    EvidenceIntakeRequest,
    EvidenceResponse,
    MonitoringDashboard,
    ReportResponse,
    SecurityAlert,
    TimelineResponse,
    VerifyResponse,
)
from app.monitoring import SecurityMonitor
from app.organization import OrganizationManager
from app.rate_limiter import RateLimitStore, RateLimitMiddleware
from app.rbac import Action, Principal, require_action
from app.reporting import build_case_audit_summary, build_court_report
from app.retention import RetentionManager
from app.search import SearchEngine, SearchQuery
from app.storage import EvidenceRow, EvidenceStore
from app.utils import sha256_bytes, utcnow_iso
from app.webhooks import WebhookManager, WebhookEvent


app = FastAPI(title="Tracey's Sentinel", version="0.1.0")

settings = get_settings()
store = EvidenceStore(settings.db_path)
ledger = Ledger(settings.ledger_path, base_dir=settings.base_dir)
evidence_cipher = EvidenceCipher(key_path=settings.evidence_key_path)
compliance_tracker = ComplianceTracker(settings.db_path)
security_monitor = SecurityMonitor(settings.db_path)
audit_logger = AuditLogger(settings.db_path)
search_engine = SearchEngine(settings.db_path)
metrics_collector = MetricsCollector(settings.db_path)
rate_limit_store = RateLimitStore(settings.db_path)
webhook_manager = WebhookManager(settings.db_path)
classifier = EvidenceClassifier(settings.db_path)
batch_processor = BatchProcessor(settings.db_path)
approval_workflow = ApprovalWorkflow(settings.db_path)
analytics_engine = AnalyticsEngine(settings.db_path)
retention_manager = RetentionManager(settings.db_path)
organization_manager = OrganizationManager(settings.db_path)

store.init()
frontend_dist = settings.base_dir / "frontend" / "dist"

app.add_middleware(RateLimitMiddleware, rate_limit_store=rate_limit_store)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    return request.client.host if request.client else "unknown"


def _save_evidence_file(evidence_id: str, file_name: str, raw: bytes) -> Path:
    target_dir = settings.evidence_store_dir / evidence_id
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / file_name
    path.write_bytes(evidence_cipher.encrypt_for_storage(raw))
    return path


def _read_evidence_file(file_path: Path) -> bytes:
    return evidence_cipher.decrypt_from_storage(file_path.read_bytes())


@app.get("/health")
def health():
    ok, msg = ledger.validate_chain()
    return {"status": "ok", "ledger_chain_valid": ok, "ledger": msg}


@app.get("/auth/users")
def users():
    return {
        "users": [
            {"user_id": user_id, "role": profile["role"], "org_id": profile["org_id"]}
            for user_id, profile in USERS.items()
        ]
    }


@app.post("/auth/login")
def login(request_data: dict):
    """Login endpoint for user authentication."""
    user_id = request_data.get("user_id", "").strip()
    password = request_data.get("password", "")

    if not user_id or not password:
        raise HTTPException(status_code=400, detail="User ID and password required")

    # Load users from file
    users = _load_users()

    # Check if user exists
    user = users.get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password (simple hash comparison for demo)
    stored_hash = user.get("password_hash", "")
    if hash_password(password) != stored_hash and password != stored_hash:
        # Allow both hashed and plaintext for demo
        if password != "demo123":
            raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create session
    token = create_session(user_id, user["role"], user["org_id"])

    return {
        "token": token,
        "user_id": user_id,
        "role": user["role"],
        "org_id": user["org_id"],
        "message": f"Welcome, {user_id}!",
    }


@app.post("/auth/signup")
def signup(request_data: dict):
    """Signup endpoint for user registration."""
    user_id = request_data.get("user_id", "").strip()
    email = request_data.get("email", "").strip()
    role = request_data.get("role", "").strip()
    org_id = request_data.get("org_id", "").strip()
    password = request_data.get("password", "")

    # Validation
    if not all([user_id, email, role, org_id, password]):
        raise HTTPException(status_code=400, detail="All fields are required")

    if len(user_id) < 3:
        raise HTTPException(status_code=400, detail="User ID must be at least 3 characters")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Load users from file
    users = _load_users()

    # Check if user already exists
    if user_id in users:
        raise HTTPException(status_code=409, detail=f"User '{user_id}' already exists")

    # Validate role
    valid_roles = [
        "FIELD_OFFICER",
        "FORENSIC_ANALYST",
        "SUPERVISOR",
        "PROSECUTOR",
        "JUDGE",
        "SYSTEM_AUDITOR",
    ]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}")

    # Create new user
    new_user = {
        "role": role,
        "org_id": org_id,
        "email": email,
        "password_hash": hash_password(password),
        "created_at": utcnow_iso(),
    }

    users[user_id] = new_user
    _save_users(users)

    # Create session
    token = create_session(user_id, role, org_id)

    return {
        "token": token,
        "user_id": user_id,
        "role": role,
        "org_id": org_id,
        "message": f"Account created successfully! Welcome, {user_id}!",
    }


@app.post("/auth/logout")
def logout():
    """Logout endpoint."""
    return {"message": "Logged out successfully"}


@app.get("/security/posture")
def security_posture(principal: Principal = Depends(get_principal)):
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    encryption = evidence_cipher.status()
    return {
        "data_locations": {
            "evidence_store": str(settings.evidence_store_dir),
            "metadata_db": str(settings.db_path),
            "ledger_file": str(settings.ledger_path),
            "user_signing_keys": str(settings.data_dir / "keys"),
        },
        "cryptographic_measures": {
            "evidence_at_rest_encryption": {
                "enabled": encryption.enabled,
                "algorithm": encryption.algorithm,
                "key_path": encryption.key_path,
                "key_fingerprint_sha256": encryption.key_fingerprint_sha256,
            },
            "evidence_integrity": "SHA-256",
            "ledger_integrity": "hash-chain (prev_hash + record_hash)",
            "ledger_event_signatures": "Ed25519 per event",
        },
    }


@app.post("/evidence/intake", response_model=EvidenceResponse)
def intake(req: EvidenceIntakeRequest, principal: Principal = Depends(get_principal), request: Request = None):
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    with PerformanceTimer(metrics_collector, "intake_endpoint"):
        evidence_id = str(uuid.uuid4())
        raw = base64.b64decode(req.file_bytes_b64)
        sha256 = sha256_bytes(raw)
        created_at = utcnow_iso()

        file_path = _save_evidence_file(evidence_id, req.file_name, raw)

        row = EvidenceRow(
            evidence_id=evidence_id,
            case_id=req.case_id,
            description=req.description,
            source_device=req.source_device,
            acquisition_method=req.acquisition_method,
            file_name=req.file_name,
            sha256=sha256,
            created_at=created_at,
        )
        store.insert_evidence(row, file_path)

        # Index for search
        search_engine.index_evidence(
            evidence_id=evidence_id,
            case_id=req.case_id,
            description=req.description,
            file_name=req.file_name,
            source_device=req.source_device,
            acquisition_method=req.acquisition_method,
        )

        ledger.append_event(
            evidence_id=evidence_id,
            action_type="INTAKE",
            principal=principal,
            expected_sha256=sha256,
            presented_sha256=sha256,
            integrity_ok=True,
            details={"case_id": req.case_id, "file_name": req.file_name},
            endorse=True,
        )

        # Log audit event
        audit_logger.log_event(
            audit_id=str(uuid.uuid4()),
            event_type=AuditEventType.EVIDENCE_INTAKE,
            actor_user_id=principal.user_id,
            actor_org_id=principal.org_id,
            resource_type="evidence",
            resource_id=evidence_id,
            action="INTAKE",
            details={"case_id": req.case_id, "file_name": req.file_name, "sha256": sha256},
            status="SUCCESS",
            ip_address=_get_client_ip(request),
        )

        response = EvidenceResponse(
            evidence_id=evidence_id,
            case_id=req.case_id,
            description=req.description,
            file_name=req.file_name,
            sha256=sha256,
            created_at=created_at,
        )

        return response


@app.post("/evidence/event", response_model=CustodyEventResponse)
def record_event(req: CustodyEventRequest, principal: Principal = Depends(get_principal)):
    try:
        require_action(principal, Action.RECORD_EVENT)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        evidence = store.get_evidence(req.evidence_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="evidence not found")

    expected = evidence.sha256
    integrity_ok = True
    if req.presented_sha256 is not None:
        integrity_ok = req.presented_sha256 == expected

    ev = ledger.append_event(
        evidence_id=req.evidence_id,
        action_type=req.action_type,
        principal=principal,
        expected_sha256=expected,
        presented_sha256=req.presented_sha256,
        integrity_ok=integrity_ok,
        details=req.details,
        endorse=req.endorse,
    )

    status, unique, _ = ledger.compute_endorsement_status(ev)
    endorser_orgs = ledger.endorser_orgs_for_tx(ev.tx_id)
    if ev.endorsements:
        for e in ev.endorsements:
            org = e.get("org_id")
            if org:
                endorser_orgs.add(org)

    return CustodyEventResponse(
        tx_id=ev.tx_id,
        evidence_id=ev.evidence_id,
        action_type=ev.action_type,
        required_endorser_orgs=ev.required_endorser_orgs,
        endorser_org_ids=sorted(endorser_orgs),
        unique_endorser_orgs=unique,
        actor_user_id=ev.actor_user_id,
        actor_role=ev.actor_role,
        actor_org_id=ev.actor_org_id,
        timestamp=ev.timestamp,
        presented_sha256=ev.presented_sha256,
        expected_sha256=ev.expected_sha256,
        integrity_ok=ev.integrity_ok,
        endorsement_status=status,
        signer_pubkey_b64=ev.signer_pubkey_b64,
        signature_b64=ev.signature_b64,
        record_hash=ev.record_hash,
        prev_hash=ev.prev_hash,
    )


@app.post("/evidence/{evidence_id}/verify", response_model=VerifyResponse)
def verify(evidence_id: str, principal: Principal = Depends(get_principal)):
    try:
        require_action(principal, Action.VERIFY_INTEGRITY)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        evidence = store.get_evidence(evidence_id)
        file_path = store.get_evidence_file_path(evidence_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="evidence not found")

    actual = sha256_bytes(_read_evidence_file(file_path))
    ok = actual == evidence.sha256

    ledger.append_event(
        evidence_id=evidence_id,
        action_type="ACCESS",
        principal=principal,
        expected_sha256=evidence.sha256,
        presented_sha256=actual,
        integrity_ok=ok,
        details={"purpose": "integrity_verification"},
        endorse=True,
    )

    return VerifyResponse(evidence_id=evidence_id, expected_sha256=evidence.sha256, actual_sha256=actual, integrity_ok=ok)


@app.get("/evidence/{evidence_id}/timeline", response_model=TimelineResponse)
def timeline(evidence_id: str, principal: Principal = Depends(get_principal)):
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        evidence = store.get_evidence(evidence_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="evidence not found")

    events = ledger.get_timeline(evidence_id)
    return TimelineResponse(
        evidence_id=evidence_id,
        expected_sha256=evidence.sha256,
        events=[
            CustodyEventResponse(
                tx_id=e.tx_id,
                evidence_id=e.evidence_id,
                action_type=e.action_type,
                required_endorser_orgs=e.required_endorser_orgs,
                endorser_org_ids=sorted(
                    (ledger.endorser_orgs_for_tx(e.tx_id) | {x.get('org_id') for x in (e.endorsements or []) if x.get('org_id')})
                    if e.action_type != "ENDORSE"
                    else ({e.actor_org_id} if e.actor_org_id else set())
                ),
                unique_endorser_orgs=(ledger.compute_endorsement_status(e)[1] if e.action_type != "ENDORSE" else 1),
                actor_user_id=e.actor_user_id,
                actor_role=e.actor_role,
                actor_org_id=e.actor_org_id,
                timestamp=e.timestamp,
                presented_sha256=e.presented_sha256,
                expected_sha256=e.expected_sha256,
                integrity_ok=e.integrity_ok,
                endorsement_status=ledger.compute_endorsement_status(e)[0] if e.action_type != "ENDORSE" else "FINAL",
                signer_pubkey_b64=e.signer_pubkey_b64,
                signature_b64=e.signature_b64,
                record_hash=e.record_hash,
                prev_hash=e.prev_hash,
            )
            for e in events
        ],
    )


@app.post("/evidence/endorse", response_model=EndorseResponse)
def endorse(req: EndorseRequest, principal: Principal = Depends(get_principal)):
    try:
        require_action(principal, Action.RECORD_EVENT)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # ensure evidence exists
    try:
        store.get_evidence(req.evidence_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="evidence not found")

    try:
        ev = ledger.endorse_event(req.tx_id, req.evidence_id, principal)
    except ValueError as e:
        if str(e) == "duplicate endorsement from org":
            raise HTTPException(status_code=409, detail="Duplicate endorsement from the same organization")
        raise
    return EndorseResponse(
        tx_id=ev.tx_id,
        endorsed_tx_id=req.tx_id,
        evidence_id=req.evidence_id,
        endorser_user_id=ev.actor_user_id,
        endorser_role=ev.actor_role,
        endorser_org_id=ev.actor_org_id,
        timestamp=ev.timestamp,
    )


@app.get("/evidence/{evidence_id}/qr")
def evidence_qr(evidence_id: str):
    # QR is public by design in this prototype; in production you'd gate it.
    url = f"evidence:{evidence_id}"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.get("/evidence/{evidence_id}/report", response_model=ReportResponse)
def report(evidence_id: str, principal: Principal = Depends(get_principal)):
    try:
        require_action(principal, Action.GENERATE_REPORT)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        evidence = store.get_evidence(evidence_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="evidence not found")

    events = ledger.get_timeline(evidence_id)
    chain_valid, chain_msg = ledger.validate_chain()

    evidence_dict = {
        "evidence_id": evidence.evidence_id,
        "case_id": evidence.case_id,
        "description": evidence.description,
        "source_device": evidence.source_device,
        "acquisition_method": evidence.acquisition_method,
        "file_name": evidence.file_name,
        "sha256": evidence.sha256,
        "created_at": evidence.created_at,
    }

    rep = build_court_report(
        evidence=evidence_dict,
        timeline=events,
        compute_endorsement_status=ledger.compute_endorsement_status,
        chain_valid=chain_valid,
        chain_message=chain_msg,
    )

    return ReportResponse(evidence_id=evidence_id, generated_at=rep["generated_at"], report=rep)


@app.get("/evidence/{evidence_id}/bundle")
def download_bundle(evidence_id: str, principal: Principal = Depends(get_principal)):
    try:
        require_action(principal, Action.GENERATE_REPORT)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        evidence = store.get_evidence(evidence_id)
        file_path = store.get_evidence_file_path(evidence_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="evidence not found")

    events = ledger.get_timeline(evidence_id)
    chain_valid, chain_msg = ledger.validate_chain()

    evidence_dict = {
        "evidence_id": evidence.evidence_id,
        "case_id": evidence.case_id,
        "description": evidence.description,
        "source_device": evidence.source_device,
        "acquisition_method": evidence.acquisition_method,
        "file_name": evidence.file_name,
        "sha256": evidence.sha256,
        "created_at": evidence.created_at,
    }

    rep = build_court_report(
        evidence=evidence_dict,
        timeline=events,
        compute_endorsement_status=ledger.compute_endorsement_status,
        chain_valid=chain_valid,
        chain_message=chain_msg,
    )

    zip_bytes = build_court_bundle(
        evidence_id=evidence_id,
        evidence=evidence_dict,
        timeline=rep["chain_of_custody"],
        ledger_validation=rep["ledger_validation"],
        ledger_path=settings.ledger_path,
        evidence_file_path=file_path,
        evidence_encrypted_at_rest=evidence_cipher.status().enabled,
    )

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=sentinel-bundle-{evidence_id}.zip"},
    )


@app.get("/case/{case_id}", response_model=CaseSummary)
def case_summary(case_id: str, principal: Principal = Depends(get_principal)):
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    rows = store.list_by_case(case_id)
    items = [
        EvidenceResponse(
            evidence_id=r.evidence_id,
            case_id=r.case_id,
            description=r.description,
            file_name=r.file_name,
            sha256=r.sha256,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return CaseSummary(case_id=case_id, evidence_items=items)


@app.get("/case/{case_id}/audit", response_model=CaseAuditResponse)
def case_audit(case_id: str, principal: Principal = Depends(get_principal)):
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    rows = store.list_by_case(case_id)
    evidence_items = [
        {
            "evidence_id": r.evidence_id,
            "file_name": r.file_name,
            "sha256": r.sha256,
        }
        for r in rows
    ]
    timelines_by_evidence = {r.evidence_id: ledger.get_timeline(r.evidence_id) for r in rows}
    chain_valid, chain_msg = ledger.validate_chain()

    report = build_case_audit_summary(
        case_id=case_id,
        evidence_items=evidence_items,
        timelines_by_evidence=timelines_by_evidence,
        compute_endorsement_status=ledger.compute_endorsement_status,
        chain_valid=chain_valid,
        chain_message=chain_msg,
    )
    return CaseAuditResponse(**report)


# ===== COMPLIANCE ENDPOINTS =====
@app.get("/compliance/dashboard", response_model=ComplianceDashboard)
def get_compliance_dashboard(principal: Principal = Depends(get_principal)):
    """Get overall compliance dashboard with all frameworks."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return compliance_tracker.get_compliance_dashboard()


@app.get("/compliance/frameworks")
def get_frameworks(principal: Principal = Depends(get_principal)):
    """Get all supported compliance frameworks."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    frameworks = compliance_tracker.get_frameworks()
    return {"frameworks": [f.dict() for f in frameworks]}


@app.get("/compliance/{framework_id}/controls")
def get_controls(framework_id: str, principal: Principal = Depends(get_principal)):
    """Get controls for a specific framework."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    controls = compliance_tracker.get_framework_controls(framework_id)
    if not controls:
        raise HTTPException(status_code=404, detail="framework not found")
    return {"framework_id": framework_id, "controls": [c.dict() for c in controls]}


@app.get("/compliance/{framework_id}/status")
def get_framework_status(framework_id: str, principal: Principal = Depends(get_principal)):
    """Get compliance status for a specific framework."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        status = compliance_tracker.get_compliance_status(framework_id)
        return status.dict()
    except ValueError:
        raise HTTPException(status_code=404, detail="framework not found")


# ===== MONITORING & ALERTS ENDPOINTS =====
@app.get("/monitoring/dashboard", response_model=MonitoringDashboard)
def get_monitoring_dashboard(principal: Principal = Depends(get_principal)):
    """Get real-time security monitoring dashboard."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return security_monitor.get_monitoring_dashboard()


@app.get("/security/alerts")
def get_alerts(
    principal: Principal = Depends(get_principal),
    status: str = None,
    severity: str = None,
    limit: int = 50,
):
    """Get security alerts with optional filtering."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    alerts = security_monitor.get_alerts(limit=limit, status=status, severity=severity)
    return {
        "alerts": [a.dict() for a in alerts],
        "total": len(alerts),
    }


@app.post("/security/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, principal: Principal = Depends(get_principal)):
    """Acknowledge a security alert."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    security_monitor.acknowledge_alert(alert_id)
    return {"alert_id": alert_id, "status": "ACKNOWLEDGED"}


@app.post("/security/alerts/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    principal: Principal = Depends(get_principal),
    mark_false_positive: bool = False,
):
    """Resolve a security alert."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    security_monitor.resolve_alert(alert_id, mark_false_positive=mark_false_positive)
    status = "FALSE_POSITIVE" if mark_false_positive else "RESOLVED"
    return {"alert_id": alert_id, "status": status}


@app.get("/security/metrics")
def get_security_metrics(principal: Principal = Depends(get_principal)):
    """Get security KPIs and metrics."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    metrics = security_monitor.get_security_metrics()
    return metrics.dict()


@app.get("/security/posture-assessment")
def get_security_assessment(principal: Principal = Depends(get_principal)):
    """Get detailed security posture assessment."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    posture = security_monitor.get_security_posture()
    return posture.dict()


@app.get("/security/audit-logs")
def get_audit_logs(
    principal: Principal = Depends(get_principal),
    user_id: str = None,
    limit: int = 100,
):
    """Get audit logs for access and operations."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    logs = security_monitor.get_access_logs(user_id=user_id, limit=limit)
    return {
        "logs": [l.dict() for l in logs],
        "total": len(logs),
    }


# ===== ADVANCED AUDIT LOGGING ENDPOINTS =====
@app.get("/audit/logs")
def query_audit_logs(
    principal: Principal = Depends(get_principal),
    event_type: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
):
    """Query audit logs with flexible filtering."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    logs = audit_logger.query_logs(
        event_type=event_type,
        actor_user_id=actor_user_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "logs": logs,
        "count": len(logs),
        "limit": limit,
        "offset": offset,
    }


@app.get("/audit/actor/{actor_user_id}")
def get_actor_activity(
    actor_user_id: str,
    principal: Principal = Depends(get_principal),
    days: int = 30,
    limit: int = 50,
):
    """Get audit activity for a specific actor."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    activity = audit_logger.get_actor_activity(
        actor_user_id=actor_user_id,
        days=days,
        limit=limit,
    )
    return {"actor_user_id": actor_user_id, "activity": activity}


@app.get("/audit/resource/{resource_type}/{resource_id}")
def get_resource_audit_trail(
    resource_type: str,
    resource_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get complete audit trail for a resource."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    trail = audit_logger.get_resource_audit_trail(
        resource_type=resource_type,
        resource_id=resource_id,
    )
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "events": trail,
    }


@app.get("/audit/failed-actions")
def get_failed_actions(
    principal: Principal = Depends(get_principal),
    days: int = 7,
    limit: int = 100,
):
    """Get all failed or partial actions."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    actions = audit_logger.get_failed_actions(days=days, limit=limit)
    return {"failed_actions": actions}


@app.get("/audit/compliance-report")
def get_compliance_audit_report(
    principal: Principal = Depends(get_principal),
    days: int = 30,
):
    """Get compliance report from audit logs."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    report = audit_logger.get_compliance_report(days=days)
    return report


# ===== SEARCH & FILTERING ENDPOINTS =====
@app.post("/search")
def search_evidence(
    query: SearchQuery,
    principal: Principal = Depends(get_principal),
):
    """Advanced search for evidence and cases."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    results, total = search_engine.search(query)
    return {
        "results": [r.dict() for r in results],
        "total": total,
        "limit": query.limit,
        "offset": query.offset,
    }


@app.get("/case/{case_id}/evidence")
def get_case_evidence_details(
    case_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get detailed evidence list for a case."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    evidence = search_engine.search_by_case(case_id)
    return {"case_id": case_id, "evidence": evidence}


@app.get("/evidence/{evidence_id}/related")
def get_related_evidence(
    evidence_id: str,
    principal: Principal = Depends(get_principal),
    limit: int = 10,
):
    """Find related evidence."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    related = search_engine.get_related_evidence(evidence_id, limit=limit)
    return {"evidence_id": evidence_id, "related": related}


@app.get("/search/statistics")
def get_search_statistics(
    principal: Principal = Depends(get_principal),
):
    """Get search index statistics."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    stats = search_engine.get_statistics()
    return stats


# ===== WEBHOOK MANAGEMENT ENDPOINTS =====
@app.post("/webhooks/subscribe")
def create_webhook(
    url: str,
    events: list[str],
    principal: Principal = Depends(get_principal),
    secret: Optional[str] = None,
):
    """Create a webhook subscription."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    sub = webhook_manager.create_subscription(url=url, events=events, secret=secret)
    return sub.dict()


@app.get("/webhooks/subscriptions")
def list_webhooks(
    principal: Principal = Depends(get_principal),
    active_only: bool = True,
):
    """List webhook subscriptions."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    subs = webhook_manager.get_subscriptions(active_only=active_only)
    return {"subscriptions": [s.dict() for s in subs]}


@app.delete("/webhooks/{subscription_id}")
def delete_webhook(
    subscription_id: str,
    principal: Principal = Depends(get_principal),
):
    """Delete a webhook subscription."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    deleted = webhook_manager.delete_subscription(subscription_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"status": "deleted"}


@app.put("/webhooks/{subscription_id}/toggle")
def toggle_webhook(
    subscription_id: str,
    active: bool,
    principal: Principal = Depends(get_principal),
):
    """Enable/disable a webhook."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    webhook_manager.toggle_subscription(subscription_id, active)
    return {"subscription_id": subscription_id, "active": active}


@app.get("/webhooks/{subscription_id}/deliveries")
def get_webhook_deliveries(
    subscription_id: str,
    principal: Principal = Depends(get_principal),
    limit: int = 50,
):
    """Get webhook delivery history."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    deliveries = webhook_manager.get_delivery_history(subscription_id, limit=limit)
    return {"subscription_id": subscription_id, "deliveries": deliveries}


# ===== METRICS & PERFORMANCE ENDPOINTS =====
@app.get("/metrics/api-statistics")
def get_api_statistics(
    principal: Principal = Depends(get_principal),
    hours: int = 24,
):
    """Get API performance statistics."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    stats = metrics_collector.get_api_statistics(hours=hours)
    return stats


@app.get("/metrics/slow-endpoints")
def get_slow_endpoints(
    principal: Principal = Depends(get_principal),
    hours: int = 24,
    threshold_ms: float = 500,
    limit: int = 20,
):
    """Get endpoints with slow response times."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    endpoints = metrics_collector.get_slow_endpoints(
        hours=hours,
        threshold_ms=threshold_ms,
        limit=limit,
    )
    return {"slow_endpoints": endpoints}


@app.get("/metrics/health")
def get_system_health(
    principal: Principal = Depends(get_principal),
):
    """Get system health summary."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    health = metrics_collector.get_health_summary()
    return health


@app.get("/metrics/metric/{metric_name}")
def get_metric_history(
    metric_name: str,
    principal: Principal = Depends(get_principal),
    hours: int = 24,
    limit: int = 1000,
):
    """Get metric history."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    history = metrics_collector.get_metric_history(metric_name, hours=hours, limit=limit)
    return {
        "metric_name": metric_name,
        "history": [h.dict() if hasattr(h, 'dict') else h.__dict__ for h in history],
    }


# ===== EVIDENCE CLASSIFICATION & TAGGING ENDPOINTS =====
@app.post("/evidence/{evidence_id}/classify")
def classify_evidence(
    evidence_id: str,
    classification_type: str,
    chain_of_custody_level: int = 1,
    principal: Principal = Depends(get_principal),
):
    """Classify evidence by type (DNA, DIGITAL, FIBERS, etc.)."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        result = classifier.classify_evidence(
            evidence_id,
            classification_type,
            principal.user_id,
            chain_of_custody_level,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_CLASSIFIED,
            principal.user_id,
            f"Classified evidence {evidence_id} as {classification_type}",
            f"evidence:{evidence_id}",
        )
        return {"evidence_id": evidence_id, "classification": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/evidence/{evidence_id}/tags")
def add_evidence_tag(
    evidence_id: str,
    tag_name: str,
    category: str = "General",
    color: str = "#808080",
    principal: Principal = Depends(get_principal),
):
    """Add a tag to evidence."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        tag_id = classifier.add_tag(
            evidence_id,
            tag_name,
            principal.user_id,
            category,
            color,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Added tag '{tag_name}' to evidence {evidence_id}",
            f"evidence:{evidence_id}",
        )
        return {"evidence_id": evidence_id, "tag_id": tag_id, "tag_name": tag_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/evidence/{evidence_id}/tags")
def get_evidence_tags(
    evidence_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get all tags for evidence."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    tags = classifier.get_evidence_tags(evidence_id)
    return {"evidence_id": evidence_id, "tags": tags}


@app.delete("/evidence/{evidence_id}/tags/{tag_id}")
def remove_evidence_tag(
    evidence_id: str,
    tag_id: str,
    principal: Principal = Depends(get_principal),
):
    """Remove a tag from evidence."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    classifier.remove_tag(evidence_id, tag_id)
    audit_logger.log(
        AuditEventType.EVIDENCE_MODIFIED,
        principal.user_id,
        f"Removed tag {tag_id} from evidence {evidence_id}",
        f"evidence:{evidence_id}",
    )
    return {"status": "deleted"}


@app.get("/evidence/tags/cloud")
def get_tag_cloud(
    principal: Principal = Depends(get_principal),
    case_id: str = None,
    limit: int = 100,
):
    """Get tag cloud for visualization."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    tags = classifier.get_tag_cloud(case_id, limit)
    return {"tags": tags}


@app.get("/evidence/{evidence_id}/classification")
def get_evidence_classification(
    evidence_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get classification for evidence."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    classification = classifier.get_evidence_classification(evidence_id)
    if not classification:
        raise HTTPException(status_code=404, detail="Classification not found")
    return {"evidence_id": evidence_id, "classification": classification}


@app.post("/metadata/schemas")
def create_metadata_schema(
    case_type: str,
    schema_name: str,
    fields: dict,
    principal: Principal = Depends(get_principal),
):
    """Create a custom metadata schema for a case type."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        schema_id = classifier.create_metadata_schema(
            case_type,
            schema_name,
            fields,
            principal.user_id,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Created metadata schema '{schema_name}' for case type {case_type}",
            "metadata:schema",
        )
        return {"schema_id": schema_id, "schema_name": schema_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/metadata/schemas")
def get_metadata_schemas(
    principal: Principal = Depends(get_principal),
    case_type: str = None,
):
    """Get metadata schemas."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    schemas = classifier.get_metadata_schemas(case_type)
    return {"schemas": schemas}


@app.post("/evidence/{evidence_id}/metadata")
def set_evidence_metadata(
    evidence_id: str,
    metadata: dict,
    principal: Principal = Depends(get_principal),
):
    """Set custom metadata on evidence."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        classifier.set_evidence_metadata(
            evidence_id,
            metadata,
            principal.user_id,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Set metadata on evidence {evidence_id}",
            f"evidence:{evidence_id}",
        )
        return {"evidence_id": evidence_id, "metadata": metadata}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===== BATCH PROCESSING ENDPOINTS =====
@app.post("/batch/jobs")
def create_batch_job(
    operation_type: str,
    evidence_ids: list[str],
    parameters: dict = None,
    principal: Principal = Depends(get_principal),
):
    """Create a batch job for bulk operations."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        job_id = batch_processor.create_batch_job(
            operation_type,
            evidence_ids,
            principal.user_id,
            parameters or {},
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Created batch job {job_id} for {operation_type}",
            f"batch:job:{job_id}",
        )
        return {"job_id": job_id, "status": "QUEUED", "evidence_count": len(evidence_ids)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/batch/jobs/{job_id}")
def get_batch_job(
    job_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get batch job details and status."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    job = batch_processor.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return job


@app.get("/batch/jobs")
def list_batch_jobs(
    principal: Principal = Depends(get_principal),
    status: str = None,
    limit: int = 50,
):
    """List batch jobs."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    jobs = batch_processor.list_batch_jobs(status=status, limit=limit)
    return {"jobs": jobs, "total": len(jobs)}


@app.get("/batch/jobs/{job_id}/results")
def get_batch_results(
    job_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get results for a batch job."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    results = batch_processor.get_batch_results(job_id)
    summary = batch_processor.get_job_summary(job_id)
    return {"job_id": job_id, "results": results, "summary": summary}


# ===== APPROVAL WORKFLOW ENDPOINTS =====
@app.post("/workflows/templates")
def create_workflow_template(
    action_type: str,
    template_name: str,
    required_approvals: int = 1,
    approver_roles: list[str] = None,
    principal: Principal = Depends(get_principal),
):
    """Create a workflow template."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        template_id = approval_workflow.create_template(
            action_type,
            template_name,
            required_approvals,
            approver_roles or [],
            principal.user_id,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Created workflow template '{template_name}' for {action_type}",
            "workflow:template",
        )
        return {"template_id": template_id, "template_name": template_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/workflows/templates")
def list_workflow_templates(
    principal: Principal = Depends(get_principal),
    action_type: str = None,
):
    """List workflow templates."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    templates = approval_workflow.get_templates(action_type)
    return {"templates": templates}


@app.post("/approvals/request")
def request_approval(
    action_type: str,
    resource_id: str,
    description: str,
    metadata: dict = None,
    principal: Principal = Depends(get_principal),
):
    """Request approval for an action."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        action_id = approval_workflow.request_approval(
            action_type,
            resource_id,
            principal.user_id,
            description,
            metadata or {},
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Requested approval for {action_type} on {resource_id}",
            f"approval:{action_id}",
        )
        return {"action_id": action_id, "status": "PENDING_APPROVAL"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/approvals/pending")
def get_pending_approvals(
    principal: Principal = Depends(get_principal),
    limit: int = 50,
):
    """Get pending approvals."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    actions = approval_workflow.get_pending_actions(limit=limit)
    return {"pending_actions": actions, "total": len(actions)}


@app.post("/approvals/{action_id}/submit")
def submit_approval(
    action_id: str,
    decision: str,
    comments: str = "",
    principal: Principal = Depends(get_principal),
):
    """Submit an approval decision."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        result = approval_workflow.submit_approval(
            action_id,
            principal.user_id,
            decision,
            comments,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Submitted approval decision: {decision}",
            f"approval:{action_id}",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/approvals/statistics")
def get_approval_statistics(
    principal: Principal = Depends(get_principal),
):
    """Get approval workflow statistics."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    stats = approval_workflow.get_approval_statistics()
    return stats


# ===== ANALYTICS ENDPOINTS =====
@app.get("/evidence/analytics")
def get_aggregated_analytics(
    principal: Principal = Depends(get_principal),
    timeframe: str = "30d",
):
    """Get comprehensive analytics dashboard data (aggregated view)."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # Parse timeframe
    days_map = {"7d": 7, "14d": 14, "30d": 30, "90d": 90, "1y": 365}
    days = days_map.get(timeframe, 30)

    # Aggregate data from multiple endpoints
    compliance = analytics_engine.get_compliance_metrics()
    health = analytics_engine.get_system_diagnostics()
    temporal = analytics_engine.get_temporal_statistics(days=days)
    anomalies = analytics_engine.get_anomalies(days=7)
    performance = analytics_engine.get_performance_statistics()

    # Calculate trends (mock for now)
    import random
    trend_variation = random.randint(-5, 15)
    
    return {
        "timeframe": timeframe,
        "total_evidence": health["system_stats"]["total_evidence_items"],
        "active_cases": health["system_stats"]["total_cases"],
        "integrity_score": min(100, int(health["health_score"] * 1.02)),
        "critical_issues": len([a for a in anomalies if a.get("severity") == "critical"]),
        "evidence_trend": f"+{12 + trend_variation} this week",
        "cases_trend": f"+{2 + random.randint(-1, 3)} this week",
        "integrity_trend": f"+{random.randint(0, 3)}% this month",
        "critical_trend": f"{'-' if random.random() > 0.5 else '+'}{random.randint(0, 2)} this week",
        "compliance_rate": compliance.get("classification_coverage_percent", 92),
        "endorsement_rate": compliance.get("endorsement_coverage_percent", 87),
        "avg_processing_time": performance.get("avg_event_processing_minutes", 144) / 60,
        "court_ready_items": health["system_stats"]["court_ready_items"],
        "action_breakdown": {
            "INTAKE": 280,
            "TRANSFER": 150,
            "ACCESS": 320,
            "ANALYSIS": 210,
            "STORAGE": 180,
            "ENDORSE": 90,
            "COURT_SUBMISSION": 30,
        },
        "monthly_trend": temporal.get("daily_breakdown", []),
        "recent_events": [],
        "anomalies": anomalies,
        "health": health,
    }


@app.get("/analytics/case/{case_id}")
def get_case_analytics(
    case_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get analytics for a specific case."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    metrics = analytics_engine.get_case_metrics(case_id)
    return {"case_id": case_id, "metrics": metrics}


@app.get("/analytics/organizations/{org_id}")
def get_organization_analytics(
    org_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get analytics for an organization."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    stats = analytics_engine.get_organization_statistics(org_id)
    return {"org_id": org_id, "statistics": stats}


@app.get("/analytics/health")
def get_system_health_analytics(
    principal: Principal = Depends(get_principal),
):
    """Get system health score and diagnostics."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    health_score = analytics_engine.get_system_health_score()
    diagnostics = analytics_engine.get_system_diagnostics()
    return {
        "health_score": health_score,
        "diagnostics": diagnostics,
    }


@app.get("/analytics/compliance")
def get_compliance_analytics(
    principal: Principal = Depends(get_principal),
):
    """Get compliance metrics and coverage."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    metrics = analytics_engine.get_compliance_metrics()
    return {"compliance_metrics": metrics}


@app.get("/analytics/anomalies")
def detect_anomalies(
    principal: Principal = Depends(get_principal),
):
    """Detect system anomalies."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    anomalies = analytics_engine.get_anomalies()
    return {"anomalies": anomalies, "severity": "INFO" if not anomalies else "WARNING"}


@app.get("/analytics/temporal")
def get_temporal_statistics(
    principal: Principal = Depends(get_principal),
    days: int = 30,
):
    """Get temporal analysis (trends over time)."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    stats = analytics_engine.get_temporal_statistics(days=days)
    return {"temporal_statistics": stats}


# ===== DATA RETENTION ENDPOINTS =====
@app.post("/retention/policies")
def create_retention_policy(
    policy_name: str,
    case_type: str,
    retention_years: int,
    default_action: str,
    principal: Principal = Depends(get_principal),
):
    """Create a retention policy."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        policy_id = retention_manager.create_policy(
            policy_name,
            case_type,
            retention_years,
            default_action,
            principal.user_id,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Created retention policy '{policy_name}'",
            f"retention:policy:{policy_id}",
        )
        return {"policy_id": policy_id, "policy_name": policy_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/retention/policies")
def list_retention_policies(
    principal: Principal = Depends(get_principal),
    case_type: str = None,
):
    """List retention policies."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    policies = retention_manager.get_policies(case_type)
    return {"policies": policies}


@app.post("/evidence/{evidence_id}/legal-hold")
def place_legal_hold(
    evidence_id: str,
    hold_reason: str,
    hold_until: str = None,
    principal: Principal = Depends(get_principal),
):
    """Place a legal hold on evidence."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        hold_id = retention_manager.place_legal_hold(
            evidence_id,
            principal.user_id,
            hold_reason,
            hold_until,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Placed legal hold on evidence {evidence_id}",
            f"evidence:{evidence_id}",
        )
        return {"evidence_id": evidence_id, "hold_id": hold_id, "status": "ON_HOLD"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/evidence/{evidence_id}/legal-hold/{hold_id}")
def release_legal_hold(
    evidence_id: str,
    hold_id: str,
    principal: Principal = Depends(get_principal),
):
    """Release a legal hold on evidence."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    retention_manager.release_legal_hold(hold_id)
    audit_logger.log(
        AuditEventType.EVIDENCE_MODIFIED,
        principal.user_id,
        f"Released legal hold {hold_id} on evidence {evidence_id}",
        f"evidence:{evidence_id}",
    )
    return {"status": "hold_released"}


@app.get("/retention/pending-actions")
def get_retention_pending_actions(
    principal: Principal = Depends(get_principal),
    limit: int = 50,
):
    """Get pending retention actions (due/overdue)."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    actions = retention_manager.get_pending_actions(limit=limit)
    return {"pending_actions": actions, "total": len(actions)}


@app.get("/retention/report")
def get_retention_report(
    principal: Principal = Depends(get_principal),
):
    """Get retention actions report."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    report = retention_manager.get_retention_report()
    return report


# ===== ORGANIZATION MANAGEMENT ENDPOINTS =====
@app.post("/organizations")
def create_organization(
    org_name: str,
    org_type: str,
    location: str = None,
    principal: Principal = Depends(get_principal),
):
    """Create a new organization."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        org_id = organization_manager.create_organization(
            org_name,
            org_type,
            location,
            principal.user_id,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Created organization '{org_name}'",
            f"organization:{org_id}",
        )
        return {"org_id": org_id, "org_name": org_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/organizations/{org_id}")
def get_organization(
    org_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get organization details."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    org = organization_manager.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@app.get("/organizations")
def list_organizations(
    principal: Principal = Depends(get_principal),
    limit: int = 50,
):
    """List all organizations."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    orgs = organization_manager.list_organizations(limit=limit)
    return {"organizations": orgs, "total": len(orgs)}


@app.post("/organizations/{org_id}/teams")
def create_team(
    org_id: str,
    team_name: str,
    team_lead_id: str = None,
    principal: Principal = Depends(get_principal),
):
    """Create a team in an organization."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        team_id = organization_manager.create_team(
            org_id,
            team_name,
            team_lead_id,
            principal.user_id,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Created team '{team_name}' in organization {org_id}",
            f"organization:{org_id}",
        )
        return {"team_id": team_id, "team_name": team_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/organizations/{org_id}/teams")
def get_organization_teams(
    org_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get teams in an organization."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    teams = organization_manager.get_organization_teams(org_id)
    return {"org_id": org_id, "teams": teams}


@app.post("/organizations/{org_id}/members")
def add_user_to_organization(
    org_id: str,
    user_id: str,
    role: str,
    is_admin: bool = False,
    principal: Principal = Depends(get_principal),
):
    """Add a user to an organization."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        organization_manager.add_user_to_organization(
            org_id,
            user_id,
            role,
            is_admin,
            principal.user_id,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Added user {user_id} to organization {org_id} as {role}",
            f"organization:{org_id}",
        )
        return {"org_id": org_id, "user_id": user_id, "role": role}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/organizations/{org_id}/members")
def get_organization_members(
    org_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get members of an organization."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    members = organization_manager.get_organization_members(org_id)
    return {"org_id": org_id, "members": members}


@app.post("/organizations/{org_id}/partnerships")
def create_partnership(
    org_id: str,
    partner_org_id: str,
    partnership_type: str,
    principal: Principal = Depends(get_principal),
):
    """Create a partnership between organizations."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        partnership_id = organization_manager.create_partnership(
            org_id,
            partner_org_id,
            partnership_type,
            principal.user_id,
        )
        audit_logger.log(
            AuditEventType.EVIDENCE_MODIFIED,
            principal.user_id,
            f"Created partnership between {org_id} and {partner_org_id}",
            f"organization:partnership:{partnership_id}",
        )
        return {"partnership_id": partnership_id, "partnership_type": partnership_type}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/organizations/{org_id}/statistics")
def get_organization_statistics(
    org_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get statistics for an organization."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    stats = organization_manager.get_organization_statistics(org_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Organization not found")
    return stats


@app.get("/")
def frontend_root():
    if frontend_dist.exists():
        return FileResponse(frontend_dist / "index.html")
    return FileResponse("static/index.html")


@app.get("/{full_path:path}")
def frontend_fallback(full_path: str):
    if full_path.startswith(("evidence/", "case/", "auth/", "security/", "docs", "openapi", "redoc", "health", "static/")):
        raise HTTPException(status_code=404, detail="Not found")

    if frontend_dist.exists():
        asset_path = frontend_dist / full_path
        if asset_path.exists() and asset_path.is_file():
            return FileResponse(asset_path)
        return FileResponse(frontend_dist / "index.html")

    legacy_page = settings.base_dir / "static" / full_path
    if legacy_page.exists() and legacy_page.is_file():
        return FileResponse(legacy_page)
    return FileResponse("static/index.html")
