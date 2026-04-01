# Tracey's Sentinel - Detailed Issues & Remediation Guide

**Generated:** April 1, 2026  
**Status:** Comprehensive Technical Analysis

---

## 🔴 CRITICAL ISSUES - MUST FIX IMMEDIATELY

### Issue #1: Missing MASTER_KEY_PASSWORD
**Severity:** CRITICAL  
**Impact:** Private keys stored unencrypted on disk  
**Estimated Fix Time:** 5 minutes

#### Current State
```python
# app/signing.py:37
if not os.getenv("MASTER_KEY_PASSWORD"):
    warnings.warn("⚠️  MASTER_KEY_PASSWORD environment variable not set...")
    # Keys stored with NoEncryption() - SECURITY RISK
```

#### Step-by-Step Fix

**1. Generate a strong master password:**
```bash
# Option A: Use Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Option B: Use OpenSSL
openssl rand -base64 32

# Result will look like: "Ab_1K2mN-pQ9rS_8tU_vW9x0yZ1aB-2cd"
```

**2. Update .env file:**
```bash
# Edit: c:\Users\4RCH4NG3L\Desktop\Projects\Tracey's Sentinel\.env

# Add or uncomment:
MASTER_KEY_PASSWORD=<paste-generated-password-here>

# Example:
MASTER_KEY_PASSWORD=Ab_1K2mN-pQ9rS_8tU_vW9x0yZ1aB-2cd
```

**3. Clear old unencrypted keys (if exists):**
```bash
# ONLY if regenerating keys:
rm -f data/keys/evidence.fernet.key
rm -f data/keys/*.pem
```

**4. Restart application:**
```bash
# Keys will be regenerated with encryption
uvicorn app.main:app --reload
```

**5. Verify fix:**
```bash
# Keys file should now be encrypted
# Size should be different from plaintext version
ls -la data/keys/
```

---

### Issue #2: Unencrypted User Credentials Storage
**Severity:** CRITICAL (for sensitive deployments)  
**Impact:** User passwords stored in plain JSON  
**Estimated Fix Time:** 2-3 weeks  
**Complexity:** HIGH

#### Current State
```python
# app/auth.py - user storage in JSON
USERS: dict = {
    "officer1": {
        "role": "FIELD_OFFICER",
        "org_id": "KPS",
        "password_hash": "$2b$12$...",  # ← Already hashed with bcrypt (GOOD)
    }
}

# Stored in: data/users.json (plaintext JSON file)
```

#### Recommended Solution

**Create proper user database table:**

```sql
-- PostgreSQL migration (use Alembic)
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email TEXT UNIQUE,
    first_name TEXT,
    last_name TEXT,
    org_id TEXT NOT NULL REFERENCES organizations(org_id),
    role TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret TEXT,  -- TOTP secret (encrypted)
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT REFERENCES users(user_id)
);

CREATE TABLE organizations (
    org_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_organizations (
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    org_id TEXT NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    PRIMARY KEY (user_id, org_id)
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_org_id ON users(org_id);
CREATE INDEX idx_users_is_active ON users(is_active);
```

**Update Alembic migration:**
```python
# alembic/versions/001_initial_schema.py

def upgrade() -> None:
    """Create initial user and organization tables."""
    op.create_table(
        'organizations',
        sa.Column('org_id', sa.String, primary_key=True),
        sa.Column('name', sa.String, nullable=False),
        # ... etc
    )
    op.create_table('users', ...)
    op.create_index('idx_users_org_id', 'users', ['org_id'])

def downgrade() -> None:
    """Drop user and organization tables."""
    op.drop_table('users')
    op.drop_table('organizations')
```

**Update auth.py to query database:**
```python
# app/auth.py

from sqlalchemy import select
from app.models import User, Organization

async def get_user_from_db(user_id: str, db_session) -> Optional[dict]:
    """Load user from database."""
    result = await db_session.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalars().first()
    return user.to_dict() if user else None

async def authenticate_user(
    user_id: str, 
    password: str, 
    db_session
) -> Optional[tuple[str, str]]:
    """Authenticate against database."""
    user = await get_user_from_db(user_id, db_session)
    if not user:
        return None
    
    if not user.get("is_active"):
        return None
        
    if not verify_password(password, user["password_hash"]):
        return None
    
    return (user_id, user["role"])
```

---

