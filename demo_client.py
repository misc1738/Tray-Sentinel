from __future__ import annotations

import base64
import json

import httpx


BASE_URL = "http://127.0.0.1:8000"


def _b64(s: bytes) -> str:
    return base64.b64encode(s).decode("utf-8")


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # 1) Intake by officer
        intake = {
            "case_id": "KPS-CASE-0001",
            "description": "Disk image acquisition (simulated)",
            "source_device": "Laptop SN ABC123",
            "acquisition_method": "FTK Imager (simulated)",
            "file_name": "disk_image.E01",
            "file_bytes_b64": _b64(b"SIMULATED_E01_IMAGE_BYTES_v1"),
        }
        r = client.post("/evidence/intake", headers={"X-User-Id": "officer1"}, json=intake)
        r.raise_for_status()
        ev = r.json()
        evidence_id = ev["evidence_id"]
        print("INTAKE evidence_id=", evidence_id)

        # 2) Create a TRANSFER event endorsed by KPS only -> should be pending
        transfer = {
            "evidence_id": evidence_id,
            "action_type": "TRANSFER",
            "details": {"from": "KPS", "to": "FORENSIC_LAB", "reason": "analysis"},
            "presented_sha256": ev["sha256"],
            "endorse": True,
        }
        r = client.post("/evidence/event", headers={"X-User-Id": "officer1"}, json=transfer)
        r.raise_for_status()
        transfer_tx = r.json()
        print("TRANSFER tx_id=", transfer_tx["tx_id"], "status=", transfer_tx["endorsement_status"])

        # 3) Second org (FORENSIC_LAB) endorses transfer -> becomes final (computed)
        endorse = {"evidence_id": evidence_id, "tx_id": transfer_tx["tx_id"]}
        r = client.post("/evidence/endorse", headers={"X-User-Id": "analyst1"}, json=endorse)
        r.raise_for_status()
        print("ENDORSE recorded")

        # 4) Fetch timeline and show computed status
        r = client.get(f"/evidence/{evidence_id}/timeline", headers={"X-User-Id": "auditor1"})
        r.raise_for_status()
        timeline = r.json()
        print("TIMELINE:")
        print(json.dumps(timeline, indent=2))

        # 5) Verify integrity (rehash off-chain file)
        r = client.post(f"/evidence/{evidence_id}/verify", headers={"X-User-Id": "analyst1"})
        r.raise_for_status()
        print("VERIFY:", r.json())

        # 6) Generate court report
        r = client.get(f"/evidence/{evidence_id}/report", headers={"X-User-Id": "supervisor1"})
        r.raise_for_status()
        print("REPORT GENERATED")


if __name__ == "__main__":
    main()
