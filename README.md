# Tracey's Sentinel — Permissioned Digital Chain of Custody (Prototype)

## What this is
A working prototype of a permissioned, blockchain-style **digital chain-of-custody** system for forensic evidence.

- Off-chain: evidence files + metadata (SQLite)
- On-chain: custody events in an **append-only hash-chained ledger** (JSONL)
- Permissioning: RBAC and multi-organization endorsement (no single party can finalize certain events)

## Run
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs:
- http://127.0.0.1:8000/docs

## Default users (prototype)
Use request headers:
- `X-User-Id`: one of `officer1`, `analyst1`, `supervisor1`, `prosecutor1`, `judge1`, `auditor1`

## Storage
- SQLite DB: `./data/sentinel.db`
- Ledger file: `./data/ledger.jsonl`
- Evidence files: `./evidence_store/<evidence_id>/...`
