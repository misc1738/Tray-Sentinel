"""
Evidence Service - Refactored business logic layer
This demonstrates how to separate concerns from main.py endpoints

This is a template showing the recommended refactoring of main.py into services.
Each service encapsulates a domain: EvidenceService, AuditService, ComplianceService, etc.

USAGE:
Instead of:
    @app.post("/evidence/intake")
    def intake(req: EvidenceIntakeRequest, ...):
        # 100+ lines of mixed concerns

Use:
    evidence_service = EvidenceService(store, ledger, search_engine, audit_logger)
    
    @app.post("/evidence/intake")
    def intake(req: EvidenceIntakeRequest, principal: Principal = Depends(get_jwt_user)):
        return evidence_service.intake(req, principal)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import uuid
import base64

from app.models import EvidenceIntakeRequest, EvidenceResponse
from app.rbac import Principal, Action, require_action
from app.storage import EvidenceStore, EvidenceRow
from app.ledger import Ledger
from app.search import SearchEngine
from app.audit_logger import AuditLogger, AuditEventType
from app.error_handler import managed_transaction, RollbackAction
from app.utils import sha256_bytes, utcnow_iso
from fastapi import HTTPException


class EvidenceService:
    """
    Service layer for evidence management
    Encapsulates all evidence-related business logic
    
    Benefits:
    - Separation of concerns (business logic ≠ HTTP layer)
    - Easier testing (can mock dependencies)
    - Reusable across multiple endpoints
    - Transaction management in one place
    """
    
    def __init__(
        self,
        store: EvidenceStore,
        ledger: Ledger,
        search_engine: SearchEngine,
        audit_logger: AuditLogger,
        evidence_cipher=None,
        settings=None,
    ):
        self.store = store
        self.ledger = ledger
        self.search_engine = search_engine
        self.audit_logger = audit_logger
        self.evidence_cipher = evidence_cipher
        self.settings = settings
        
        # Configuration
        self.max_file_size = 100 * 1024 * 1024  # 100 MB default
    
    def intake(
        self,
        req: EvidenceIntakeRequest,
        principal: Principal,
        client_ip: str = "unknown"
    ) -> EvidenceResponse:
        """
        Register evidence into chain of custody
        Handles: validation, storage, indexing, ledger, audit
        
        Raises:
            HTTPException: For validation or processing errors
        """
        # Authorization check
        try:
            require_action(principal, Action.REGISTER_EVIDENCE)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        
        # Input validation
        self._validate_intake_request(req)
        
        # Decode and validate file
        try:
            raw = base64.b64decode(req.file_bytes_b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64: {str(e)}")
        
        if len(raw) > self.max_file_size:
            raise HTTPException(status_code=413, detail="File exceeds size limit")
        
        if len(raw) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Compute hash
        sha256 = sha256_bytes(raw)
        
        # Multi-step intake with transactional rollback
        with managed_transaction("evidence_intake") as ctx:
            try:
                evidence_id = str(uuid.uuid4())
                created_at = utcnow_iso()
                
                # Step 1: Save file
                file_path = self._save_file(evidence_id, req.file_name, raw)
                ctx.mark_step_complete("file_saved")
                ctx.add_rollback(RollbackAction(
                    "delete_file",
                    lambda: file_path.unlink(missing_ok=True)
                ))
                
                # Step 2: Insert metadata
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
                self.store.insert_evidence(row, file_path)
                ctx.mark_step_complete("metadata_inserted")
                ctx.add_rollback(RollbackAction(
                    "delete_metadata",
                    lambda: self.store.delete_evidence(evidence_id)
                ))
                
                # Step 3: Index for search
                self.search_engine.index_evidence(
                    evidence_id=evidence_id,
                    case_id=req.case_id,
                    description=req.description,
                    file_name=req.file_name,
                    source_device=req.source_device,
                    acquisition_method=req.acquisition_method,
                )
                ctx.mark_step_complete("search_indexed")
                ctx.add_rollback(RollbackAction(
                    "delete_search",
                    lambda: self.search_engine.remove_evidence(evidence_id)
                ))
                
                # Step 4: Append to ledger
                self.ledger.append_event(
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
                
                # Step 5: Audit log
                self.audit_logger.log_event(
                    audit_id=str(uuid.uuid4()),
                    event_type=AuditEventType.EVIDENCE_INTAKE,
                    actor_user_id=principal.user_id,
                    actor_org_id=principal.org_id,
                    resource_type="evidence",
                    resource_id=evidence_id,
                    action="INTAKE",
                    details={
                        "case_id": req.case_id,
                        "file_name": req.file_name,
                        "sha256": sha256
                    },
                    status="SUCCESS",
                    ip_address=client_ip,
                )
                ctx.mark_step_complete("audit_logged")
                
                return EvidenceResponse(
                    evidence_id=evidence_id,
                    case_id=req.case_id,
                    description=req.description,
                    file_name=req.file_name,
                    sha256=sha256,
                    created_at=created_at,
                )
                
            except Exception as e:
                # Log failure
                self.audit_logger.log_event(
                    audit_id=str(uuid.uuid4()),
                    event_type=AuditEventType.EVIDENCE_INTAKE,
                    actor_user_id=principal.user_id,
                    actor_org_id=principal.org_id,
                    resource_type="evidence",
                    resource_id=getattr(evidence_id, "id", "unknown"),
                    action="INTAKE",
                    details={"error": str(e)},
                    status="FAILED",
                    ip_address=client_ip,
                )
                raise HTTPException(status_code=500, detail=f"Intake failed: {str(e)}")
    
    def _validate_intake_request(self, req: EvidenceIntakeRequest) -> None:
        """Validate evidence intake request"""
        if not req.case_id or not req.case_id.strip():
            raise HTTPException(status_code=400, detail="case_id is required")
        
        if not req.file_name or not req.file_name.strip():
            raise HTTPException(status_code=400, detail="file_name is required")
        
        if '..' in req.file_name:
            raise HTTPException(status_code=400, detail="Invalid file_name")
    
    def _save_file(self, evidence_id: str, file_name: str, raw: bytes) -> Path:
        """Save file with encryption"""
        target_dir = self.settings.evidence_store_dir / evidence_id
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / file_name
        
        if self.evidence_cipher:
            encrypted = self.evidence_cipher.encrypt_for_storage(raw)
        else:
            encrypted = raw
        
        path.write_bytes(encrypted)
        return path


# TODO: Create similar services for other domains:
# - AuditService (audit logging, compliance)
# - ComplianceService (compliance checks, frameworks)
# - SecurityService (threat detection, alerts)
# - ReportingService (report generation)
# - SearchService (evidence search, indexing)

# Usage in main.py:
# from app.evidence_service import EvidenceService
# evidence_service = EvidenceService(store, ledger, search_engine, audit_logger, evidence_cipher, settings)
#
# @app.post("/evidence/intake")
# def intake(req: EvidenceIntakeRequest, principal: Principal = Depends(get_jwt_user)):
#     return evidence_service.intake(req, principal, client_ip=...)
