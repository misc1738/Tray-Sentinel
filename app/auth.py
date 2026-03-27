from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Header, HTTPException

from app.rbac import Principal, Role


# Prototype identity provider.
# In production this would be replaced by OIDC + mTLS client certs + org CA.
USERS: dict[str, dict[str, str]] = {
    "officer1": {"role": Role.FIELD_OFFICER.value, "org_id": "KPS", "password_hash": "demo123"},
    "analyst1": {"role": Role.FORENSIC_ANALYST.value, "org_id": "FORENSIC_LAB", "password_hash": "demo123"},
    "supervisor1": {"role": Role.SUPERVISOR.value, "org_id": "KPS", "password_hash": "demo123"},
    "prosecutor1": {"role": Role.PROSECUTOR.value, "org_id": "ODPP", "password_hash": "demo123"},
    "judge1": {"role": Role.JUDGE.value, "org_id": "JUDICIARY", "password_hash": "demo123"},
    "auditor1": {"role": Role.SYSTEM_AUDITOR.value, "org_id": "INTERNAL_AUDIT", "password_hash": "demo123"},
}

# Session tokens: token -> {user_id, role, org_id, expires}
SESSIONS: dict[str, dict] = {}

# User storage file
USER_STORAGE_FILE = Path("data/users.json")
USER_STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_users():
    """Load users from JSON file."""
    if USER_STORAGE_FILE.exists():
        try:
            with open(USER_STORAGE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return USERS.copy()


def _save_users(users_dict: dict):
    """Save users to JSON file."""
    with open(USER_STORAGE_FILE, 'w') as f:
        json.dump(users_dict, f, indent=2)


def hash_password(password: str) -> str:
    """Hash a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(64)


def create_session(user_id: str, role: str, org_id: str) -> str:
    """Create a new session and return token."""
    token = generate_session_token()
    SESSIONS[token] = {
        "user_id": user_id,
        "role": role,
        "org_id": org_id,
        "expires": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
    }
    return token


def validate_session_token(token: str) -> dict | None:
    """Validate a session token and return session data."""
    if token not in SESSIONS:
        return None

    session = SESSIONS[token]
    if datetime.fromisoformat(session["expires"]) < datetime.utcnow():
        del SESSIONS[token]
        return None

    return session


def get_principal_from_token(token: str) -> Principal:
    """Get principal from session token."""
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return Principal(
        user_id=session["user_id"],
        role=Role(session["role"]),
        org_id=session["org_id"],
    )


def get_principal(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> Principal:
    """Get principal from X-User-Id header or Bearer token."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")

    # Try to load from users file
    users = _load_users()

    row = users.get(x_user_id)
    if not row:
        raise HTTPException(status_code=401, detail="Unknown user")

    return Principal(user_id=x_user_id, role=Role(row["role"]), org_id=row["org_id"])
