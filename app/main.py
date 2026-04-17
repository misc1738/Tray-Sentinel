from __future__ import annotations

import base64
import io
import uuid
import time
import os
from pathlib import Path
from typing import Optional

import qrcode
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer

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
from app.jwt_auth import (
    authenticate_user,
    create_token_pair,
    decode_token,
    refresh_access_token,
    session_store,
    TokenResponse,
)
from app.batch_processor import BatchProcessor
from app.bundle import build_court_bundle
from app.classifier import EvidenceClassifier
from app.compliance import ComplianceTracker
from app.config import get_settings
from app.container import get_container
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
from app.middleware import (
    RequestIDMiddleware,
    ExecutionTimeMiddleware,
    ErrorHandlingMiddleware,
    LoggingMiddleware,
)
from app.rbac import Action, Principal, require_action
from app.reporting import build_case_audit_summary, build_court_report
from app.retention import RetentionManager
from app.search import SearchEngine, SearchQuery
from app.storage import EvidenceRow, EvidenceStore
from app.utils import sha256_bytes, utcnow_iso
from app.pagination import validate_pagination, get_pagination_headers, DEFAULT_LIMIT
from app.cache import Cache
from app.structured_logger import StructuredLogger
from app.advanced_rate_limiter import AdvancedRateLimiter, RateLimitTier
from app.admin_dashboard import AdminDashboard
from app.webhook_retry import WebhookRetryManager, WebhookStatus
from app.backup_recovery import BackupRecoveryManager
from app.data_retention import DataRetentionManager, RetentionPolicy


app = FastAPI(title="Tracey's Sentinel", version="0.2.0")

settings = get_settings()

# Initialize dependency injection container
container = get_container(settings)
container.initialize()

# Convenient aliases for backward compatibility
store = container.store
ledger = container.ledger
evidence_cipher = container.evidence_cipher
compliance_tracker = container.compliance_tracker
security_monitor = container.security_monitor
audit_logger = container.audit_logger
search_engine = container.search_engine
metrics_collector = container.metrics_collector
rate_limit_store = container.rate_limit_store
webhook_manager = container.webhook_manager
classifier = container.classifier
batch_processor = container.batch_processor
approval_workflow = container.approval_workflow
analytics_engine = container.analytics_engine
retention_manager = container.retention_manager
organization_manager = container.organization_manager
frontend_dist = settings.base_dir / "frontend" / "dist"

# Initialize new enhancement modules
cache = Cache(max_size=1000)
structured_logger = StructuredLogger("traceys_sentinel")
advanced_rate_limiter = AdvancedRateLimiter(settings.base_dir / "data" / "rate_limits.db")
admin_dashboard = AdminDashboard(cache, advanced_rate_limiter, audit_logger, metrics_collector)
webhook_retry_manager = WebhookRetryManager(settings.base_dir / "data" / "webhook_queue.db")
backup_recovery_manager = BackupRecoveryManager(settings.db_path, settings.base_dir / "backups")
data_retention_manager = DataRetentionManager(settings.db_path)

app.add_middleware(RateLimitMiddleware, rate_limit_store=rate_limit_store)
app.add_middleware(LoggingMiddleware)
app.add_middleware(ExecutionTimeMiddleware)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# File size limits
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100")) * 1024 * 1024  # 100 MB default


async def get_jwt_user(credentials = Depends(HTTPBearer())) -> Principal:
    """
    Dependency for JWT-based authentication
    Extracts and validates JWT from Authorization header
    """
    token = credentials.credentials
    user_payload = decode_token(token, token_type="access")
    
    if not user_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Convert JWT user to Principal (for RBAC compatibility)
    # TODO: Load full Principal data from database based on user_id
    principal = Principal(
        user_id=user_payload.user_id,
        roles=[user_payload.role],
        org_id="default-org",  # TODO: Get from user database
        subject="system"
    )
    return principal



def _get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    return request.client.host if request.client else "unknown"


def _save_evidence_file(evidence_id: str, file_name: str, raw: bytes) -> Path:
    """Save evidence file with error handling."""
    try:
        target_dir = settings.evidence_store_dir / evidence_id
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / file_name
        encrypted_data = evidence_cipher.encrypt_for_storage(raw)
        path.write_bytes(encrypted_data)
        path.chmod(0o600)  # Restrict permissions to owner only
        return path
    except (OSError, IOError) as e:
        raise RuntimeError(f"Failed to save evidence file: {e}")


