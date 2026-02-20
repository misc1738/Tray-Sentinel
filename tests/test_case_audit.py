from __future__ import annotations

from pathlib import Path

from app.ledger import Ledger
from app.rbac import Principal, Role
from app.reporting import build_case_audit_summary


def test_case_audit_summary_flags_integrity_and_pending_endorsements(tmp_path: Path):
    ledger = Ledger(tmp_path / "ledger.jsonl", base_dir=tmp_path)

    kps = Principal(user_id="officer1", role=Role.FIELD_OFFICER, org_id="KPS")

    # Requires 2 orgs; starts pending after originator endorsement only.
    ledger.append_event(
        evidence_id="E1",
        action_type="TRANSFER",
        principal=kps,
        expected_sha256="abc",
        presented_sha256="abc",
        integrity_ok=True,
        details={"from": "KPS", "to": "FORENSIC_LAB"},
        endorse=True,
    )

    # Marked as integrity failure but fully endorsed for single-org requirement.
    ledger.append_event(
        evidence_id="E2",
        action_type="ACCESS",
        principal=kps,
        expected_sha256="def",
        presented_sha256="bad",
        integrity_ok=False,
        details={"purpose": "sanity_check"},
        endorse=True,
    )

    report = build_case_audit_summary(
        case_id="CASE-1",
        evidence_items=[
            {"evidence_id": "E1", "file_name": "a.bin", "sha256": "abc"},
            {"evidence_id": "E2", "file_name": "b.bin", "sha256": "def"},
        ],
        timelines_by_evidence={
            "E1": ledger.get_timeline("E1"),
            "E2": ledger.get_timeline("E2"),
        },
        compute_endorsement_status=ledger.compute_endorsement_status,
        chain_valid=True,
        chain_message="ok",
    )

    assert report["case_id"] == "CASE-1"
    assert report["evidence_count"] == 2
    assert report["total_events"] == 2
    assert report["integrity_failures"] == 1
    assert report["pending_endorsements"] == 1
    assert report["compliant_evidence_count"] == 0

    by_id = {row["evidence_id"]: row for row in report["evidence_audits"]}
    assert by_id["E1"]["compliance_status"] == "ATTENTION_REQUIRED"
    assert by_id["E1"]["pending_endorsements"] == 1
    assert by_id["E2"]["compliance_status"] == "ATTENTION_REQUIRED"
    assert by_id["E2"]["integrity_failures"] == 1
