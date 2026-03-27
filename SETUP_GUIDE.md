# 🚀 Tracey's Sentinel - Complete Setup & Enhancement Guide

## ✨ What's New - Authentication System Implementation

This project has been significantly enhanced with a fully functional authentication system, improved UI/UX, and additional features for secure forensic evidence management.

### Recent Enhancements

1. **🔐 Full Authentication System**
   - Created dedicated login/signup pages (`auth.html`)
   - Session-based authentication with token storage
   - User registration system with role and organization assignment
   - Logout functionality

2. **👥 User Profile Display**
   - Real-time user information in header
   - Role and organization display
   - Quick logout button

3. **🔧 Backend Authentication APIs**
   - POST `/auth/login` - User login
   - POST `/auth/signup` - User registration
   - POST `/auth/logout` - Session termination
   - Enhanced CORS configuration for localhost

4. **🎨 UI/UX Improvements**
   - Professional login/signup page with gradient design
   - Error handling and validation
   - Loading states for form submissions
   - Demo user quick-access feature
   - Password confirmation validation

---

## 📋 Prerequisites

- **Python**: 3.11+ (tested on 3.14)
- **Node.js**: 18+ (optional, for frontend development)
- **pip** or virtual environment manager

---

## 🔧 Backend Setup & Installation

### Step 1: Create Virtual Environment

```powershell
# Navigate to project directory
cd "c:\path\to\Tracey's Sentinel"

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# If you get execution policy error:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Step 2: Install Dependencies

```powershell
# Install required packages
pip install -r requirements.txt
```

### Step 3: Create Data Directories

```powershell
# Create necessary directories
mkdir -Force data/keys
mkdir -Force evidence_store
```

### Step 4: Start Backend Server

```powershell
# Start FastAPI server with hot-reload
uvicorn app.main:app --reload --port 8000

# Or without hot-reload for production:
uvicorn app.main:app --port 8000
```

**Backend will be available at**: `http://127.0.0.1:8000`

---

## 🌐 Frontend Setup (Optional)

The frontend is served directly by FastAPI in production mode. For development with hot-reload:

### Step 1: Install Frontend Dependencies (Optional)

```powershell
cd frontend
npm install
npm run dev
```

**Frontend dev server**: `http://127.0.0.1:5173`

### Step 2: Production Build

```powershell
npm run build
```

---

## 🔑 Authentication Flow

### Login/Registration

1. **Visit the Application**
   - Go to `http://127.0.0.1:8000` or `http://localhost:8000`
   - You'll be redirected to `auth.html` if not authenticated

2. **Create Account or Login**
   - **New Users**: Click "Sign Up" and fill in:
     - User ID (minimum 3 characters)
     - Email address
     - Role (Field Officer, Forensic Analyst, Supervisor, Prosecutor, Judge, System Auditor)
     - Organization ID (e.g., KPS, FORENSIC_LAB, ODPP)
     - Password (minimum 8 characters)
   
   - **Existing Users**: Use demo credentials below

3. **Demo Users** (Pre-configured for testing)
   ```
   Username: officer1      | Role: Field Officer    | Org: KPS
   Username: analyst1      | Role: Forensic Analyst | Org: FORENSIC_LAB
   Username: supervisor1   | Role: Supervisor       | Org: KPS
   Username: prosecutor1   | Role: Prosecutor       | Org: ODPP
   Username: judge1        | Role: Judge            | Org: JUDICIARY
   Username: auditor1      | Role: System Auditor   | Org: INTERNAL_AUDIT
   
   Password (all): demo123
   ```

4. **After Login**
   - Access the main dashboard at `http://127.0.0.1:8000`
   - User information displayed in header (user ID, role, organization)
   - Click "Logout" button to end session

---

## 📊 API Endpoints

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Authenticate user and get session token |
| POST | `/auth/signup` | Register new user account |
| POST | `/auth/logout` | End user session |
| GET | `/auth/users` | List all available demo users |

### Evidence Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/evidence/intake` | Register new evidence |
| POST | `/evidence/event` | Record custody event |
| POST | `/evidence/endorse` | Endorse evidence transaction |
| POST | `/evidence/{evidence_id}/verify` | Verify evidence integrity |
| GET | `/evidence/{evidence_id}/timeline` | Get evidence custody timeline |
| GET | `/evidence/{evidence_id}/report` | Generate court report |
| GET | `/evidence/{evidence_id}/bundle` | Download evidence bundle (ZIP) |

### Case Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/case/{case_id}` | Get case summary |
| GET | `/case/{case_id}/audit` | Get case audit report |

### System Functions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health check |
| GET | `/security/posture` | Security posture assessment |
| GET | `/monitoring/dashboard` | Security monitoring data |

---

## 🧪 Testing the System

### 1. Test Login with cURL

```powershell
$body = @{
    user_id = "officer1"
    password = "demo123"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/auth/login" `
    -Method Post `
    -Headers @{"Content-Type"="application/json"} `
    -Body $body

$response | ConvertTo-Json
```

### 2. Test Health Endpoint

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get | ConvertTo-Json
```

### 3. Use Demo Client

```powershell
# Run the provided demo client
python demo_client.py
```

### 4. Run Test Suite

```powershell
# Run all tests
pytest -v

# Run specific test file
pytest tests/test_case_audit.py -v

# Run with coverage
pytest --cov=app --cov-report=html
```