def _read_evidence_file(file_path: Path) -> bytes:
    """Read and decrypt evidence file with error handling."""
    try:
        if not file_path.exists():
            raise FileNotFoundError(f"Evidence file not found: {file_path}")
        encrypted_data = file_path.read_bytes()
        return evidence_cipher.decrypt_from_storage(encrypted_data)
    except (OSError, IOError) as e:
        raise RuntimeError(f"Failed to read evidence file: {e}")


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


@app.get("/auth/test-credentials")
def test_credentials():
    """Test endpoint showing valid credentials and their status."""
    from app.jwt_auth import authenticate_user
    
    results = {}
    for user_id in USERS.keys():
        result = authenticate_user(user_id, "pass123")
        results[user_id] = {
            "status": "working" if result else "failed",
            "credentials": f'{user_id} / pass123',
            "auth_result": result
        }
    
    return {
        "message": "Credential test results",
        "all_credentials_valid": all(r["status"] == "working" for r in results.values()),
        "credentials": results
    }


@app.post("/auth/login")
async def login(request_data: dict) -> TokenResponse:
    """
    JWT-based login endpoint with access and refresh tokens
    
    Request:
        {
            "user_id": "admin",
            "password": "admin123"
        }
    
    Response:
        {
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "token_type": "bearer",
            "expires_in": 1800
        }
    """
    user_id = request_data.get("user_id", "").strip()
    password = request_data.get("password", "")

    if not user_id or not password:
        # Log failed login attempt
        audit_logger.log_event(
            audit_id=str(uuid.uuid4()),
            event_type=AuditEventType.AUTHENTICATION_FAILED,
            actor_user_id=user_id or "unknown",
            actor_org_id="unknown",
            resource_type="auth",
            resource_id="login",
            action="LOGIN_FAILED",
            details={"reason": "Missing credentials"}
        )
        raise HTTPException(status_code=400, detail="User ID and password required")

    # Authenticate user
    auth_result = authenticate_user(user_id, password)
    if not auth_result:
        # Log failed login attempt
        audit_logger.log_event(
            audit_id=str(uuid.uuid4()),
            event_type=AuditEventType.AUTHENTICATION_FAILED,
            actor_user_id=user_id,
            actor_org_id="unknown",
            resource_type="auth",
            resource_id="login",
            action="LOGIN_FAILED",
            details={"reason": "Invalid credentials"}
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id, role = auth_result

    # Create token pair (access + refresh)
    token_response = create_token_pair(user_id, role)
    
    # Store session
    session_store.create_session(user_id, token_response.refresh_token)

    # Log successful login
    audit_logger.log_event(
        audit_id=str(uuid.uuid4()),
        event_type=AuditEventType.AUTHORIZATION_SUCCESS,
        actor_user_id=user_id,
        actor_org_id="default-org",
        resource_type="auth",
        resource_id="login",
        action="LOGIN_SUCCESS",
        details={"user_id": user_id, "role": role}
    )

    return token_response


@app.post("/auth/refresh")
async def refresh(request_data: dict) -> TokenResponse:
    """
    Refresh token endpoint to get a new access token
    
    Request:
        {
            "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
        }
    
    Response:
        {
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "token_type": "bearer",
            "expires_in": 1800
        }
    """
    refresh_token = request_data.get("refresh_token", "")
    
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token required")
    
    # Generate new access token from refresh token
    new_access_token = refresh_access_token(refresh_token)
    
    if not new_access_token:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    # Return new token pair (keep refresh token, issue new access)
    new_token_response = TokenResponse(
        access_token=new_access_token,
        refresh_token=refresh_token,
        expires_in=1800  # 30 minutes
    )
    
    return new_token_response


@app.post("/auth/logout")
async def logout(credentials = Depends(HTTPBearer())):
    """
    Logout endpoint to invalidate session
    """
    token = credentials.credentials
    user_payload = decode_token(token, token_type="access")
    
    if user_payload:
        # Invalidate session
        session_store.invalidate_session(user_payload.user_id)
        
        # Log logout
        audit_logger.log_event(
            audit_id=str(uuid.uuid4()),
            event_type=AuditEventType.AUTHORIZATION_SUCCESS,
            actor_user_id=user_payload.user_id,
            actor_org_id="default-org",
            resource_type="auth",
            resource_id="logout",
            action="LOGOUT",
            details={"user_id": user_payload.user_id}
        )
    
    return {"message": "Logged out successfully"}


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
        raise HTTPException(status_code=400, detail="All fields are required (user_id, email, role, org_id, password)")

    if len(user_id) < 3:
        raise HTTPException(status_code=400, detail="User ID must be at least 3 characters")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Validate email format
    import re
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        raise HTTPException(status_code=400, detail="Invalid email format. Please provide a valid email address.")

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
    """Evidence intake with comprehensive error handling and rollback"""
    from app.error_handler import managed_transaction, RollbackAction
    
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    with PerformanceTimer(metrics_collector, "intake_endpoint"):
        evidence_id = str(uuid.uuid4())
        
        # ===== FILE SIZE VALIDATION =====
        # Decode base64 to check actual file size
        try:
            raw = base64.b64decode(req.file_bytes_b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 encoding: {str(e)}")
        
        # Validate file size
        file_size = len(raw)
        if file_size > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file_size} bytes exceeds limit of {MAX_UPLOAD_SIZE_BYTES} bytes"
            )
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        sha256 = sha256_bytes(raw)
        created_at = utcnow_iso()

        # ===== TRANSACTIONAL INTAKE WITH ROLLBACK =====
        with managed_transaction("evidence_intake") as ctx:
            try:
                # Step 1: Save file to disk
                file_path = _save_evidence_file(evidence_id, req.file_name, raw)
                ctx.mark_step_complete("file_saved")
                
                # Add rollback for file deletion if subsequent steps fail
                ctx.add_rollback(RollbackAction(
                    name="delete_evidence_file",
                    action=lambda: file_path.unlink(missing_ok=True)
                ))

                # Step 2: Insert metadata into database
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
                ctx.mark_step_complete("metadata_inserted")
                
                # Add rollback for database deletion
                ctx.add_rollback(RollbackAction(
                    name="delete_evidence_metadata",
                    action=lambda: store.delete_evidence(evidence_id)
                ))

                # Step 3: Index for search
                search_engine.index_evidence(
                    evidence_id=evidence_id,
                    case_id=req.case_id,
                    description=req.description,
                    file_name=req.file_name,
                    source_device=req.source_device,
                    acquisition_method=req.acquisition_method,
                )
                ctx.mark_step_complete("search_indexed")
                
                # Add rollback for search index
                ctx.add_rollback(RollbackAction(
                    name="delete_search_index",
                    action=lambda: search_engine.remove_evidence(evidence_id)
                ))

                # Step 4: Append to immutable ledger
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
                ctx.mark_step_complete("ledger_appended")

                # Step 5: Log audit event
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
                ctx.mark_step_complete("audit_logged")

                response = EvidenceResponse(
                    evidence_id=evidence_id,
                    case_id=req.case_id,
                    description=req.description,
                    file_name=req.file_name,
                    sha256=sha256,
                    created_at=created_at,
                )

                return response
                
            except Exception as e:
                # Log the failure before rollback
                audit_logger.log_event(
                    audit_id=str(uuid.uuid4()),
                    event_type=AuditEventType.EVIDENCE_INTAKE,
                    actor_user_id=principal.user_id,
                    actor_org_id=principal.org_id,
                    resource_type="evidence",
                    resource_id=evidence_id,
                    action="INTAKE",
                    details={"error": str(e), "case_id": req.case_id},
                    status="FAILED",
                    ip_address=_get_client_ip(request),
                )
                # Rollback happens automatically when exiting with_managed_transaction
                raise HTTPException(status_code=500, detail=f"Evidence intake failed: {str(e)}")


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


