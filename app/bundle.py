from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.pdf_report import _build_pdf_report
from app.utils import sha256_file, sha256_bytes


def build_court_bundle(
    *,
    evidence_id: str,
    evidence: dict[str, Any],
    timeline: list[dict[str, Any]],
    ledger_validation: dict[str, Any],
    ledger_path: Path,
    evidence_file_path: Path,
) -> bytes:
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1) JSON report
        report = {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "jurisdiction": "Kenya",
            "legal_basis": {
                "evidence_act": "Evidence Act (Kenya) Section 106B",
                "standards": ["ISO/IEC 27037", "ISO/IEC 27043", "NIST SP 800-86"],
            },
            "ledger_validation": ledger_validation,
            "evidence": evidence,
            "chain_of_custody": timeline,
        }
        zf.writestr("report.json", json.dumps(report, indent=2, ensure_ascii=False))

        # 2) PDF report
        zf.writestr("report.pdf", _build_pdf_report(report))

        # 3) Ledger lines for this evidence
        ledger_lines = []
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("evidence_id") == evidence_id or (
                row.get("action_type") == "ENDORSE"
                and (row.get("details") or {}).get("endorsed_tx_id")
                and any(
                    ev.get("tx_id") == (row.get("details") or {}).get("endorsed_tx_id")
                    for ev in timeline
                )
            ):
                ledger_lines.append(line)
        zf.writestr("ledger.jsonl", "\n".join(ledger_lines) + "\n")

        # 4) Hash manifest
        manifest = {
            "evidence_file": {
                "path": str(evidence_file_path.relative_to(evidence_file_path.parents[1])),
                "sha256": sha256_file(evidence_file_path),
            },
            "ledger.jsonl": {"sha256": sha256_bytes("".join(ledger_lines).encode("utf-8"))},
            "report.json": {"sha256": sha256_bytes(json.dumps(report, sort_keys=True).encode("utf-8"))},
            "report.pdf": {"sha256": sha256_bytes(_build_pdf_report(report))},
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    bundle.seek(0)
    return bundle.getvalue()
