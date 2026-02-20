from __future__ import annotations

from fastapi import Header, HTTPException

from app.rbac import Principal, Role


# Prototype identity provider.
# In production this would be replaced by OIDC + mTLS client certs + org CA.
USERS: dict[str, dict[str, str]] = {
    "officer1": {"role": Role.FIELD_OFFICER.value, "org_id": "KPS"},
    "analyst1": {"role": Role.FORENSIC_ANALYST.value, "org_id": "FORENSIC_LAB"},
    "supervisor1": {"role": Role.SUPERVISOR.value, "org_id": "KPS"},
    "prosecutor1": {"role": Role.PROSECUTOR.value, "org_id": "ODPP"},
    "judge1": {"role": Role.JUDGE.value, "org_id": "JUDICIARY"},
    "auditor1": {"role": Role.SYSTEM_AUDITOR.value, "org_id": "INTERNAL_AUDIT"},
}


def get_principal(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> Principal:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    row = USERS.get(x_user_id)
    if not row:
        raise HTTPException(status_code=401, detail="Unknown user")

    return Principal(user_id=x_user_id, role=Role(row["role"]), org_id=row["org_id"])