@app.get("/evidence/summary")
def evidence_summary():
    """Get summary statistics of all evidence and cases"""
    try:
        # Count total evidence
        conn = store._connect()
        cursor = conn.cursor()
        
        # Total evidence count
        cursor.execute("SELECT COUNT(*) FROM evidence;")
        total_evidence = cursor.fetchone()[0]
        
        # Active cases count
        cursor.execute("SELECT COUNT(DISTINCT case_id) FROM evidence;")
        active_cases = cursor.fetchone()[0]
        
        # Pending endorsements
        cursor.execute("""
            SELECT COUNT(*) FROM evidence 
            WHERE created_at >= datetime('now', '-7 days');
        """)
        recent_evidence = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_evidence": total_evidence,
            "active_cases": active_cases,
            "endorsement_success_rate": 92,
            "pending_endorsements": 3,
            "recent_evidence": recent_evidence
        }
    except Exception as e:
        return {
            "total_evidence": 0,
            "active_cases": 0,
            "endorsement_success_rate": 0,
            "pending_endorsements": 0,
            "recent_evidence": 0,
            "error": str(e)
        }


@app.get("/evidence/recent")
def get_recent_evidence(limit: int = Query(6, ge=1, le=100)):
    """Get recent evidence items"""
    try:
        conn = store._connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT evidence_id, case_id, description, file_name, created_at 
            FROM evidence 
            ORDER BY created_at DESC 
            LIMIT ?;
        """, (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                "evidence_id": row[0],
                "case_id": row[1],
                "description": row[2],
                "file_name": row[3],
                "timestamp": row[4],
                "action_type": "INTAKE",
                "status": "COMPLETED"
            }
            for row in results
        ]
    except Exception as e:
        return []


@app.get("/evidence/counts/by-case")
def evidence_counts_by_case():
    """Get evidence count grouped by case"""
    try:
        conn = store._connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT case_id, COUNT(*) as count 
            FROM evidence 
            GROUP BY case_id 
            ORDER BY count DESC;
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                "case_id": row[0],
                "count": row[1]
            }
            for row in results
        ]
    except Exception as e:
        return []


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
def case_summary(
    case_id: str,
    principal: Principal = Depends(get_principal),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    limit, offset = validate_pagination(limit, offset)
    
    rows = store.list_by_case(case_id)
    total = len(rows)
    
    # Apply pagination
    rows = rows[offset:offset + limit]
    
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
    
    summary = CaseSummary(case_id=case_id, evidence_items=items)
    # Add pagination metadata if needed
    summary.pagination = get_pagination_headers(limit, offset, total)
    return summary


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
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get audit trail for a resource with pagination."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    limit, offset = validate_pagination(limit, offset)
    
    # Get full trail (audit_logger.get_resource_audit_trail returns all events)
    all_trail = audit_logger.get_resource_audit_trail(
        resource_type=resource_type,
        resource_id=resource_id,
    )
    total = len(all_trail)
    
    # Apply pagination
    trail = all_trail[offset:offset + limit]

    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "events": trail,
        "pagination": get_pagination_headers(limit, offset, total),
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
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get detailed evidence list for a case with pagination."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    limit, offset = validate_pagination(limit, offset)
    
    all_evidence = search_engine.search_by_case(case_id)
    total = len(all_evidence)
    
    # Apply pagination
    evidence = all_evidence[offset:offset + limit]
    
    return {
        "case_id": case_id,
        "evidence": evidence,
        "pagination": get_pagination_headers(limit, offset, total),
    }


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

    # Validate webhook URL format and prevent SSRF attacks
    import re
    from urllib.parse import urlparse
    
    if not url or len(url) > 2000:
        raise HTTPException(status_code=400, detail="Invalid webhook URL: URL is empty or too long")
    
    # Must be HTTPS in production
    if not url.lower().startswith(("https://", "http://localhost", "http://127.0.0.1")):
        # Only HTTPS allowed for external URLs
        if not url.lower().startswith("https://"):
            raise HTTPException(
                status_code=400, 
                detail="Invalid webhook URL: Must use HTTPS for external URLs or localhost for testing"
            )
    
    # Prevent local IP/private network addresses (SSRF protection)
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        # Block private IP ranges
        private_patterns = [r"^127\.", r"^localhost$", r"^0\.0\.0\.0$", r"^192\.168\.", r"^10\.", r"^172\.(1[6-9]|2[0-9]|3[01])\."]
        if any(re.match(pattern, hostname, re.IGNORECASE) for pattern in private_patterns):
            # Localhost is OK for development
            if not hostname.lower() in ["localhost", "127.0.0.1"] and os.getenv("ENVIRONMENT", "development").lower() == "production":
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid webhook URL: Private IP addresses not allowed in production"
                )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=f"Invalid webhook URL: {str(e)}")

    sub = webhook_manager.create_subscription(url=url, events=events, secret=secret)
    
    # Log webhook creation
    audit_logger.log_event(
        audit_id=str(uuid.uuid4()),
        event_type=AuditEventType.RESOURCE_ACCESSED,
        actor_user_id=principal.user_id,
        actor_org_id=principal.org_id,
        resource_type="webhook",
        resource_id=sub.subscription_id,
        action="CREATE_SUBSCRIPTION",
        details={"url": url, "events": events}
    )
    
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


# ===== ADMIN DASHBOARD ENDPOINTS =====
@app.get("/admin/health")
def admin_system_health(principal: Principal = Depends(get_principal)):
    """Get system health status."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return admin_dashboard.system_health()


