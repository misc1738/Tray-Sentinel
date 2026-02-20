from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any

from fpdf import FPDF

from app.utils import sha256_bytes


def _build_pdf_report(data: dict[str, Any]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    def txt(s: str, bold: bool = False):
        pdf.set_font("Arial", "B" if bold else "", size=12)
        pdf.multi_cell(0, 8, s)
        pdf.ln(4)

    txt("Tracey's Sentinel — Court Bundle", bold=True)
    txt(f"Evidence ID: {data['evidence']['evidence_id']}")
    txt(f"Case ID: {data['evidence']['case_id']}")
    txt(f"SHA‑256: {data['evidence']['sha256']}")
    txt(f"Created: {data['evidence']['created_at']}")
    txt("")

    txt("Legal Basis", bold=True)
    txt("Kenya Evidence Act Section 106B")
    txt("Standards: ISO/IEC 27037, ISO/IEC 27043, NIST SP 800‑86")
    txt("")

    txt("Chain Validation", bold=True)
    txt(f"Chain valid: {data['ledger_validation']['chain_valid']} — {data['ledger_validation']['message']}")
    txt("")

    txt("Custody Timeline", bold=True)
    for ev in data["chain_of_custody"]:
        txt(f"{ev['action_type']} — {ev['timestamp']}")
        txt(f"Actor: {ev['actor']['user_id']} ({ev['actor']['role']}, {ev['actor']['org_id']})")
        txt(f"Endorsement: {ev['endorsement_status']}")
        txt("")

    return pdf.output(dest="S").encode("latin-1")
