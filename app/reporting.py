from __future__ import annotations

from typing import Any

from app.ledger import LedgerEvent
from app.utils import utcnow_iso


def build_court_report(
    *,
    evidence: dict[str, Any],
    timeline: list[LedgerEvent],
    compute_endorsement_status,
    chain_valid: bool,
    chain_message: str,
) -> dict[str, Any]:
    # Court-ready summary focused on integrity + chronological actions.
    events = []
    for e in timeline:
        endorsement_status = "FINAL" if e.action_type == "ENDORSE" else compute_endorsement_status(e)[0]
        events.append(
            {
                "tx_id": e.tx_id,
                "action_type": e.action_type,
                "timestamp": e.timestamp,
                "actor": {"user_id": e.actor_user_id, "role": e.actor_role, "org_id": e.actor_org_id},
                "required_endorser_orgs": e.required_endorser_orgs,
                "endorsement_status": endorsement_status,
                "integrity_ok": e.integrity_ok,
                "presented_sha256": e.presented_sha256,
                "expected_sha256": e.expected_sha256,
                "details": e.details,
                "signing": {"signer_pubkey_b64": e.signer_pubkey_b64, "signature_b64": e.signature_b64},
                "record_hash": e.record_hash,
                "prev_hash": e.prev_hash,
            }
        )

    return {
        "generated_at": utcnow_iso(),
        "jurisdiction": "Kenya",
        "legal_basis": {
            "evidence_act": "Evidence Act (Kenya) Section 106B",
            "standards": ["ISO/IEC 27037", "ISO/IEC 27043", "NIST SP 800-86"],
        },
        "ledger_validation": {"chain_valid": chain_valid, "message": chain_message},
        "evidence": evidence,
        "chain_of_custody": events,
        "attestation": {
            "notes": "This report is generated from an append-only, hash-chained custody ledger. Any tampering breaks hash continuity and validation.",
        },
    }


def build_case_audit_summary(
    *,
    case_id: str,
    evidence_items: list[dict[str, Any]],
    timelines_by_evidence: dict[str, list[LedgerEvent]],
    compute_endorsement_status,
    chain_valid: bool,
    chain_message: str,
) -> dict[str, Any]:
    evidence_audits: list[dict[str, Any]] = []
    total_events = 0
    total_integrity_failures = 0
    total_pending_endorsements = 0

    for evidence in evidence_items:
        evidence_id = evidence["evidence_id"]
        events = timelines_by_evidence.get(evidence_id, [])
        total_events += len(events)

        integrity_failures = sum(1 for e in events if not e.integrity_ok)
        pending_endorsements = sum(
            1
            for e in events
            if e.action_type != "ENDORSE" and compute_endorsement_status(e)[0] == "PENDING_ENDORSEMENT"
        )

        total_integrity_failures += integrity_failures
        total_pending_endorsements += pending_endorsements

        compliance_status = "COMPLIANT"
        if integrity_failures > 0 or pending_endorsements > 0:
            compliance_status = "ATTENTION_REQUIRED"

        evidence_audits.append(
            {
                "evidence_id": evidence_id,
                "file_name": evidence["file_name"],
                "expected_sha256": evidence["sha256"],
                "event_count": len(events),
                "last_event_at": events[-1].timestamp if events else None,
                "integrity_failures": integrity_failures,
                "pending_endorsements": pending_endorsements,
                "compliance_status": compliance_status,
            }
        )

    compliant_evidence_count = sum(1 for item in evidence_audits if item["compliance_status"] == "COMPLIANT")

    return {
        "case_id": case_id,
        "generated_at": utcnow_iso(),
        "chain_valid": chain_valid,
        "chain_message": chain_message,
        "evidence_count": len(evidence_items),
        "total_events": total_events,
        "integrity_failures": total_integrity_failures,
        "pending_endorsements": total_pending_endorsements,
        "compliant_evidence_count": compliant_evidence_count,
        "evidence_audits": evidence_audits,
    }