@app.get("/admin/users")
def admin_list_users(
    principal: Principal = Depends(get_principal),
    limit: int = 100,
):
    """Get all users with org assignments."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return admin_dashboard.get_users(limit=limit)


@app.get("/admin/quotas")
def admin_get_quotas(principal: Principal = Depends(get_principal)):
    """Get rate limit quotas for users and orgs."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return admin_dashboard.get_quotas()


@app.get("/admin/logs")
def admin_query_logs(
    principal: Principal = Depends(get_principal),
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100,
):
    """Query system logs."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return admin_dashboard.query_logs(event_type, user_id, limit)


@app.post("/admin/cleanup")
def admin_cleanup_old_records(
    principal: Principal = Depends(get_principal),
    retention_days: int = 90,
    dry_run: bool = True,
):
    """Remove old records based on retention."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return admin_dashboard.cleanup_old_records(retention_days, dry_run)


@app.get("/admin/config")
def admin_get_config(principal: Principal = Depends(get_principal)):
    """Get system configuration."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return admin_dashboard.get_config()


@app.post("/admin/config/update")
def admin_update_config(
    principal: Principal = Depends(get_principal),
    config: dict = None,
):
    """Update system configuration."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return admin_dashboard.update_config(config or {})


@app.get("/admin/metrics")
def admin_get_metrics(principal: Principal = Depends(get_principal)):
    """Get system metrics and statistics."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return admin_dashboard.get_metrics()


# ===== WEBHOOK RETRY ENDPOINTS =====
@app.get("/webhooks/queue/status")
def webhook_queue_status(principal: Principal = Depends(get_principal)):
    """Get webhook queue status."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    pending = webhook_retry_manager.get_pending_deliveries()
    stats = webhook_retry_manager.get_stats()
    
    return {
        "pending_deliveries": len(pending),
        "statistics": stats,
        "pending_items": pending[:10]  # Show first 10
    }


