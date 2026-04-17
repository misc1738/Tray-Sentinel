# Tracey's Sentinel: User Data Flow & Storage Guide

## 🔍 Complete User Journey

### Phase 1: Authentication
```
User visits http://localhost:8000
  ↓
Redirected to /auth.html (login page)
  ↓
User enters credentials
  ↓
Backend validates via /auth/login endpoint
  ↓
JWT token + user info stored in localStorage:
  - auth_token (JWT)
  - user_id
  - user_role
  - org_id
  ↓
Redirected to /index.html (main dashboard)
```

**Login Credentials (Default):**
- Username: `operator@kps.gov`
- Password: `password123` (from app/auth.py)

---

## 📤 Evidence Intake Flow

### Phase 2: Upload Evidence
```
User clicks "Evidence Intake Scanner" tab
  ↓
Selects files from disk (File Input)
  ↓
Fills in form:
  - Case ID (e.g., "KPS-CASE-0001")
  - Description (optional)
  ↓
Clicks "Submit Evidence" button
  ↓
Browser converts file to Base64
  ↓
Sends POST to /evidence/intake with:
  {
    "case_id": "KPS-CASE-0001",
    "description": "Surveillance video",
    "file_name": "footage.mp4",
    "file_bytes_b64": "AAEBAgMEBQYHCAk...",
    "source_device": "web-upload",
    "acquisition_method": "file_upload"
  }
```

