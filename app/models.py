from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


ActionType = Literal[
    "INTAKE",
    "TRANSFER",
    "ACCESS",
    "ANALYSIS",
    "STORAGE",
    "COURT_SUBMISSION",
    "ENDORSE",
]


class EvidenceIntakeRequest(BaseModel):
    case_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_device: Optional[str] = None
    acquisition_method: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    file_bytes_b64: str = Field(min_length=1)


class EvidenceResponse(BaseModel):
    evidence_id: str
    case_id: str
    description: str
    file_name: str
    sha256: str
    created_at: str


class CustodyEventRequest(BaseModel):
    evidence_id: str = Field(min_length=1)
    action_type: ActionType
    details: dict[str, Any] = Field(default_factory=dict)
    presented_sha256: Optional[str] = None
    endorse: bool = False


class CustodyEventResponse(BaseModel):
    tx_id: str
    evidence_id: str
    action_type: ActionType
    required_endorser_orgs: int = 1
    endorser_org_ids: list[str] = Field(default_factory=list)
    unique_endorser_orgs: int = 0
    actor_user_id: str
    actor_role: str
    actor_org_id: str
    timestamp: str
    presented_sha256: Optional[str]
    expected_sha256: str
    integrity_ok: bool
    endorsement_status: str
    signer_pubkey_b64: str = ""
    signature_b64: str = ""
    record_hash: str = ""
    prev_hash: str = ""


class TimelineResponse(BaseModel):
    evidence_id: str
    expected_sha256: str
    events: list[CustodyEventResponse]


class VerifyResponse(BaseModel):
    evidence_id: str
    expected_sha256: str
    actual_sha256: str
    integrity_ok: bool


class ReportResponse(BaseModel):
    evidence_id: str
    generated_at: str
    report: dict[str, Any]


class EndorseRequest(BaseModel):
    evidence_id: str = Field(min_length=1)
    tx_id: str = Field(min_length=1)


class EndorseResponse(BaseModel):
    tx_id: str
    endorsed_tx_id: str
    evidence_id: str
    endorser_user_id: str
    endorser_role: str
    endorser_org_id: str
    timestamp: str


class CaseSummary(BaseModel):
    case_id: str
    evidence_items: list[EvidenceResponse]
