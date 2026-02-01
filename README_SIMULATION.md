SmartGrid Sentinel — Simulation artifacts

This folder contains example schemas and scenario definitions to start the SmartGrid Sentinel simulator.

Files added:
- `schemas/telemetry_schema.json` — JSON Schema for a single telemetry reading. Includes default sampling and anomaly injection types (drift, step, oscillation, dropout).
- `schemas/ot_log_schema.json` — JSON Schema for OT/SCADA logs (HMI, PLC, IDS, firewall). Includes attack scenario parameter hints.
- `scenarios/medium_risk_voltage_fluctuation.json` — Example scenario that combines a voltage oscillation on `FEEDER-F12` with multiple failed HMI logins and an unauthorized PLC command. Produces a Medium-risk incident by design.

How to use (conceptual):
1. Load the `telemetry_schema.json` and `ot_log_schema.json` into your simulator module as the canonical record formats.
2. Implement an injector that reads a scenario (e.g., the provided example) and schedules telemetry and log events according to `timeline` and injection parameters.
3. For reproducible tests, seed your RNG and log the seed with scenario runs.
4. Feed generated events to the API endpoint `/sensors/process` (or directly to the orchestrator) and verify detection, risk classification, explanation text, and recommended actions.

Suggested next steps (I can implement these):
- Create a lightweight Python simulator (single-file) that reads `scenarios/*.json` and emits records over a local MQTT broker or directly to the API.
- Implement a small test harness that runs the medium-risk scenario and prints the orchestrator's output (incident JSON) for review.

If you want, I can now implement the Python simulator and a small test harness that runs the provided Medium-risk scenario and validates the expected outcomes. Which would you like me to do next? (A) implement the simulator + harness, or (B) design the AI models & explainability details next?