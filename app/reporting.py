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
