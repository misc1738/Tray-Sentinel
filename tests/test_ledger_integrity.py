from __future__ import annotations

import json
from pathlib import Path

from app.ledger import Ledger
from app.rbac import Principal, Role


def test_ledger_hash_chain_detects_tamper(tmp_path: Path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = Ledger(ledger_path, base_dir=tmp_path)

    p = Principal(user_id="u1", role=Role.FIELD_OFFICER, org_id="KPS")

    ev1 = ledger.append_event(
        evidence_id="E1",
        action_type="INTAKE",
        principal=p,
        expected_sha256="abc",
        presented_sha256="abc",
        integrity_ok=True,
        details={"case_id": "C1"},
        endorse=True,
    )
    assert ev1.prev_hash == "GENESIS"

    ok, _ = ledger.validate_chain()
    assert ok

    # Tamper with the ledger file
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["details"]["case_id"] = "C1-TAMPER"
    lines[0] = json.dumps(row, sort_keys=True)
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, msg = ledger.validate_chain()
    assert not ok
    assert msg in {"record hash mismatch", "prev_hash mismatch"}
