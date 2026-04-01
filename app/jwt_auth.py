"""
JWT-based Authentication Module
Handles secure authentication with JWT access tokens and refresh tokens
"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict
import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

# ===== PASSWORD HASHING =====
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


# ===== JWT CONFIGURATION =====
# Never hardcode secrets - always use environment variables in production
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", None)
if not JWT_SECRET_KEY:
    import warnings
    import sys
    error_msg = (
        "CRITICAL: JWT_SECRET_KEY environment variable is not set. "
        "This is required for secure token handling. "
        "Set JWT_SECRET_KEY in .env or environment before starting the app. "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )
    warnings.warn(error_msg, RuntimeWarning)
    # In production, this should fail-fast. In development, we'll use a temporary key with a visible warning.
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        print(f"\n\n{'='*80}\n{error_msg}\n{'='*80}\n", file=sys.stderr)
        sys.exit(1)
    # Development mode: use a temporary insecure key
    JWT_SECRET_KEY = "dev-only-insecure-key-change-for-production-" + secrets.token_hex(16)

JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
JWT_ALGORITHM = "HS256"


# ===== TOKEN MODELS =====
class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: str  # subject (user_id)
    user_id: str
    role: str
    iat: datetime  # issued at
    exp: datetime  # expiration
    type: str  # "access" or "refresh"


class TokenResponse(BaseModel):
    """Token response with access and refresh tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserPayload(BaseModel):
    """User data extracted from JWT"""
    user_id: str
    role: str


# ===== TOKEN GENERATION =====
def create_access_token(user_id: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # PyJWT expects Unix timestamp integers for exp/iat, not datetime objects
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "role": role,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "type": "access"
    }
    
    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: str, role: str) -> str:
    """
    Create a JWT refresh token with longer expiration
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    # PyJWT expects Unix timestamp integers for exp/iat, not datetime objects
    payload = {
        "sub": user_id,
        "user_id": user_id,
        "role": role,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "type": "refresh"
    }
    
    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_token_pair(user_id: str, role: str) -> TokenResponse:
    """
    Create both access and refresh tokens
    """
    access_token = create_access_token(user_id, role)
    refresh_token = create_refresh_token(user_id, role)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


# ===== TOKEN VERIFICATION =====
def decode_token(token: str, token_type: str = "access") -> Optional[UserPayload]:
    """
    Decode and validate a JWT token
    
    Args:
        token: JWT token string
        token_type: Expected token type ("access" or "refresh")
    
    Returns:
        UserPayload if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # Verify token type matches expected
        if payload.get("type") != token_type:
            return None
        
        user_id = payload.get("user_id")
        role = payload.get("role")
        
        if not user_id or not role:
            return None
        
        return UserPayload(user_id=user_id, role=role)
    
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def refresh_access_token(refresh_token: str) -> Optional[str]:
    """
    Generate a new access token from a valid refresh token
    
    Args:
        refresh_token: Refresh JWT token
    
    Returns:
        New access token if refresh token is valid, None otherwise
    """
    user_payload = decode_token(refresh_token, token_type="refresh")
    if not user_payload:
        return None
    
    return create_access_token(user_payload.user_id, user_payload.role)


# ===== SESSION DATABASE (Persistent) =====
# Initialize with database path
_session_db_path = Path(os.getenv("DATABASE_URL", "data/sentinel.db"))
_session_db_path.parent.mkdir(parents=True, exist_ok=True)

from app.session_db import SessionDatabase
session_store = SessionDatabase(_session_db_path)


# ===== USER AUTHENTICATION =====
# In production, this should be replaced with a real database query
def _get_demo_users():
    """Load users from auth module for centralized user management."""
    from app.auth import _load_users
    return _load_users()


def authenticate_user(user_id: str, password: str) -> Optional[tuple[str, str]]:
    """
    Authenticate a user by verifying credentials against bcrypt hashes
    
    Returns:
        (user_id, role) if credentials valid, None otherwise
    """
    users = _get_demo_users()
    user = users.get(user_id)
    
    if not user:
        return None
    
    password_hash = user.get("password_hash")
    if not password_hash or not verify_password(password, password_hash):
        return None
    
    return (user_id, user.get("role", "user"))