**Code Location:** [static/app.js](static/app.js#L1162-L1240)

---

## 💾 Backend Processing

### Phase 3: Server-Side Storage

**Endpoint:** `POST /evidence/intake` ([app/main.py](app/main.py#L477))

1. **Authentication Check**
   - Validates JWT token
   - Checks RBAC permissions (require `REGISTER_EVIDENCE` action)

2. **File Validation**
   - Decodes base64
   - Checks file size (max 100 MB)
   - Verifies file extension is safe

3. **Cryptographic Processing**
   - Calculates SHA-256 hash of file
   - Encrypts file with Fernet (AES-128)
   - Signs request with Ed25519

4. **Database Storage**
   - Stores metadata in SQLite
   - Saves encrypted file to disk
   - Records in append-only ledger

---

## 📁 File Storage Locations

### SQLite Database
```
data/sentinel.db
├── evidence (table)
│  ├── evidence_id (UUID)
│  ├── case_id
│  ├── description
│  ├── file_name
│  ├── sha256 (hash)
│  └── created_at (timestamp)
│
└── evidence_file (table)
   ├── evidence_id (UUID)
   └── file_path (on disk location)
```

**Location:** `data/sentinel.db`

### Evidence Files
```
evidence_store/
├── {evidence_id_1}/
│  └── original_file_name
├── {evidence_id_2}/
│  └── original_file_name
└── {evidence_id_3}/
   └── original_file_name
```

**Location:** `evidence_store/` directory

**Status:** Files are encrypted at rest

### Audit Ledger
```
data/ledger.jsonl (append-only log)
```

Each line contains:
```json
{
  "ledger_id": "uuid",
  "sequence": 1,
  "event_type": "INTAKE",
  "actor_user_id": "operator@kps.gov",
  "resource_id": "evidence_uuid",
  "timestamp": "2026-04-17T...",
  "prev_hash": "sha256...",
  "current_hash": "sha256...",
  "signature": "ed25519..."
}
```

---

## 🗄️ Database Schema

### Evidence Table
```sql
CREATE TABLE evidence (
    evidence_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    description TEXT NOT NULL,
    source_device TEXT,
    acquisition_method TEXT NOT NULL,
    file_name TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

-- Indexes for fast queries
CREATE INDEX idx_evidence_case_id ON evidence(case_id);
CREATE INDEX idx_evidence_sha256 ON evidence(sha256);
CREATE INDEX idx_evidence_created_at ON evidence(created_at);
```

### Evidence File Mapping
```sql
CREATE TABLE evidence_file (
    evidence_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id)
);
```

---

## 🔧 Database Fixes & Optimization

### Issue 1: Duplicate SHA256 Values
**Problem:** Two evidence items with same hash causes constraint violation

**Solution:**
```sql
-- Check for duplicates
SELECT sha256, COUNT(*) as count FROM evidence GROUP BY sha256 HAVING count > 1;

-- Delete duplicates (keep first one)
DELETE FROM evidence WHERE evidence_id NOT IN (
    SELECT MIN(evidence_id) FROM evidence GROUP BY sha256
);
```

### Issue 2: Missing Foreign Key Integrity
**Problem:** Evidence files exist without metadata records

**Solution:**
```sql
-- Find orphaned file records
SELECT ef.evidence_id FROM evidence_file ef
LEFT JOIN evidence e ON ef.evidence_id = e.evidence_id
WHERE e.evidence_id IS NULL;

-- Delete orphaned records
DELETE FROM evidence_file where evidence_id NOT IN (SELECT evidence_id FROM evidence);
```

### Issue 3: Corrupted Ledger
**Problem:** Ledger entries have invalid hashes

**Solution:** Rebuild from database
```python
from app.ledger import Ledger
ledger = Ledger(Path("data/sentinel.db"))
ledger.rebuild_from_database()  # Regenerates valid ledger
```

---

## 🚀 Testing the Flow

### 1. Start the Server
```bash
npm run dev
```

### 2. Access Dashboard
```
http://localhost:8000
```

### 3. Login
```
User: operator@kps.gov
Pass: password123
```

### 4. Upload Evidence
1. Go to "Evidence Intake Scanner" tab
2. Click "Upload Evidence Files"
3. Select a test file
4. Fill in Case ID: `KPS-CASE-TEST-001`
5. Click "Submit Evidence"

### 5. Verify Storage
```bash
# Check database
sqlite3 data/sentinel.db "SELECT * FROM evidence LIMIT 1;"

# Check file storage
ls -la evidence_store/
```

---

## 📊 API Endpoints for Data

### Evidence Management
```
POST   /evidence/intake              # Upload evidence
GET    /evidence/{id}                # Get evidence details
POST   /evidence/{id}/verify         # Verify integrity
POST   /evidence/{id}/transfer       # Transfer custody
POST   /evidence/{id}/endorsement    # Request endorsement
```

### Case Management
```
GET    /case/{id}                    # Get case info
GET    /case/{id}/evidence           # List evidence in case
GET    /case/{id}/audit              # Get audit trail
GET    /case/{id}/timeline           # Get custody timeline
```

### Search & Query
```
GET    /search?query=...             # Full-text search
GET    /search/advanced?...          # Advanced filters
```

---

## 🔐 Data Security

### Encryption
- **At Rest:** Fernet (AES-128) via `app/evidence_crypto.py`
- **In Transit:** HTTPS/TLS recommended
- **Keys:** Stored in `data/keys/` directory

### Hashing
- **Algorithm:** SHA-256
- **Purpose:** Integrity verification
- **Ledger:** Each custody event is cryptographically signed with Ed25519

### Access Control
- **Authentication:** JWT tokens
- **Authorization:** Role-Based Access Control (RBAC)
- **Audit:** Every action logged with actor, timestamp, IP

---

## 🛠️ Database Maintenance

### Backup Database
```bash
cp data/sentinel.db backups/sentinel.db.backup
```

### Check Database Integrity
```bash
sqlite3 data/sentinel.db "PRAGMA integrity_check;"
```

### Optimize Database
```bash
sqlite3 data/sentinel.db "VACUUM;"
```

### View Evidence Count
```bash
sqlite3 data/sentinel.db "SELECT COUNT(*) as total_evidence FROM evidence;"
```

### List All Cases
```bash
sqlite3 data/sentinel.db "SELECT DISTINCT case_id FROM evidence;"
```

---

## 📋 Summary: Data Flow Diagram

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ 1. User fills form
       │    (case_id, description, file)
       │
       ▼
┌─────────────────┐
│  JavaScript     │
│  (app.js)       │ 2. Convert to Base64
│                 │    Build JSON payload
└──────┬──────────┘
       │
       ▼
┌─────────────────────────────────┐
│  POST /evidence/intake          │
│  (app/main.py)                  │
└──────┬──────────────────────────┘
       │
       ├─→ 3. Validate auth (JWT)
       │   4. Check RBAC permission
       │   5. Verify file size
       │
       ├─→ 6. Calculate SHA-256
       │   7. Encrypt file (Fernet)
       │   8. Sign transaction (Ed25519)
       │
       ├─→ 9. Insert into evidence table (SQLite)
       │   10. Insert into evidence_file table
       │   11. Append to ledger.jsonl
       │
       ▼
┌───────────────────────────┐
│  Response JSON            │
│  {                        │
│    "evidence_id": "uuid"  │
│    "sha256": "hash..."    │
│    "created_at": "time"   │
│  }                        │
└───────────────────────────┘
```

---

## ❓ FAQ

**Q: Where can users see uploaded evidence?**
A: Dashboard tab "Evidence Intelligence Center" shows stats. Individual evidence can be viewed via Case pages.

**Q: Is data encrypted?**
A: Yes. Files are encrypted with Fernet (AES-128) before storage.

**Q: How is evidence integrity verified?**
A: SHA-256 hashing + cryptographic ledger with Ed25519 signatures provide tamper-evidence.

**Q: Can evidence be deleted?**
A: No. Ledger is append-only (immutable). Only custody events are recorded, never deletions.

**Q: Where are backups stored?**
A: `backups/` directory. Manual backups recommended before critical operations.

**Q: Can I use PostgreSQL instead of SQLite?**
A: Yes. Set `DATABASE_URL=postgresql://user:pass@host/db` in `.env`
