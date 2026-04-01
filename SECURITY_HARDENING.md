# Security Hardening Guide - Tracey's Sentinel

## Overview
This guide provides comprehensive security hardening recommendations for production deployment of Tracey's Sentinel.

## Critical Issues Fixed in v0.2.0

✅ **Password Hashing**: Upgraded from SHA256 to bcrypt  
✅ **JWT Secret Management**: Now requires environment variable (not hardcoded)  
✅ **Ledger Concurrency**: Added thread-safe file locking  
✅ **Database Indexes**: Performance optimization to prevent scan-based attacks  
✅ **Audit Logging**: Enhanced structured logging for compliance  
✅ **Request Limits**: Pagination and rate limiting enforced

## Authentication & Authorization

### 1. JWT Configuration

**Current Implementation:**
```python
# .env
JWT_SECRET_KEY=<min-32-character-random-string>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

**Hardening Steps:**
- [ ] Generate strong JWT secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] Enable JWT signature verification in all routes
- [ ] Rotate JWT_SECRET_KEY periodically (implementing a key versioning system)
- [ ] Add jti (JWT ID) claim to prevent token reuse
- [ ] Monitor for token expiry and force re-authentication

### 2. Multi-Factor Authentication (MFA)

Implement TOTP or WebAuthn:

```python
# Future enhancement: app/mfa.py
import pyotp

def generate_mfa_secret(user_id: str) -> str:
    """Generate TOTP secret for user."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    qr_url = totp.provisioning_uri(name=user_id, issuer_name='TraceySentinel')
    return secret, qr_url

def verify_mfa_token(secret: str, token: str) -> bool:
    """Verify TOTP token."""
    totp = pyotp.TOTP(secret)
    return totp.verify(token)
```

### 3. Session Management

**Security Requirements:**
- [ ] Sessions expire after inactivity (30-60 minutes for regular users)
- [ ] Sessions stored in secure, encrypted database (not in-memory)
- [ ] Session tokens include user context (user_id, org_id, role)
- [ ] Logout invalidates session immediately
- [ ] Concurrent session limits (max 3 per user)

## Data Protection

### 1. Encryption at Rest

**Current Implementation:**
```python
# Evidence encryption using Fernet (AES-128-CBC)
from app.evidence_crypto import EvidenceCipher
cipher = EvidenceCipher(key_path="data/keys/evidence.fernet.key")
encrypted = cipher.encrypt_for_storage(raw_bytes)
```

**Hardening:**
- [ ] Use AES-256-GCM instead of Fernet for new implementations
- [ ] Rotate encryption keys annually
- [ ] Store encryption keys separately from data (use key management service)
- [ ] Enable automatic re-encryption on key rotation
- [ ] Verify encryption on startup: `cipher.validate_encryption()`

### 2. Encryption in Transit

**Requirements:**
- [ ] TLS 1.3+ enforced
- [ ] HSTS header enabled: `Strict-Transport-Security: max-age=31536000`
- [ ] Certificate pinning for API clients
- [ ] mTLS for service-to-service communication

```python
# FastAPI HTTPS configuration
if environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["sentinel.example.com"],
    )
    # Enable HTTPS redirect
    # Use reverse proxy (nginx) to enforce TLS
```

### 3. Database Security

**PostgreSQL Configuration:**
```sql
-- Enable SSL connections
ssl = on
ssl_cert_file = '/etc/postgresql/server.crt'
ssl_key_file = '/etc/postgresql/server.key'

-- Restrict authentication
CREATE ROLE sentinel_app LOGIN PASSWORD 'strong_password';
GRANT CONNECT ON DATABASE sentinel TO sentinel_app;
GRANT USAGE ON SCHEMA public TO sentinel_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO sentinel_app;

-- Disable superuser access
ALTER ROLE sentinel_app NOSUPERUSER;
```

## Access Control

### 1. Role-Based Access Control (RBAC)

**Current Roles:**
- FIELD_OFFICER: Register evidence, record events
- FORENSIC_ANALYST: Analyze evidence, record events
- SUPERVISOR: Generate reports, supervise analysts
- PROSECUTOR: View evidence, generate reports
- JUDGE: View evidence, review reports
- SYSTEM_AUDITOR: Audit logs, compliance reports

**Hardening:**
- [ ] Implement attribute-based access control (ABAC) for finer granularity
- [ ] Add organization-level permissions
- [ ] Implement time-limited role elevation (sudo-like capability)
- [ ] Require re-authentication for sensitive operations

### 2. Rate Limiting

**Current Configuration:**
```python
# app/rate_limiter.py
RATE_LIMIT = 100  # requests per minute per IP
```

**Production Hardening:**
- [ ] Increase strict rate limiting on authentication endpoints: 5 attempts/minute
- [ ] Implement exponential backoff on failed login attempts
- [ ] Block IPs after 10 consecutive failed attempts for 15 minutes
- [ ] Maintain separate rate limits per API key/user

## Audit & Logging

### 1. Comprehensive Audit Logging

All sensitive operations must be logged:

```python
audit_logger.log_event(
    audit_id=str(uuid.uuid4()),
    event_type=AuditEventType.EVIDENCE_INTAKE,
    actor_user_id=principal.user_id,
    actor_org_id=principal.org_id,
    resource_type="evidence",
    resource_id=evidence_id,
    action="INTAKE",
    status="SUCCESS",
    ip_address=_get_client_ip(request),
    details={
        "file_name": file_name,
        "file_size": file_size,
        "sha256": sha256,
    }
)
```

**Retention Policy:**
- [ ] Audit logs: 7 years (forensic standard)
- [ ] API request logs: 90 days
- [ ] Security events: 2 years
- [ ] Application logs: 30 days

### 2. Log Integrity

- [ ] Use write-once storage (WORM) for audit logs
- [ ] Cryptographically sign log entries
- [ ] Forward logs to centralized logging system (ELK, Splunk, Datadog)
- [ ] Alert on suspicious patterns

```python
def sign_audit_log_batch(logs: list[dict]) -> dict:
    """Sign a batch of audit logs for integrity verification."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    
    batch_content = json.dumps(logs, sort_keys=True)
    with open("keys/audit_signing.key", "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
    
    signature = private_key.sign(
        batch_content.encode(),
        padding.PSS(padding.SHA256()),
    )
    return {
        "logs": logs,
        "signature": signature.hex(),
        "timestamp": datetime.utcnow().isoformat(),
    }
```

## Network Security

### 1. API Security Headers

```python
# app/main.py
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

### 2. CORS Configuration

**Restrict to known origins:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_URL", "http://localhost:5173")
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)
```

### 3. Input Validation

- [ ] Validate all file uploads (magic bytes, size, format)
- [ ] Sanitize all user input to prevent injection attacks
- [ ] Use parameterized queries for all database operations
- [ ] Implement request size limits

```python
# Validation example
def validate_evidence_intake(request: EvidenceIntakeRequest) -> bool:
    # File size validation
    file_size = len(base64.b64decode(request.file_bytes_b64))
    if file_size > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError("File exceeds maximum size")
    
    # File format validation
    magic_bytes = base64.b64decode(request.file_bytes_b64)[:4]
    allowed_magic_bytes = [b'%PDF', b'\x89PNG', b'\xFF\xD8']
    if magic_bytes not in allowed_magic_bytes:
        raise ValueError("Unsupported file format")
    
    return True
