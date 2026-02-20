from __future__ import annotations

from pathlib import Path

from app.ledger import Ledger
from app.rbac import Principal, Role


def test_transfer_requires_two_org_endorsements(tmp_path: Path):
    ledger = Ledger(tmp_path / "ledger.jsonl", base_dir=tmp_path)

    kps = Principal(user_id="officer1", role=Role.FIELD_OFFICER, org_id="KPS")
    lab = Principal(user_id="analyst1", role=Role.FORENSIC_ANALYST, org_id="FORENSIC_LAB")

    transfer = ledger.append_event(
        evidence_id="E1",
        action_type="TRANSFER",
        principal=kps,
        expected_sha256="abc",
        presented_sha256="abc",
        integrity_ok=True,
        details={"from": "KPS", "to": "FORENSIC_LAB"},
        endorse=True,
    )

    status, unique, required = ledger.compute_endorsement_status(transfer)
    assert required == 2
    assert unique == 1
    assert status == "PENDING_ENDORSEMENT"

    ledger.endorse_event(transfer.tx_id, "E1", lab)

    # Duplicate endorsement by same org should be rejected
    try:
        ledger.endorse_event(transfer.tx_id, "E1", lab)
        assert False, "expected duplicate endorsement rejection"
    except ValueError as e:
        assert str(e) == "duplicate endorsement from org"

    # Re-read event (timeline loads from file); status should now be FINAL
    ev = ledger.get_timeline("E1")[0]
    status, unique, required = ledger.compute_endorsement_status(ev)
    assert required == 2
    assert unique == 2
    assert status == "FINAL"