---

## 📁 Project Structure

```
Tracey's Sentinel/
├── app/                          # Backend application
│   ├── main.py                  # FastAPI application entry point
│   ├── auth.py                  # Authentication & session management
│   ├── models.py                # Pydantic data models
│   ├── storage.py               # Database & file storage
│   ├── ledger.py                # Append-only custody ledger
│   ├── signing.py               # Ed25519 cryptographic signing
│   ├── evidence_crypto.py        # Evidence encryption/decryption
│   ├── rbac.py                  # Role-based access control
│   ├── compliance.py            # Compliance tracking
│   ├── audit_logger.py          # Audit logging
│   ├── search.py                # Full-text search
│   ├── metrics.py               # Performance metrics
│   ├── webhooks.py              # Event webhooks
│   └── ...
├── static/                      # Frontend application
│   ├── index.html               # Main dashboard
│   ├── auth.html                # Login/signup page (NEW)
│   ├── case.html                # Case management
│   ├── app.js                   # Main application logic
│   ├── auth.js                  # Authentication logic (NEW)
│   ├── case.js                  # Case management logic
│   ├── style.css                # Application styling
│   └── ...
├── tests/                       # Automated tests
│   ├── test_evidence_encryption.py
│   ├── test_ledger_integrity.py
│   ├── test_case_audit.py
│   └── ...
├── data/
│   ├── sentinel.db              # SQLite metadata
│   ├── ledger.jsonl             # Append-only custody log
│   ├── keys/                    # Cryptographic keys
│   │   ├── evidence.fernet.key  # Evidence encryption key
│   │   └── *.ed25519.pem        # User signing keys
│   └── users.json               # Registered users (storage)
├── evidence_store/              # Encrypted evidence storage
│   └── {evidence_id}/           # Per-evidence directory
│       └── {filename}           # Encrypted evidence file
├── requirements.txt             # Python dependencies
├── README.md                    # Main documentation
└── SETUP_GUIDE.md              # This file
```

---

## 🔒 Security Notes

### Current Implementation (Prototype)

- ✅ Evidence encryption at rest (Fernet)
- ✅ Cryptographic evidence integrity (SHA-256)
- ✅ Transaction signing (Ed25519)
- ✅ Append-only ledger with hash-chain validation
- ✅ Role-based access control (RBAC)
- ✅ Session-based authentication with tokens
- ⚠️ Plaintext passwords in demo (for testing only)

### Production Recommendations

1. **Replace Header-Based Auth**
   - Implement OAuth2 with PKCE
   - Use JWT tokens with short expiration
   - Add refresh token mechanism

2. **Key Management**
   - Use HSM (Hardware Security Module) for key storage
   - Implement key rotation policies
   - Store keys in dedicated vault (HashiCorp Vault, AWS KMS, etc.)

3. **Network Security**
   - Deploy with TLS/SSL certificates
   - Implement mTLS for service-to-service communication
   - Add WAF (Web Application Firewall) rules

4. **Monitoring & Logging**
   - Centralize audit logs (SIEM)
   - Set up real-time alerts
   - Implement log retention policies

5. **Database Security**
   - Use encrypted database connections
   - Enable database-level encryption
   - Implement backup encryption and retention

---

## 🐛 Troubleshooting

### Port Already in Use

```powershell
# Find process using port 8000
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess

# Kill process (replace PID)
Stop-Process -Id <PID> -Force

# Use different port
uvicorn app.main:app --port 8001
```

### Virtual Environment Issues

```powershell
# Deactivate and remove old env
deactivate
Remove-Item .venv -Recurse -Force

# Create fresh environment
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Authentication Not Working

1. Check that backend is running: `http://127.0.0.1:8000/health`
2. Verify CORS settings in `app/main.py`
3. Clear browser cache and localStorage
4. Check browser developer console (F12) for errors
5. Verify user exists with `GET /auth/users`

### Database Issues

```powershell
# Reset database (WARNING: deletes all data)
Remove-Item data/sentinel.db -Force -ErrorAction SilentlyContinue
Remove-Item data/ledger.jsonl -Force -ErrorAction SilentlyContinue
Remove-Item data/keys -Recurse -Force -ErrorAction SilentlyContinue

# Restart backend
```

---

## 📚 Additional Features

### Audit Logging
Track all user activities with flexible queries:
- Query by event type, actor, resource, status
- Actor activity tracking
- Compliance reporting

### Search & Filtering
- Full-text evidence search
- Advanced filtering by case, status, date range
- Index statistics

### Rate Limiting
- Per-IP rate limiting (100 requests/minute)
- Automatic old record cleanup
- Configurable thresholds

### Performance Metrics
- API latency tracking
- Endpoint-level statistics
- Slow query detection

### Webhooks
- Event-driven subscriptions
- Support for evidence, custody, endorsement events
- Delivery tracking and retry logic

---

## 📞 Support

For issues or questions:
1. Check the main [README.md](README.md)
2. Review [BACKEND_ENHANCEMENTS.md](BACKEND_ENHANCEMENTS.md)
3. Check test files in `tests/` directory
4. Enable debug logging in backend

---

## 📝 License & Status

Prototype project for forensic process demonstration. Not production-certified.
See [README.md](README.md) for full details.