### Issue #3: Search Sort_By Validation (MEDIUM)
**Severity:** MEDIUM (addresses SQL injection risk)  
**Status:** ✅ ALREADY FIXED  
**Verification:** ✓ Whitelist validation present in app/search.py line 167

```python
# VERIFIED FIXED: app/search.py:167-170
allowed_sort_fields = {"created_at", "updated_at", "resource_type", "resource_id", "case_id"}
sort_field = search_query.sort_by if search_query.sort_by in allowed_sort_fields else "created_at"
```

---

---

## 🟠 HIGH PRIORITY ISSUES

### Issue #4: Response Model Inconsistencies
**Severity:** HIGH (API compatibility & versioning)  
**Impact:** Breaking changes go unnoticed  
**Estimated Fix Time:** 1 week  
**Complexity:** MEDIUM

#### Affected Endpoints (Fix Priority Order)

**Priority 1 - Audit Endpoints:**
```python
# ❌ Current - Untyped
@app.get("/audit/logs")
def query_audit_logs(...):
    return {
        "logs": [...],
        "count": 10,
        "limit": 50,
        "offset": 0
    }

# ✅ Fixed - Typed
from pydantic import BaseModel
from typing import List

class AuditLogItem(BaseModel):
    audit_id: str
    event_type: str
    actor_user_id: str
    actor_org_id: str
    resource_type: str
    resource_id: str
    action: str
    status: str  # SUCCESS, FAILURE, PARTIAL
    timestamp: str
    ip_address: Optional[str] = None

class AuditLogsResponse(BaseModel):
    logs: List[AuditLogItem]
    count: int
    limit: int
    offset: int

@app.get("/audit/logs", response_model=AuditLogsResponse)
def query_audit_logs(...) -> AuditLogsResponse:
    # ... logic ...
    return AuditLogsResponse(
        logs=log_items,
        count=total,
        limit=limit,
        offset=offset
    )
```

**Priority 2 - Security Endpoints:**
```python
# ❌ Current
@app.get("/security/audit-logs")
def get_audit_logs(...):
    return {"logs": [...], "total": ...}

# ✅ Fixed
class SecurityAuditLog(BaseModel):
    timestamp: str
    user_id: str
    action: str
    resource: str
    status: str

class SecurityAuditResponse(BaseModel):
    logs: List[SecurityAuditLog]
    total: int

@app.get("/security/audit-logs", response_model=SecurityAuditResponse)
def get_audit_logs(...) -> SecurityAuditResponse:
    ...
```

**Priority 3 - Search Endpoints:**
```python
# ❌ Current (partially typed)
@app.post("/search")
def search_evidence(query: SearchQuery, ...):
    return {
        "results": [...],
        "total": ...,
        "limit": ...,
        "offset": ...
    }

# ✅ Fixed
class SearchResponseModel(BaseModel):
    results: List[SearchResult]
    total: int
    limit: int
    offset: int

@app.post("/search", response_model=SearchResponseModel)
def search_evidence(...) -> SearchResponseModel:
    results, total = search_engine.search(query)
    return SearchResponseModel(
        results=results,
        total=total,
        limit=query.limit,
        offset=query.offset
    )
```

#### Generating Response Models (Quick Script)
```bash
# Run this to generate stub response models
cat > app/response_models.py << 'EOF'
"""All API response models for documentation and validation."""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class AuditLogResponse(BaseModel):
    audit_id: str
    event_type: str
    actor_user_id: str
    actor_org_id: str
    # ... other fields ...

class AdminStatsResponse(BaseModel):
    total_evidence: int
    total_cases: int
    total_users: int
    # ... etc ...

# Add more as needed
EOF
```

---

### Issue #5: Email Validation in Signup
**Severity:** MEDIUM-HIGH  
**Impact:** Invalid emails in database  
**Estimated Fix Time:** 2 hours

#### Current Code
```python
# ❌ app/main.py:332 - NO VALIDATION
@app.post("/auth/signup")
def signup(request_data: dict):
    email = request_data.get("email", "").strip()
    # ← No validation!
```

#### Step-by-Step Fix

**1. Update Pydantic models:**
```python
# app/models.py - ADD

from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class SignupRequest(BaseModel):
    """User signup request with validation."""
    user_id: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    email: EmailStr  # ← Built-in email validation
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    org_id: Optional[str] = None

class SignupResponse(BaseModel):
    """Signup response."""
    user_id: str
    email: str
    message: str
```

