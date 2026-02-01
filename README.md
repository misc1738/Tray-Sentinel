# SmartGrid Sentinel — MVP

This repository contains the SmartGrid Sentinel system: a simulator, AI agents, orchestrator, and an API for anomaly detection and security monitoring for power substations.

Quick start (local, development):

1. Create a Python venv and install requirements:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

2. Run the API:

```powershell
uvicorn api.main:app --reload --port 8000
```

3. Run the simulator (dry-run):

```powershell
python .\tools\simulator\simulator.py --scenario .\scenarios\medium_risk_voltage_fluctuation.json --dry-run
```

Next steps:
- Tune models and thresholds
- Add persistent Postgres/TimescaleDB for production
- Replace stubs with full agent implementations
