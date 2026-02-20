from __future__ import annotations

import base64
import io
import uuid
from pathlib import Path

import qrcode
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.auth import get_principal
from app.bundle import build_court_bundle
from app.config import get_settings
from app.ledger import Ledger
from app.models import (
    CaseSummary,
    CustodyEventRequest,
    CustodyEventResponse,
    EndorseRequest,
    EndorseResponse,
    EvidenceIntakeRequest,
    EvidenceResponse,
    ReportResponse,
    TimelineResponse,
    VerifyResponse,
)
from app.rbac import Action, Principal, require_action
from app.reporting import build_court_report
from app.storage import EvidenceRow, EvidenceStore
from app.utils import sha256_bytes, sha256_file, utcnow_iso


app = FastAPI(title="Tracey's Sentinel", version="0.1.0")

settings = get_settings()
store = EvidenceStore(settings.db_path)
ledger = Ledger(settings.ledger_path, base_dir=settings.base_dir)
store.init()

app.mount("/static", StaticFiles(directory="static"), name="static")


def _save_evidence_file(evidence_id: str, file_name: str, raw: bytes) -> Path:
    target_dir = settings.evidence_store_dir / evidence_id
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / file_name
    path.write_bytes(raw)
    return path


@app.get("/health")
def health():
    ok, msg = ledger.validate_chain()
    return {"status": "ok", "ledger_chain_valid": ok, "ledger": msg}


@app.post("/evidence/intake", response_model=EvidenceResponse)
def intake(req: EvidenceIntakeRequest, principal: Principal = Depends(get_principal)):
    try:
        require_action(principal, Action.REGISTER_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

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

    return EvidenceResponse(
        evidence_id=evidence_id,
        case_id=req.case_id,
        description=req.description,
        file_name=req.file_name,
        sha256=sha256,
        created_at=created_at,
    )


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

    actual = sha256_file(file_path)
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
