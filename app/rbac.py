from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Role(str, Enum):
    FIELD_OFFICER = "FIELD_OFFICER"
    FORENSIC_ANALYST = "FORENSIC_ANALYST"
    SUPERVISOR = "SUPERVISOR"
    PROSECUTOR = "PROSECUTOR"
    JUDGE = "JUDGE"
    SYSTEM_AUDITOR = "SYSTEM_AUDITOR"


class Action(str, Enum):
    REGISTER_EVIDENCE = "REGISTER_EVIDENCE"
    RECORD_EVENT = "RECORD_EVENT"
    VERIFY_INTEGRITY = "VERIFY_INTEGRITY"
    VIEW_EVIDENCE = "VIEW_EVIDENCE"
    GENERATE_REPORT = "GENERATE_REPORT"


ROLE_ACTIONS: dict[Role, set[Action]] = {
    Role.FIELD_OFFICER: {Action.REGISTER_EVIDENCE, Action.RECORD_EVENT, Action.VERIFY_INTEGRITY, Action.VIEW_EVIDENCE},
    Role.FORENSIC_ANALYST: {Action.RECORD_EVENT, Action.VERIFY_INTEGRITY, Action.VIEW_EVIDENCE},
    Role.SUPERVISOR: {Action.RECORD_EVENT, Action.VERIFY_INTEGRITY, Action.VIEW_EVIDENCE, Action.GENERATE_REPORT},
    Role.PROSECUTOR: {Action.VIEW_EVIDENCE, Action.GENERATE_REPORT},
    Role.JUDGE: {Action.VIEW_EVIDENCE, Action.GENERATE_REPORT},
    Role.SYSTEM_AUDITOR: {Action.VIEW_EVIDENCE, Action.GENERATE_REPORT},
}


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: Role
    org_id: str


def require_action(principal: Principal, action: Action) -> None:
    allowed = ROLE_ACTIONS.get(principal.role, set())
    if action not in allowed:
        raise PermissionError(f"role {principal.role} not permitted to perform {action}")


def requires_endorsement(action_type: str) -> bool:
    # For prototype: custody-transfer / court submission require at least two org endorsements
    return action_type in {"TRANSFER", "COURT_SUBMISSION"}


def required_endorser_org_count(action_type: str) -> int:
    return 2 if requires_endorsement(action_type) else 1