**2. Update signup endpoint:**
```python
# app/main.py:332 - UPDATED

@app.post("/auth/signup", response_model=SignupResponse)
def signup(request: SignupRequest) -> SignupResponse:
    """Register a new user with email validation."""
    # Email is automatically validated by Pydantic!
    
    # Check if user already exists
    users = _load_users()
    if request.user_id in users:
        raise HTTPException(status_code=409, detail="User already exists")
    
    # Check if email already used
    for user_data in users.values():
        if user_data.get("email") == request.email:
            raise HTTPException(status_code=409, detail="Email already registered")
    
    # Create user
    users[request.user_id] = {
        "email": request.email,
        "password_hash": hash_password(request.password),
        "first_name": request.first_name,
        "last_name": request.last_name,
        "org_id": request.org_id or "default-org",
        "role": "FIELD_OFFICER",
        "created_at": utcnow_iso(),
    }
    
    _save_users(users)
    
    return SignupResponse(
        user_id=request.user_id,
        email=request.email,
        message="Signup successful"
    )
```

**3. Test it:**
```bash
# Invalid email → will be rejected by Pydantic
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"user_id":"john","password":"securepass123","email":"not-an-email"}'

# Response: "422 Unprocessable Entity" with email validation error

# Valid email → will work
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"user_id":"john","password":"securepass123","email":"john@example.com"}'
```

---

### Issue #6: Pagination Inconsistency
**Severity:** MEDIUM  
**Impact:** Confusing API behavior  
**Estimated Fix Time:** 3 hours

#### Current State
```python
/case/{case_id}/evidence: limit=50 (from pagination.DEFAULT_LIMIT)
/security/audit-logs: limit=100 (hardcoded)
/audit/actor/{actor_user_id}: limit=50 (hardcoded)
/webhooks/{subscription_id}/deliveries: limit=50 (hardcoded)
```

#### Fix: Standardize All Endpoints

**1. Update pagination.py:**
```python
# app/pagination.py

DEFAULT_LIMIT = 20  # Changed from variable default
MAX_LIMIT = 500
MIN_LIMIT = 1

def validate_pagination(
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    max_limit: int = MAX_LIMIT
) -> tuple[int, int]:
    """Validate and normalize pagination parameters."""
    limit = max(MIN_LIMIT, min(int(limit), max_limit))
    offset = max(0, int(offset))
    return limit, offset
```

**2. Update all endpoints:**
```python
from app.pagination import validate_pagination, DEFAULT_LIMIT, MAX_LIMIT

@app.get("/audit/logs")
def query_audit_logs(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """Query audit logs with standard pagination."""
    limit, offset = validate_pagination(limit, offset)
    # ... rest of logic ...

@app.get("/security/audit-logs")
def get_audit_logs(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """Get audit logs with standard pagination."""
    limit, offset = validate_pagination(limit, offset)
    # ... rest of logic ...
```

---

### Issue #7: Lambda Functions in Rollback Actions
**Severity:** MEDIUM  
**Impact:** Can't persist/log rollback actions  
**Estimated Fix Time:** 4 hours

#### Current Code
```python
# ❌ app/error_handler.py - NOT SERIALIZABLE
ctx.add_rollback(RollbackAction(
    name="delete_evidence_file",
    action=lambda: file_path.unlink(missing_ok=True)
))
```

#### Fix: Use functools.partial

**1. Create rollback action registry:**
```python
# app/error_handler.py - NEW

from functools import partial
from typing import Callable
import os

class RollbackRegistry:
    """Registry of serializable rollback actions."""
    
    @staticmethod
    def delete_file(path: str) -> None:
        """Delete a file."""
        if os.path.exists(path):
            os.unlink(path)
    
    @staticmethod
    def remove_dir(path: str) -> None:
        """Remove a directory."""
        import shutil
        if os.path.exists(path):
            shutil.rmtree(path)
    
    @staticmethod
    def db_delete_record(db_op: Callable) -> None:
        """Execute database deletion."""
        db_op()
```