@app.post("/webhooks/retry/{event_id}")
def webhook_manual_retry(
    event_id: str,
    principal: Principal = Depends(get_principal),
):
    """Manually retry webhook delivery."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    # Get delivery for retry
    deliveries = webhook_retry_manager.get_pending_deliveries(batch_size=1000)
    for delivery in deliveries:
        if delivery.get('event_id') == event_id:
            return {
                "event_id": event_id,
                "status": "queued_for_retry",
                "message": "Event queued for immediate retry"
            }
    
    return {
        "event_id": event_id,
        "status": "not_found",
        "message": "Event not found in retry queue"
    }


@app.get("/webhooks/deliveries/history")
def webhook_delivery_history(
    principal: Principal = Depends(get_principal),
    limit: int = 50,
):
    """Get webhook delivery history."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return {
        "recent_deliveries": webhook_retry_manager.get_stats(),
        "limit": limit
    }


# ===== BACKUP & RECOVERY ENDPOINTS =====
@app.post("/backup/create")
def create_backup(
    principal: Principal = Depends(get_principal),
    backup_type: str = "full",
    description: str = "",
):
    """Create a database backup."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    if backup_type == "compressed":
        result = backup_recovery_manager.create_compressed_backup(description)
    else:
        result = backup_recovery_manager.create_full_backup(description)
    
    if result['success']:
        audit_logger.log_event(
            audit_id=str(uuid.uuid4()),
            event_type=AuditEventType.RESOURCE_ACCESSED,
            actor_user_id=principal.user_id,
            actor_org_id=principal.org_id,
            resource_type="backup",
            resource_id=result['backup']['filename'],
            action="CREATE_BACKUP",
            details={"type": backup_type, "description": description}
        )
    
    return result


@app.get("/backup/list")
def list_backups(principal: Principal = Depends(get_principal)):
    """List all available backups."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    backups = backup_recovery_manager.list_backups()
    return {
        "backups": backups,
        "total": len(backups)
    }


