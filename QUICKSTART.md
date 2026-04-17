# Quick Start: How to Use Tracey's Sentinel

## 🚀 Getting Started (2 minutes)

### 1. Start the Server
```bash
npm run dev
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 2. Open in Browser
```
http://127.0.0.1:8000
```

### 3. Login
```
Email: operator@kps.gov
Password: password123
```

---

## 📤 Upload Your First Evidence

### Step 1: Navigate to Evidence Intake
1. You'll see a dashboard with several tabs at the top
2. Click the **"Evidence Intake Scanner"** tab

### Step 2: Fill in the Form

You'll see a form with two sections:

**Section A: Upload Evidence Files**
- Click "📁 Upload Evidence Files" button
- Select a file from your computer (any file type: PDF, JPG, MP4, ZIP, etc.)
- The file preview will show in a list

**Section B: Case Information**
- **Case ID**: Enter something like `KPS-CASE-001` or `ROBBERY-2026-042`
- **Description**: (Optional) Write what this evidence is about

### Step 3: Submit
- Click **"Submit Evidence"** button
- Watch the progress bar as files upload
- You'll see success notifications for each file

---

## ✅ Verify Upload Success

### In the Dashboard
1. Go back to the **"Evidence Intelligence Center"** tab
2. You should see **"Total Evidence"** counter increase
3. Your uploaded file SHA-256 hash is stored (tamper-proof)

### Via Database
```bash
sqlite3 data/sentinel.db "SELECT evidence_id, file_name, case_id FROM evidence;"
```

### Via API
```bash
curl http://127.0.0.1:8000/docs
```
Then try the `GET /evidence/{id}` endpoint with your evidence ID

---

## 🔍 Find Your Evidence

### Option 1: Dashboard Search
- Browse the "Evidence Intelligence Center" tab
- Evidence is organized by case

### Option 2: Direct API Call
```bash
# Get all evidence for a case
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://127.0.0.1:8000/case/KPS-CASE-001/evidence
```

### Option 3: Database Query
```bash
sqlite3 data/sentinel.db \
  "SELECT * FROM evidence WHERE case_id = 'KPS-CASE-001';"
```

---

## 🔐 What Happens Behind the Scenes

When you upload a file:

1. **File Processing**
   - Browser converts file to Base64
   - Sends to backend API

2. **Server Validation**
   - Checks authentication (JWT token)
   - Verifies permissions (RBAC)
   - Validates file size (max 100 MB)

3. **Cryptographic Security**
   - Calculates SHA-256 hash (fingerprint)
   - Encrypts file with AES-128 (Fernet)
   - Signs transaction with Ed25519

4. **Storage**
   - Metadata → SQLite database
   - Encrypted file → `evidence_store/` directory
   - Event → Append-only ledger (`data/ledger.jsonl`)

5. **Response**
   - Returns evidence ID (UUID)
   - Returns SHA-256 hash
   - Shows confirmation message

---

## 📊 View Your Data

### Database Location
```
data/sentinel.db
```

### File Storage
```
evidence_store/
├── {evidence-id-1}/
│   └── filename.pdf          (encrypted)
├── {evidence-id-2}/
│   └── screenshot.png        (encrypted)
└── {evidence-id-3}/
   └── archive.zip           (encrypted)
```

### Audit Trail
```
data/ledger.jsonl             (tamper-proof log)
```

---

## 🛠️ Useful Commands

### Check Database Health
```bash
# Run verification
python db_verify.py

# Fix any issues
python db_verify.py fix
```

### View Database
```bash
# View all evidence
sqlite3 data/sentinel.db "SELECT * FROM evidence;"

# Count items by case
sqlite3 data/sentinel.db \
  "SELECT case_id, COUNT(*) FROM evidence GROUP BY case_id;"

# View audit logs
sqlite3 data/sentinel.db "SELECT * FROM audit_logs LIMIT 10;"
```

### API Documentation
```
http://127.0.0.1:8000/docs              (Swagger UI)
http://127.0.0.1:8000/redoc             (ReDoc)
```

---

## 🆘 Troubleshooting

### Issue: "No files selected"
**Solution:** Make sure you clicked the upload button and selected a file

### Issue: "Case ID is required"
**Solution:** Enter a case ID in the text field (e.g., `KPS-2026-001`)

### Issue: Upload fails with 403 error
**Solution:** Check that you're logged in with valid credentials

### Issue: Large file upload is slow
**Solution:** This is normal. Files are encrypted before storage. Max size is 100 MB.

### Issue: "Database not found"
**Solution:** This happens on first run. Upload a file to initialize it.

---

## 📝 Example Test Scenarios

### Scenario 1: Surveillance Request
```
Case ID: "SURVEILLANCE-APR-2026"
Description: "CCTV footage from bank robbery"
File: surveillance.mp4 (5 MB)
```

### Scenario 2: Financial Records
```
Case ID: "FRAUD-CASE-001"
Description: "Bank statements and wire transfers"
File: financial_records.pdf (2 MB)
```

### Scenario 3: Multiple Evidence Items
```
Case ID: "MULTI-EVIDENCE-CASE"
Upload 1: suspect_photo.jpg
Upload 2: fingerprints.png
Upload 3: witness_statement.pdf
```

---

## 🔗 Architecture Overview

```
┌────────────────────────────────────────┐
│   Browser UI (index.html)              │
│   - Evidence Intake Form               │
│   - Dashboard with Stats               │
│   - Audit Trail Viewer                 │
└────────────┬───────────────────────────┘
             │ POST /evidence/intake
             │
┌────────────▼───────────────────────────┐
│   FastAPI Backend (app/main.py)        │
│   - JWT Authentication                 │
│   - RBAC Permission Checks             │
│   - File Encryption                    │
│   - Cryptographic Signing              │
└────────────┬───────────────────────────┘
             │
        ┌────┴────┐
        │          │
    ┌───▼──┐  ┌──▼────────────────┐
    │ SQLi │  │ evidence_store/    │
    │ te   │  │ (encrypted files)  │
    │ DB   │  └────────────────────┘
    └──────┘
        │
        └──→ data/ledger.jsonl (tamper-proof log)
```

---

## 📞 Next Steps

1. ✅ Upload some test evidence
2. ✅ View it in the dashboard
3. ✅ Check the database: `sqlite3 data/sentinel.db "SELECT * FROM evidence;"`
4. ✅ View audit logs: `sqlite3 data/sentinel.db "SELECT * FROM audit_logs;"`
5. ✅ Try the API docs: `http://localhost:8000/docs`

---

## 🎯 Key Files

| File | Purpose |
|------|---------|
| `static/index.html` | Main dashboard UI |
| `static/app.js` | Form handlers & API calls |
| `app/main.py` | API endpoints |
| `data/sentinel.db` | SQLite database |
| `evidence_store/` | Encrypted files |
| `data/ledger.jsonl` | Immutable audit log |
| `db_verify.py` | Health check tool |

---

**You're ready to go! 🚀 Start uploading evidence now.**
