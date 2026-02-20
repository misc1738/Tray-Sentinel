from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.rbac import Principal, required_endorser_org_count
from app.signing import get_or_create_user_keys, pubkey_b64, sign_b64, verify_signature
from app.utils import sha256_bytes, utcnow_iso


@dataclass(frozen=True)
class LedgerEvent:
    tx_id: str
    evidence_id: str
    action_type: str
    required_endorser_orgs: int
    actor_user_id: str
    actor_role: str
    actor_org_id: str
    timestamp: str
    presented_sha256: Optional[str]
    expected_sha256: str
    integrity_ok: bool
    prev_hash: str
    record_hash: str
    endorsement_status: str
    endorsements: list[dict[str, str]]
    details: dict[str, Any]
    signer_pubkey_b64: str
    signature_b64: str


class Ledger:
    def __init__(self, ledger_path: Path, *, base_dir: Optional[Path] = None):
        self.ledger_path = ledger_path
        self.base_dir = base_dir
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            self.ledger_path.write_text("", encoding="utf-8")

    def _signing_payload(self, row_without_hash: dict[str, Any]) -> bytes:
        # Signature is over canonical JSON excluding record_hash and signature fields.
        copy = dict(row_without_hash)
        copy.pop("record_hash", None)
        copy.pop("signer_pubkey_b64", None)
        copy.pop("signature_b64", None)
        return json.dumps(copy, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _iter_rows(self):
        if not self.ledger_path.exists():
            return
        with self.ledger_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def last_hash(self) -> str:
        last = "GENESIS"
        for row in self._iter_rows():
            last = row["record_hash"]
        return last

    def get_timeline(self, evidence_id: str) -> list[LedgerEvent]:
        out: list[LedgerEvent] = []
        for row in self._iter_rows():
            if row.get("evidence_id") == evidence_id:
                out.append(LedgerEvent(**row))
        return out

    def _endorsements_by_tx(self) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for row in self._iter_rows():
            if row.get("action_type") != "ENDORSE":
                continue
            endorsed_tx_id = (row.get("details") or {}).get("endorsed_tx_id")
            if not endorsed_tx_id:
                continue
            org_id = row.get("actor_org_id")
            if not org_id:
                continue
            out.setdefault(endorsed_tx_id, set()).add(org_id)
        return out

    def endorser_orgs_for_tx(self, tx_id: str) -> set[str]:
        return set(self._endorsements_by_tx().get(tx_id, set()))

    def compute_endorsement_status(self, ev: LedgerEvent) -> tuple[str, int, int]:
        """Returns (status, unique_endorser_orgs, required_orgs)."""
        required = max(1, int(ev.required_endorser_orgs))
        endorsed = self.endorser_orgs_for_tx(ev.tx_id)
        # If the originating event included an endorsement, count the actor org as an endorser.
        if ev.endorsements:
            for e in ev.endorsements:
                org = e.get("org_id")
                if org:
                    endorsed.add(org)
        unique = len(endorsed)
        status = "FINAL" if unique >= required else "PENDING_ENDORSEMENT"
        return status, unique, required

    def append_event(
        self,
        *,
        evidence_id: str,
        action_type: str,
        principal: Principal,
        expected_sha256: str,
        presented_sha256: Optional[str],
        integrity_ok: bool,
        details: dict[str, Any],
        endorse: bool,
    ) -> LedgerEvent:
        tx_id = str(uuid.uuid4())
        prev_hash = self.last_hash()
        timestamp = utcnow_iso()

        required_orgs = required_endorser_org_count(action_type)
        endorsements: list[dict[str, str]] = []
        if endorse:
            endorsements.append({"org_id": principal.org_id, "user_id": principal.user_id})

        # Status reflects whether this event is fully endorsed.
        endorsement_status = "FINAL" if len({e['org_id'] for e in endorsements}) >= required_orgs else "PENDING_ENDORSEMENT"

        canonical = {
            "tx_id": tx_id,
            "evidence_id": evidence_id,
            "action_type": action_type,
            "required_endorser_orgs": required_orgs,
            "actor_user_id": principal.user_id,
            "actor_role": principal.role.value,
            "actor_org_id": principal.org_id,
            "timestamp": timestamp,
            "presented_sha256": presented_sha256,
            "expected_sha256": expected_sha256,
            "integrity_ok": integrity_ok,
            "prev_hash": prev_hash,
            "endorsement_status": endorsement_status,
            "endorsements": endorsements,
            "details": details,
        }

        if not self.base_dir:
            raise ValueError("Ledger requires base_dir for signing")
        km = get_or_create_user_keys(base_dir=self.base_dir, user_id=principal.user_id)
        canonical["signer_pubkey_b64"] = pubkey_b64(km.public_key)
        canonical["signature_b64"] = sign_b64(km.private_key, self._signing_payload(canonical))

        record_hash = sha256_bytes(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        canonical["record_hash"] = record_hash

        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(canonical, sort_keys=True) + "\n")

        return LedgerEvent(**canonical)

    def endorse_event(self, tx_id: str, evidence_id: str, principal: Principal) -> LedgerEvent:
        # JSONL is append-only; endorsement is written as a new ENDORSE event that references tx_id.
        if principal.org_id in self.endorser_orgs_for_tx(tx_id):
            raise ValueError("duplicate endorsement from org")
        prev_hash = self.last_hash()
        timestamp = utcnow_iso()
        canonical = {
            "tx_id": str(uuid.uuid4()),
            "evidence_id": evidence_id,
            "action_type": "ENDORSE",
            "required_endorser_orgs": 1,
            "actor_user_id": principal.user_id,
            "actor_role": principal.role.value,
            "actor_org_id": principal.org_id,
            "timestamp": timestamp,
            "presented_sha256": None,
            "expected_sha256": "",
            "integrity_ok": True,
            "prev_hash": prev_hash,
            "endorsement_status": "FINAL",
            "endorsements": [{"org_id": principal.org_id, "user_id": principal.user_id}],
            "details": {"endorsed_tx_id": tx_id},
        }

        if not self.base_dir:
            raise ValueError("Ledger requires base_dir for signing")
        km = get_or_create_user_keys(base_dir=self.base_dir, user_id=principal.user_id)
        canonical["signer_pubkey_b64"] = pubkey_b64(km.public_key)
        canonical["signature_b64"] = sign_b64(km.private_key, self._signing_payload(canonical))

        record_hash = sha256_bytes(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        canonical["record_hash"] = record_hash
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(canonical, sort_keys=True) + "\n")
        return LedgerEvent(**canonical)

    def validate_chain(self) -> tuple[bool, str]:
        prev = "GENESIS"
        for row in self._iter_rows():
            record_hash = row.get("record_hash")
            copy = dict(row)
            copy.pop("record_hash", None)
            expected = sha256_bytes(json.dumps(copy, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            if expected != record_hash:
                return False, "record hash mismatch"
            if row.get("prev_hash") != prev:
                return False, "prev_hash mismatch"

            signer_pub = row.get("signer_pubkey_b64")
            sig = row.get("signature_b64")
            if not signer_pub or not sig:
                return False, "missing signature"
            if not verify_signature(pubkey_b64_str=signer_pub, signature_b64_str=sig, payload=self._signing_payload(row)):
                return False, "invalid signature"

            prev = record_hash
        return True, "ok"