**2. Update RollbackAction:**
```python
# app/error_handler.py - UPDATED

from dataclasses import dataclass
from typing import Callable, Any

@dataclass
class RollbackAction:
    """A rollback action - fully serializable."""
    name: str
    action_type: str  # "delete_file", "remove_dir", "db_delete_record"
    args: dict  # Arguments for the action function
    
    def execute(self) -> None:
        """Execute the rollback action."""
        registry_method = getattr(RollbackRegistry, self.action_type)
        registry_method(**self.args)

    def to_dict(self) -> dict:
        """Serialize for logging."""
        return {
            "name": self.name,
            "action_type": self.action_type,
            "args": self.args
        }
```

**3. Usage in main.py:**
```python
# app/main.py - UPDATED

ctx.add_rollback(RollbackAction(
    name="delete_evidence_file",
    action_type="delete_file",
    args={"path": str(file_path)}
))

# Can now be:
# - Logged: json.dumps(rollback.to_dict())
# - Persisted: stored in database
# - Replayed: rollback.execute()
```

---

---

## 🟡 MEDIUM PRIORITY ISSUES

### Issue #8: X-User-Id Header Deprecation Plan
**Severity:** MEDIUM (legacy security pattern)  
**Impact:** Mixed auth methods complicate security analysis  
**Estimated Fix Time:** 2 weeks (deprecation period)

#### Deprecation Timeline

**Phase 1 (Week 1-2): Add Deprecation Warning**
```python
# app/auth.py - UPDATED

def get_principal(...) -> Principal:
    # Try JWT token first
    if authorization and authorization.lower().startswith("bearer "):
        # ... JWT auth ...
        return principal
    
    # Fall back to X-User-Id header (DEPRECATED)
    if x_user_id:
        import warnings
        warnings.warn(
            "X-User-Id header authentication is deprecated. "
            "Please use Authorization: Bearer <token> instead. "
            "This will be removed in v0.3.0 (June 2026).",
            DeprecationWarning
        )
        # ... existing auth ...
        return principal
    
    raise HTTPException(status_code=401, detail="Missing or invalid credentials")
```

**Phase 2 (Week 3-4): Log Deprecation Usage**
```python
# Log when X-User-Id is used for audit trail
audit_logger.log_event(
    audit_id=str(uuid.uuid4()),
    event_type=AuditEventType.AUTHENTICATION_SUCCESS,
    actor_user_id=x_user_id,
    actor_org_id=org_id,
    action="LOGIN_VIA_DEPRECATED_HEADER",  # Flag deprecated method
    details={"warning": "Using deprecated X-User-Id header"}
)
```

**Phase 3 (v0.3.0): Remove X-User-Id Support**
```python
# app/auth.py - v0.3.0

def get_principal(...) -> Principal:
    # Only JWT tokens accepted
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid credentials. Use Authorization: Bearer <token>"
        )
    
    token = authorization[7:]
    user_payload = decode_token(token, token_type="access")
    # ...
```

---

### Issue #9: Encryption Error Information Disclosure
**Severity:** MEDIUM  
**Impact:** Could leak encryption details  
**Estimated Fix Time:** 2 hours

#### Current Code
```python
# ❌ app/evidence_crypto.py:40 - TOO VERBOSE

def decrypt_from_storage(encrypted_evidence: bytes) -> bytes:
    try:
        decrypted = self.cipher.decrypt(encrypted_evidence)
        return decrypted
    except InvalidToken:
        # This specific error could leak encryption info
        raise ValueError("Evidence file corrupted or tampered")
```

#### Fix: Generic Error Handling
```python
# ✅ IMPROVED

def decrypt_from_storage(self, encrypted_evidence: bytes) -> bytes:
    """Decrypt evidence from storage.
    
    Raises:
        ValueError: If decryption fails (generic error to prevent info disclosure)
    """
    try:
        decrypted = self.cipher.decrypt(encrypted_evidence)
        
        # Validate decrypted content is reasonable (not empty, not too large)
        if len(decrypted) == 0:
            raise ValueError("Decrypted evidence is empty")
        
        if len(decrypted) > 1024 * 1024 * 500:  # 500 MB max
            raise ValueError("Decrypted evidence exceeds size limits")
        
        return decrypted
        
    except InvalidToken:
        # Log for investigation but return generic error to client
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Evidence decryption failed - possible tampering")
        
        raise ValueError("Unable to decrypt evidence")
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected decryption error: {e}")
        
        raise ValueError("Unable to decrypt evidence")
```

---

---