```

## Deployment Security

### 1. Container Security (Docker)

```dockerfile
# Use minimal base image
FROM python:3.12-slim

# Run as non-root user
RUN useradd -m -u 1000 sentinel
USER sentinel

# Use pip-audit to check dependencies
RUN pip install --no-cache-dir -U pip && \
    pip install pip-audit && \
    pip-audit

# Security scanning on build
# RUN trivy image --severity HIGH,CRITICAL
```

### 2. Environment Variables

Never commit secrets to version control:

```bash
# .gitignore
.env
.env.local
data/keys/
data/ledger.jsonl
```

Use a secrets management system:
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault

### 3. Infrastructure Security

- [ ] Run application behind WAF (Web Application Firewall)
- [ ] Use reverse proxy (nginx) with security modules (modsecurity)
- [ ] Enable VPC/network isolation
- [ ] Use security groups to restrict access
- [ ] Enable cloud provider DDoS protection

## Vulnerability Management

### 1. Dependency Scanning

```bash
# Check for vulnerable dependencies
pip install safety
safety check

# Generate SBOM (Software Bill of Materials)
pip install cyclonedx-bom
cyclonedx-bom -o sbom.xml
```

### 2. SAST (Static Application Security Testing)

```bash
# Python security linter
pip install bandit
bandit -r app/

# Type checking
mypy app/
```

### 3. Secret Detection

```bash
# Scan for accidentally committed secrets
pip install detect-secrets
detect-secrets scan --baseline .secrets.baseline
```

## Incident Response

### 1. Security Monitoring

Monitor these events:
- Multiple failed login attempts
- Unauthorized access attempts
- Evidence tampering (hash mismatch)
- Chain-of-custody violations
- Unusual data access patterns

```python
# Alert on suspicious activity
if audit_logger.get_failed_actions(days=1):
    send_security_alert(
        severity="HIGH",
        event="Multiple failed authentication attempts detected"
    )
```

### 2. Breach Response Plan

1. **Detection**: Automated alerts on suspicious activity
2. **Containment**: Isolate affected systems, revoke compromised credentials
3. **Investigation**: Review audit logs, identify scope
4. **Communication**: Notify affected parties, law enforcement (if required)
5. **Recovery**: Restore from backups, deploy patches
6. **Post-Incident**: Root cause analysis, prevent recurrence

## Compliance Checklist

- [ ] NIST Cybersecurity Framework compliance
- [ ] GDPR compliance (if storing PII)
- [ ] HIPAA compliance (if handling health data)
- [ ] FIPS 140-2 compliance (if required by jurisdiction)
- [ ] Chain of custody standards (NFSTC, AAFS)
- [ ] Regular security assessments
- [ ] Penetration testing (annual)
- [ ] Third-party security audit (annual or bi-annual)

## References

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- NIST Cybersecurity Framework: https://www.nist.gov/cyberframework
- CWE Top 25: https://cwe.mitre.org/top25/
- SANS Top 25: https://www.sans.org/top25-software-errors/
