# Tracey's Sentinel

Permissioned digital chain-of-custody platform for forensic evidence handling.

Tracey's Sentinel is a FastAPI + React system that captures evidence intake, records custody operations on a tamper-evident ledger, enforces role-based actions, tracks multi-organization endorsements, verifies integrity, and generates court-facing artifacts.

---

## Table of Contents

- [1) What this project does](#1-what-this-project-does)
- [2) System architecture](#2-system-architecture)
- [3) Cryptography and security controls](#3-cryptography-and-security-controls)
- [4) Data storage layout](#4-data-storage-layout)
- [5) API reference](#5-api-reference)
- [6) Frontend console](#6-frontend-console)
- [7) Local setup and run](#7-local-setup-and-run)
- [8) Demo workflow](#8-demo-workflow)
- [9) Testing](#9-testing)
- [10) Operational notes](#10-operational-notes)
- [11) Production hardening roadmap](#11-production-hardening-roadmap)

---

## 1) What this project does

### Core capabilities

- Registers evidence via secure intake (`POST /evidence/intake`)
- Computes and persists canonical evidence SHA-256
- Stores evidence bytes encrypted at rest
- Writes each custody action to an append-only JSONL ledger
- Cryptographically signs each ledger event with Ed25519
- Enforces role-based access control using actor identity header
- Supports endorsement thresholds by organization (example: `TRANSFER` requires 2 unique orgs)
- Verifies file integrity against registered hash (`POST /evidence/{id}/verify`)
- Produces timeline/report/bundle for court use (`/timeline`, `/report`, `/bundle`)
- Generates case-level audit/compliance summaries (`GET /case/{case_id}/audit`)

### Custody action types

- `INTAKE`
- `TRANSFER`
- `ACCESS`
- `ANALYSIS`
- `STORAGE`
- `COURT_SUBMISSION`
- `ENDORSE`

---

## 2) System architecture

### Backend (FastAPI)

- `app/main.py`
  - Route orchestration, auth dependency integration, response shaping
- `app/storage.py`
  - SQLite metadata storage + file path mapping
- `app/ledger.py`
  - Append-only hash-chain ledger; endorsement computation; signature validation
- `app/signing.py`
  - Ed25519 key management, sign/verify helpers
- `app/evidence_crypto.py`
  - Evidence-at-rest encryption/decryption (Fernet envelope)
- `app/rbac.py`
  - Roles, action permissions, endorsement thresholds
- `app/reporting.py`
  - Court report and case audit summary builders
- `app/bundle.py`, `app/pdf_report.py`
  - Court bundle and PDF generation

### Frontend (React + Vite)

- `frontend/src/App.jsx`
  - Animated operations console, evidence/case/security workflows
- `frontend/src/api.js`
  - API client + operator header wiring
- `frontend/src/styles.css`
  - Premium visual theme + motion effects

### High-level flow

1. Intake request arrives with base64 evidence payload
2. Backend computes SHA-256 of plaintext bytes
3. Evidence is encrypted and written to evidence store
4. Metadata is written to SQLite
5. Signed `INTAKE` event is appended to ledger JSONL
6. Later custody events/endorsements are appended as immutable rows
7. Verify/report/bundle operations read + decrypt evidence as required

---

## 3) Cryptography and security controls

### Evidence confidentiality at rest

- Evidence bytes are encrypted before disk write
- Envelope format: file content is prefixed with `TSENC1:` + Fernet token
- Fernet provides:
  - AES-128-CBC encryption
  - HMAC-SHA256 authentication
- Key file location: `data/keys/evidence.fernet.key`
- Backward compatibility: legacy plaintext files are still readable

### Evidence integrity

- Canonical integrity hash: SHA-256 of original plaintext bytes at intake
- Verification recomputes SHA-256 from decrypted bytes and compares to stored hash

### Ledger integrity

- Append-only JSONL record stream
- Every event includes:
  - `prev_hash` (links to prior event)
  - `record_hash` (hash of current canonical row)
- Chain validation checks record hash correctness and hash linkage

### Non-repudiation

- Every ledger event is signed with actor-specific Ed25519 key material
- Event includes signer public key and detached signature
- Validation verifies signature over canonical event payload

### Endorsement trust model

- Policies derive required unique endorser organizations per action type
- `TRANSFER` and `COURT_SUBMISSION` require 2 org endorsements
- Others require 1 org
- Endorsements are separate append-only `ENDORSE` events referencing target `tx_id`

### Security posture endpoint

- `GET /security/posture`
- Returns:
  - data locations
  - active cryptographic controls
  - evidence encryption key fingerprint (SHA-256)

---

## 4) Data storage layout

Project-relative storage:

- `data/sentinel.db`
  - Evidence metadata and evidence→file-path mapping
- `data/ledger.jsonl`
  - Append-only custody ledger
- `data/keys/<user_id>.ed25519.pem`
  - Actor signing private keys (prototype storage model)
- `data/keys/evidence.fernet.key`
  - Evidence-at-rest encryption key
- `evidence_store/<evidence_id>/<file_name>`
  - Encrypted evidence payload file

---

## 5) API reference

Base URL (local): `http://127.0.0.1:8000`

### Authentication header

All protected endpoints require:

- `X-User-Id: officer1 | analyst1 | supervisor1 | prosecutor1 | judge1 | auditor1`

### Health + identity + security

- `GET /health`
  - Validates full ledger chain and event signatures

- `GET /auth/users`
  - Lists prototype users, roles, and org IDs

- `GET /security/posture`
  - Returns storage locations and cryptographic control summary

### Evidence lifecycle

- `POST /evidence/intake`
  - Registers a new evidence item
  - Request fields:
    - `case_id`
    - `description`
    - `source_device` (optional)
    - `acquisition_method`
    - `file_name`
    - `file_bytes_b64`

- `POST /evidence/event`
  - Adds custody event for evidence
  - Request fields:
    - `evidence_id`
    - `action_type`
    - `details` (object)
    - `presented_sha256` (optional)
    - `endorse` (boolean)

- `POST /evidence/endorse`
  - Adds endorsement event for an existing transaction
  - Request fields:
    - `evidence_id`
    - `tx_id`

- `POST /evidence/{evidence_id}/verify`
  - Verifies decrypted evidence hash against registered SHA-256
  - Appends `ACCESS` verification event

- `GET /evidence/{evidence_id}/timeline`
  - Returns event timeline with endorsement status and signature/hash fields

### Reporting + artifacts

- `GET /evidence/{evidence_id}/report`
  - Court-style JSON report

- `GET /evidence/{evidence_id}/bundle`
  - ZIP bundle containing:
    - `report.json`
    - `report.pdf`
    - `ledger.jsonl` (filtered)
    - `manifest.json` (artifact hashes + encryption flag)

- `GET /evidence/{evidence_id}/qr`
  - QR image for `evidence:<evidence_id>` reference

### Case views

- `GET /case/{case_id}`
  - List evidence items under case

- `GET /case/{case_id}/audit`
  - Compliance summary:
    - evidence count
    - total events
    - integrity failures
    - pending endorsements
    - compliant evidence count
    - per-evidence status (`COMPLIANT` or `ATTENTION_REQUIRED`)

### Error patterns

- `401` missing/unknown `X-User-Id`
- `403` role not authorized for action
- `404` missing evidence/case resource
- `409` duplicate endorsement by same org

---

## 6) Frontend console

The React console is a full operator UI with premium animated visuals and backend connectivity.

### Major screens/workflows

- Operator selection (identity + role context)
- Ledger health overview
- Evidence intake form (file upload → base64)
- Custody event creation (action type, details, optional endorsement)
- Separate endorsement form
- Evidence operations (load, verify, download report, download bundle, open QR)
- Timeline viewer with hash/signature metadata
- Case dashboard + audit summary
- Security posture panel with storage and cryptographic controls

### Frontend route/serving behavior

- Dev mode served by Vite (`http://127.0.0.1:5173`)
- Vite proxy forwards `/health`, `/auth`, `/security`, `/evidence`, `/case` to FastAPI
- In production, FastAPI serves `frontend/dist` at `/` with SPA fallback

---

## 7) Local setup and run

### Prerequisites

- Python 3.11+ (project currently tested on local 3.14 runtime)
- Node.js 18+ and npm

### Backend setup (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend URLs:

- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

### Frontend setup (PowerShell)

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:

- `http://127.0.0.1:5173`

### Production-style frontend build

```powershell
cd frontend
npm run build
```

Then run backend and open `http://127.0.0.1:8000/`.

---

## 8) Demo workflow

Run the demo client:

```powershell
python demo_client.py
```

Typical sequence executed:

1. intake evidence
2. add transfer event
3. add endorsement
4. retrieve timeline
5. verify integrity
6. generate report

---

## 9) Testing

Run all tests:

```powershell
pytest -q
```

Current coverage includes:

- ledger tamper detection via hash-chain validation
- endorsement threshold behavior and duplicate-endorsement rejection
- case audit summary aggregation and compliance flagging
- evidence encryption roundtrip correctness
- backward-compatible read of legacy plaintext evidence files

---

## 10) Operational notes

### Prototype identity model

- Authentication is header-based (`X-User-Id`) for local/demo use
- Not suitable as-is for production authentication assurance

### Key material handling

- Signing and encryption keys are file-based in local storage
- This is a prototype key management approach, not HSM-backed

### Evidence migration behavior

- Existing plaintext evidence remains readable
- Newly ingested evidence is encrypted by default

### Bundle semantics

- Bundle manifest reports canonical evidence SHA-256 (registered plaintext hash)
- It does not expose raw encrypted blob hash as primary truth source

---

## 11) Production hardening roadmap

Recommended next steps before real deployment:

- OIDC/OAuth2 with short-lived tokens and strong session controls
- mTLS between trusted services and clients
- Hardware-backed keys (HSM/KMS/TPM) with key rotation policy
- Immutable/object-locked evidence storage and WORM retention controls
- Audit log shipping to centralized SIEM with alerting
- Secrets management (vault/KMS) instead of local key files
- Multi-region backup and disaster recovery playbooks
- Formal compliance mapping and threat modeling

---

## License / status

Prototype project for forensic process demonstration and technical validation.
Not legal advice and not production-certified in current form.