## ✅ QUICK WINS (< 4 hours each)

### Quick Win #1: Add Endpoint Docstrings

**Current:**
```python
@app.get("/evidence/{evidence_id}/timeline", response_model=TimelineResponse)
def timeline(evidence_id: str, principal: Principal = Depends(get_principal)):
    # Missing docstring
```

**Fixed:**
```python
@app.get("/evidence/{evidence_id}/timeline", response_model=TimelineResponse)
def timeline(evidence_id: str, principal: Principal = Depends(get_principal)):
    """
    Get custody timeline for evidence.
    
    Retrieves complete chain of custody events for specified evidence,
    sorted chronologically from intake to most recent action.
    
    Args:
        evidence_id: UUID of evidence to retrieve timeline for
        
    Returns:
        TimelineResponse with ordered list of custody events
        
    Raises:
        HTTPException 404: Evidence not found
        HTTPException 403: User lacks VIEW_EVIDENCE permission
        
    Example:
        GET /evidence/550e8400-e29b-41d4-a716-446655440000/timeline
        Authorization: Bearer eyJ0eXAiOiJKV1Q...
        
        Response:
        {
            "evidence_id": "550e8400-e29b-41d4-a716-446655440000",
            "events": [
                {
                    "tx_id": "550e8400-e29b-41d4-a716-446655440001",
                    "action": "INTAKE",
                    "timestamp": "2026-04-01T10:30:00Z",
                    "actor_user_id": "officer1",
                    "actor_org_id": "KPS"
                }
            ]
        }
    """
    try:
        require_action(principal, Action.VIEW_EVIDENCE)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    # ... implementation ...
```

---

### Quick Win #2: Replace Lambda Rollback Actions

**Script to find all lambdas:**
```bash
grep -n "lambda:" app/main.py app/error_handler.py
```

**Fix each one:**
```python
# ❌ Before
ctx.add_rollback(RollbackAction(
    name="cleanup",
    action=lambda: shutil.rmtree(temp_dir)
))

# ✅ After
ctx.add_rollback(RollbackAction(
    name="cleanup",
    action_type="remove_dir",
    args={"path": str(temp_dir)}
))
```

---

### Quick Win #3: Add Health Check Endpoint

```python
# Add to app/main.py

@app.get("/health/detailed")
def detailed_health():
    """Get detailed system health status."""
    import os
    
    # Check database
    try:
        store.get_connection()
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    # Check ledger
    try:
        ok, msg = ledger.validate_chain()
        ledger_status = "valid" if ok else "corrupted"
    except:
        ledger_status = "error"
    
    # Check encryption
    encryption = evidence_cipher.status()
    
    # Check file system
    fs_status = "ok" if settings.evidence_store_dir.exists() else "error"
    
    return {
        "status": "ok" if all([
            db_status == "connected",
            ledger_status == "valid",
            fs_status == "ok"
        ]) else "degraded",
        "checks": {
            "database": db_status,
            "ledger": ledger_status,
            "encryption": encryption.enabled,
            "filesystem": fs_status,
            "timestamp": utcnow_iso()
        }
    }
```

---

---

## Implementation Checklist

Use this checklist to track fixes:

### Critical Issues
- [ ] Issue #1: Set MASTER_KEY_PASSWORD
- [ ] Issue #2: Implement user database
- [ ] Issue #3: PostgreSQL migration planning

### High Priority
- [ ] Issue #4: Add response_models (audit endpoints)
- [ ] Issue #4: Add response_models (security endpoints)
- [ ] Issue #4: Add response_models (search endpoints)
- [ ] Issue #5: Email validation in signup
- [ ] Issue #6: Standardize pagination defaults
- [ ] Issue #7: Replace lambda rollbacks

### Medium Priority
- [ ] Issue #8: Add deprecation warning for X-User-Id
- [ ] Issue #9: Improve encryption error handling
- [ ] Quick Win #1: Add endpoint docstrings
- [ ] Quick Win #2: Replace all lambda rollbacks
- [ ] Quick Win #3: Add detailed health check

### Testing
- [ ] Run tests after each fix: `pytest tests/ -v`
- [ ] Check for new warnings
- [ ] Verify endpoints work with curl/Postman

---

**Total Estimated Time to Address All Issues: 4-6 weeks (distributed)**

---

*Technical remediation guide generated: April 1, 2026*
