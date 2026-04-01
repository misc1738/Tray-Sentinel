from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Header, HTTPException
from passlib.context import CryptContext

from app.rbac import Principal, Role

# ===== PASSWORD HASHING =====
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt (secure)."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# Prototype identity provider (demo users with bcrypt hashes).
# In production this would be replaced by OIDC + mTLS client certs + org CA.
# Default passwords: officer1->pass123, analyst1->pass123, etc.
USERS: dict[str, dict[str, str]] = {
    "officer1": {
        "role": Role.FIELD_OFFICER.value,
        "org_id": "KPS",
        "password_hash": "$2b$12$2SsdKP9.ZqKTslgyB/oy7evSLHW48rsHz0dyv7bXuDLNmxUk0W9DO",  # bcrypt(pass123)
    },
    "analyst1": {
        "role": Role.FORENSIC_ANALYST.value,
        "org_id": "FORENSIC_LAB",
        "password_hash": "$2b$12$2SsdKP9.ZqKTslgyB/oy7evSLHW48rsHz0dyv7bXuDLNmxUk0W9DO",
    },
    "supervisor1": {
        "role": Role.SUPERVISOR.value,
        "org_id": "KPS",
        "password_hash": "$2b$12$2SsdKP9.ZqKTslgyB/oy7evSLHW48rsHz0dyv7bXuDLNmxUk0W9DO",
    },
    "prosecutor1": {
        "role": Role.PROSECUTOR.value,
        "org_id": "ODPP",
        "password_hash": "$2b$12$2SsdKP9.ZqKTslgyB/oy7evSLHW48rsHz0dyv7bXuDLNmxUk0W9DO",
    },
    "judge1": {
        "role": Role.JUDGE.value,
        "org_id": "JUDICIARY",
        "password_hash": "$2b$12$2SsdKP9.ZqKTslgyB/oy7evSLHW48rsHz0dyv7bXuDLNmxUk0W9DO",
    },
    "auditor1": {
        "role": Role.SYSTEM_AUDITOR.value,
        "org_id": "INTERNAL_AUDIT",
        "password_hash": "$2b$12$2SsdKP9.ZqKTslgyB/oy7evSLHW48rsHz0dyv7bXuDLNmxUk0W9DO",
    },
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


def get_principal(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    authorization: str | None = Header(default=None, alias="Authorization")
) -> Principal:
    """
    Get principal from X-User-Id header (legacy) OR Bearer token (new JWT).
    
    Supports both:
    1. Legacy: X-User-Id header (for backward compatibility)
    2. New JWT: Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
    """
    from app.jwt_auth import decode_token
    
    # Try JWT token first (new approach)
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]  # Remove "Bearer " prefix
        user_payload = decode_token(token, token_type="access")
        
        if user_payload:
            # TODO: Load full user data from database based on user_id
            # For now, use default org_id
            users = _load_users()
            user_data = users.get(user_payload.user_id, {})
            
            return Principal(
                user_id=user_payload.user_id,
                role=Role(user_payload.role),
                org_id=user_data.get("org_id", "default-org"),
            )
    
    # Fall back to X-User-Id header (legacy, deprecated in favor of JWT)
    if x_user_id:
        users = _load_users()
        row = users.get(x_user_id)
        
        if row:
            return Principal(user_id=x_user_id, role=Role(row["role"]), org_id=row["org_id"])
    
    raise HTTPException(status_code=401, detail="Missing or invalid credentials. Use Bearer token or X-User-Id header.")