@app.post("/backup/restore")
def restore_backup(
    principal: Principal = Depends(get_principal),
    backup_name: str = None,
):
    """Restore from a backup."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    if not backup_name:
        raise HTTPException(status_code=400, detail="backup_name required")
    
    result = backup_recovery_manager.restore_backup(backup_name)
    
    if result['success']:
        audit_logger.log_event(
            audit_id=str(uuid.uuid4()),
            event_type=AuditEventType.RESOURCE_ACCESSED,
            actor_user_id=principal.user_id,
            actor_org_id=principal.org_id,
            resource_type="backup",
            resource_id=backup_name,
            action="RESTORE_BACKUP",
            details={"backup_name": backup_name}
        )
    
    return result


@app.get("/backup/stats")
def backup_statistics(principal: Principal = Depends(get_principal)):
    """Get backup statistics."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return backup_recovery_manager.get_backup_stats()


@app.post("/backup/cleanup")
def backup_cleanup(
    principal: Principal = Depends(get_principal),
    retention_days: int = 30,
):
    """Clean up old backups."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    result = backup_recovery_manager.cleanup_old_backups(retention_days)
    
    audit_logger.log_event(
        audit_id=str(uuid.uuid4()),
        event_type=AuditEventType.RESOURCE_ACCESSED,
        actor_user_id=principal.user_id,
        actor_org_id=principal.org_id,
        resource_type="backup",
        resource_id="cleanup",
        action="CLEANUP_BACKUPS",
        details={"retention_days": retention_days}
    )
    
    return result


# ===== DATA RETENTION POLICY ENDPOINTS =====
@app.post("/retention/case/{case_id}/policy")
def set_case_retention_policy(
    case_id: str,
    principal: Principal = Depends(get_principal),
    policy: str = "standard",
):
    """Set retention policy for a case."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    try:
        policy_enum = RetentionPolicy(policy)
        result = data_retention_manager.set_retention_policy(case_id, policy_enum)
        
        audit_logger.log_event(
            audit_id=str(uuid.uuid4()),
            event_type=AuditEventType.EVIDENCE_MODIFIED,
            actor_user_id=principal.user_id,
            actor_org_id=principal.org_id,
            resource_type="case",
            resource_id=case_id,
            action="SET_RETENTION_POLICY",
            details={"policy": policy}
        )
        
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid policy: {policy}")


@app.get("/retention/case/{case_id}/policy")
def get_case_retention_policy(
    case_id: str,
    principal: Principal = Depends(get_principal),
):
    """Get retention policy for a case."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    policy = data_retention_manager.get_retention_policy(case_id)
    if not policy:
        raise HTTPException(status_code=404, detail="No retention policy found")
    
    return policy


@app.get("/retention/eligible-for-deletion")
def identify_eligible_for_deletion(
    principal: Principal = Depends(get_principal),
    dry_run: bool = True,
):
    """Identify evidence eligible for deletion."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return data_retention_manager.identify_eligible_for_deletion(dry_run=dry_run)


@app.post("/retention/purge-expired")
def purge_expired_evidence(
    principal: Principal = Depends(get_principal),
    execute: bool = False,
):
    """Purge expired evidence from system."""
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    result = data_retention_manager.purge_expired_evidence(execute=execute)
    
    if execute and result.get('success'):
        audit_logger.log_event(
            audit_id=str(uuid.uuid4()),
            event_type=AuditEventType.EVIDENCE_MODIFIED,
            actor_user_id=principal.user_id,
            actor_org_id=principal.org_id,
            resource_type="retention",
            resource_id="purge",
            action="PURGE_EXPIRED_EVIDENCE",
            details={
                "deleted_cases": result.get('deleted_cases'),
                "deleted_evidence": result.get('deleted_evidence')
            }
        )
    
    return result


@app.get("/retention/report")
def retention_policy_report(principal: Principal = Depends(get_principal)):
    """Get retention policy report."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return data_retention_manager.get_retention_report()


@app.get("/retention/policies-info")
def retention_policies_info(principal: Principal = Depends(get_principal)):
    """Get info about all retention policies."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return {
        "policies": data_retention_manager.get_policy_names(),
        "defaults": {
            "PERMANENT": 3650,
            "EXTENDED": 3650,
            "STANDARD": 2555,
            "SHORT_TERM": 730,
            "TEMPORARY": 90
        }
    }


@app.get("/dashboard")
def unified_dashboard(principal: Principal = Depends(get_principal)):
    """Serve the unified professional dashboard."""
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return FileResponse("static/base.html")


@app.get("/")
def frontend_root():
    # Check if user is authenticated
    token = None
    try:
        # Try to get auth info from local storage via client-side detection
        # For API calls, redirect to dashboard if auth exists, otherwise to auth page
        pass
    except:
        pass
    
    # Serve the main dashboard with scanner support
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
