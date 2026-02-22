# Tracey's Sentinel — Permissioned Digital Chain of Custody (Prototype)

Tracey's Sentinel is a FastAPI prototype for tamper-evident digital evidence handling.
It combines:

- off-chain evidence storage (files + SQLite metadata)
- an append-only hash-chained ledger (`JSONL`)
- per-event Ed25519 digital signatures
- RBAC + multi-organization endorsement rules

The goal is to preserve evidentiary integrity and produce court-facing artifacts (JSON report, PDF report, ZIP bundle).

## Key Capabilities

- Evidence intake with SHA-256 registration
- Custody event recording (`INTAKE`, `TRANSFER`, `ACCESS`, `ANALYSIS`, `STORAGE`, `COURT_SUBMISSION`, `ENDORSE`)
- Multi-org endorsement tracking (e.g., `TRANSFER` requires 2 unique org endorsements)
- Integrity verification against original evidence hash
- Timeline and chain validation
- Court report + court bundle generation
- Case-level audit summary endpoint for compliance monitoring

## Architecture

### Core Components

- `app/main.py` — FastAPI routes and orchestration
- `app/storage.py` — SQLite evidence metadata + file path mapping
- `app/ledger.py` — append-only hash-chain ledger + signature validation
- `app/signing.py` — Ed25519 key management/sign/verify helpers
- `app/rbac.py` — roles, actions, and endorsement policy
- `app/reporting.py` — court report and case audit summary builders
- `app/bundle.py` / `app/pdf_report.py` — bundle and PDF generation

### Data Planes

- **Off-chain**: evidence bytes on disk + metadata in SQLite
- **Ledger plane**: each event stored as one JSON line with:
	- `prev_hash` (chain link)
	- `record_hash` (content hash)
	- signer public key + signature

## Endorsement Model

- Endorsement requirement is policy-driven per `action_type`.
- `TRANSFER` and `COURT_SUBMISSION` require 2 unique endorser orgs.
- Other events require 1 org (often satisfied by originator if `endorse=true`).
- Endorsements are append-only `ENDORSE` events referencing original `tx_id`.

## RBAC (Prototype Identities)

Pass caller identity using header:

- `X-User-Id: officer1 | analyst1 | supervisor1 | prosecutor1 | judge1 | auditor1`

Role permissions are defined in `app/rbac.py`.

## Local Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

- Swagger UI: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## React Frontend (New)

A full React operations console now lives in `frontend/` and is wired to the FastAPI backend.

### Run Frontend in Development

```powershell
cd frontend
npm install
npm run dev
```

Frontend dev URL:

- http://127.0.0.1:5173

The Vite dev server proxies API calls (`/health`, `/auth`, `/evidence`, `/case`) to FastAPI at `http://127.0.0.1:8000`.

### Build Frontend for Production Serving via FastAPI

```powershell
cd frontend
npm run build
```

When `frontend/dist` exists, FastAPI serves the built React app at `/` with SPA fallback routing.

### Frontend Features

- Operator selection from backend identities (`/auth/users`)
- Ledger health status
- Evidence intake (file upload + base64 conversion)
- Custody event recording + endorsement options
- Separate endorsement workflow
- Evidence timeline view, integrity verify, report/bundle download, QR open
- Case summary + case audit dashboard

## API Reference

### Health

- `GET /health`
	- Validates entire ledger chain and signatures.

### Evidence Lifecycle

- `POST /evidence/intake`
	- Registers evidence bytes (base64), computes SHA-256, stores file + metadata, writes `INTAKE` event.

- `POST /evidence/event`
	- Records a custody event.
	- Accepts `endorse=true/false` to include originator endorsement on that event.

- `POST /evidence/endorse`
	- Adds a separate `ENDORSE` event for an existing transaction.
	- Rejects duplicate endorsement from same org.

- `POST /evidence/{evidence_id}/verify`
	- Re-hashes stored file and compares against registered hash.
	- Writes an `ACCESS` verification event.

- `GET /evidence/{evidence_id}/timeline`
	- Full timeline for one evidence item, including computed endorsement status.

### Reporting + Packaging

- `GET /evidence/{evidence_id}/report`
	- Court-focused JSON report.

- `GET /evidence/{evidence_id}/bundle`
	- ZIP download containing:
		- `report.json`
		- `report.pdf`
		- filtered `ledger.jsonl`
		- `manifest.json` with hashes

- `GET /evidence/{evidence_id}/qr`
	- Returns a QR image containing `evidence:<evidence_id>`.

### Case Views

- `GET /case/{case_id}`
	- Lists evidence items for a case.

- `GET /case/{case_id}/audit` (new)
	- Aggregated case compliance summary with:
		- total events
		- integrity failure count
		- pending endorsement count
		- per-evidence compliance status (`COMPLIANT` or `ATTENTION_REQUIRED`)

## Storage Layout

- SQLite DB: `./data/sentinel.db`
- Ledger file: `./data/ledger.jsonl`
- User keys: `./data/keys/<user_id>.ed25519.pem`
- Evidence files: `./evidence_store/<evidence_id>/<file_name>`

## Demo Script

Run:

```powershell
python demo_client.py
```

The script executes intake → transfer → endorsement → timeline → verify → report.

## Testing

```powershell
pytest -q
```

Current tests cover:

- hash-chain tamper detection
- endorsement uniqueness + threshold behavior
- case audit summary integrity/pending-endorsement flagging

## Security Notes (Prototype Scope)

- Identity is header-based and not production-grade.
- Private keys are stored on local disk for demo purposes.
- No encrypted-at-rest evidence store in this prototype.

Production hardening should include OIDC, mTLS, HSM-backed keys, immutable storage controls, and audit log shipping.
