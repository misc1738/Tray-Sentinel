"""
Lightweight SmartGrid Sentinel simulator
- Loads a scenario JSON and emits telemetry and OT log events
- Supports dry-run mode (prints events) and api mode (POST to endpoint)
- Simple deterministic RNG seeding for reproducibility
"""
from __future__ import annotations
import json
import time
import argparse
import random
from datetime import datetime, timedelta
try:
    from dateutil import parser as dtparse  # type: ignore
except Exception:
    # lightweight fallback if dateutil is not installed in the environment
    def _isoparse(s: str):
        # strip trailing Z and parse
        s2 = s.rstrip("Z")
        try:
            return datetime.fromisoformat(s2)
        except Exception:
            # last resort: parse only date portion
            return datetime.utcnow()

    dtparse = type("P", (), {"parse": staticmethod(_isoparse)})
from typing import List, Dict, Any, Optional
try:
    import requests
except Exception:
    requests = None
from pathlib import Path
try:
    from jsonschema import validate, ValidationError
except Exception:
    # fallback no-op validation if library not installed (dry-run fallback)
    def validate(instance, schema):
        return True

    class ValidationError(Exception):
        pass

# Load schemas relative to repo
BASE = Path(__file__).resolve().parents[2]
TELEMETRY_SCHEMA = BASE / "schemas" / "telemetry_schema.json"
OT_LOG_SCHEMA = BASE / "schemas" / "ot_log_schema.json"


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class SimpleSimulator:
    def __init__(self, scenario: Dict[str, Any], api_endpoint: Optional[str] = None, dry_run: bool = True, seed: Optional[int] = None):
        self.scenario = scenario
        self.api = api_endpoint
        self.dry_run = dry_run
        self.seed = seed if seed is not None else 42
        random.seed(self.seed)
        self.telemetry_schema = load_json(TELEMETRY_SCHEMA)
        self.ot_schema = load_json(OT_LOG_SCHEMA)

    def validate_record(self, record: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        try:
            validate(instance=record, schema=schema)
            return True
        except ValidationError as e:
            print("Validation error:", e)
            return False

    def generate_oscillation(self, base_value: float, amplitude_pct: float, frequency_hz: float, duration_seconds: int, sample_rate_seconds: int) -> List[Dict[str, Any]]:
        samples = []
        steps = max(1, int(duration_seconds / sample_rate_seconds))
        for i in range(steps):
            t = i * sample_rate_seconds
            # Simple sinusoidal oscillation
            angle = 2 * 3.141592653589793 * frequency_hz * t
            value = base_value * (1 + amplitude_pct * (0.5 * (1 + math.sin(angle))))
            samples.append(value)
        return samples

    def generate_telemetry(self) -> List[Dict[str, Any]]:
        out = []
        default_nominal_voltage = self.telemetry_schema.get('x:simulation', {}).get('defaults', {}).get('nominal_voltage_kv', 220)
        timeline = self.scenario.get('timeline', {})
        start = dtparse.parse(timeline.get('start_time')) if timeline.get('start_time') else datetime.utcnow()

        for inj in self.scenario.get('telemetry_injections', []):
            device_id = inj.get('device_id')
            sensor_type = inj.get('sensor_type')
            params = inj.get('injection', {})
            sample_rate_seconds = params.get('sample_rate_seconds', 10)
            duration = params.get('duration_seconds', timeline.get('duration_minutes', 1) * 60)

            if params.get('type') == 'oscillation':
                amplitude_pct = params.get('amplitude_pct', 0.05)
                frequency_hz = params.get('frequency_hz', 0.01)
                steps = max(1, int(duration / sample_rate_seconds))
                for i in range(steps):
                    ts = (start + timedelta(seconds=i * sample_rate_seconds)).isoformat() + 'Z'
                    # simple oscillation around nominal
                    angle = 2 * 3.141592653589793 * frequency_hz * (i * sample_rate_seconds)
                    value = default_nominal_voltage * (1 + amplitude_pct * math.sin(angle))
                    rec = {
                        "device_id": device_id,
                        "timestamp": ts,
                        "sensor_type": sensor_type,
                        "value": round(value, 3),
                        "unit": "kV",
                        "quality": 0.95,
                        "sample_rate_hz": 1.0 / max(1, sample_rate_seconds),
                        "metadata": {"scenario_id": self.scenario.get('scenario_id')}
                    }
                    out.append(rec)

            elif params.get('type') == 'dropout':
                drop_prob = params.get('drop_probability', 0.1)
                duration_minutes = params.get('duration_minutes', 5)
                steps = max(1, int((duration_minutes * 60) / sample_rate_seconds))
                for i in range(steps):
                    if random.random() < drop_prob:
                        # skip (dropout)
                        continue
                    ts = (start + timedelta(seconds=i * sample_rate_seconds)).isoformat() + 'Z'
                    # normal value
                    value = default_nominal_voltage * (1 + random.uniform(-0.01, 0.01))
                    rec = {
                        "device_id": device_id,
                        "timestamp": ts,
                        "sensor_type": sensor_type,
                        "value": round(value, 3),
                        "unit": "kV",
                        "quality": 0.9,
                        "sample_rate_hz": 1.0 / max(1, sample_rate_seconds),
                        "metadata": {"scenario_id": self.scenario.get('scenario_id')}
                    }
                    out.append(rec)

            elif params.get('type') == 'step':
                magnitude_pct = params.get('magnitude_pct', 0.1)
                # single step at t=0
                ts = start.isoformat() + 'Z'
                value = default_nominal_voltage * (1 + magnitude_pct)
                rec = {
                    "device_id": device_id,
                    "timestamp": ts,
                    "sensor_type": sensor_type,
                    "value": round(value, 3),
                    "unit": "kV",
                    "quality": 0.9,
                    "sample_rate_hz": 1.0 / max(1, sample_rate_seconds),
                    "metadata": {"scenario_id": self.scenario.get('scenario_id')}
                }
                out.append(rec)

            else:
                # fallback: single nominal sample
                ts = start.isoformat() + 'Z'
                value = default_nominal_voltage * (1 + random.uniform(-0.005, 0.005))
                rec = {
                    "device_id": device_id,
                    "timestamp": ts,
                    "sensor_type": sensor_type,
                    "value": round(value, 3),
                    "unit": "kV",
                    "quality": 1.0,
                    "sample_rate_hz": 1.0 / max(1, sample_rate_seconds),
                    "metadata": {"scenario_id": self.scenario.get('scenario_id')}
                }
                out.append(rec)

        return out

    def generate_ot_logs(self) -> List[Dict[str, Any]]:
        out = []
        timeline = self.scenario.get('timeline', {})
        start = dtparse.parse(timeline.get('start_time')) if timeline.get('start_time') else datetime.utcnow()

        for inj in self.scenario.get('ot_log_injections', []):
            etype = inj.get('event_type')
            freq = inj.get('frequency')
            if etype == 'failed_login' and freq:
                attempts = int(freq.get('attempts_per_minute', 1) * freq.get('duration_minutes', 1))
                ip = inj.get('ip_address', f"10.0.0.{random.randint(2,250)}")
                user = inj.get('user', 'unknown')
                for i in range(attempts):
                    ts = (start + timedelta(seconds=int(i * (60.0 / max(1, freq.get('attempts_per_minute',1)))))).isoformat() + 'Z'
                    rec = {
                        "event_id": f"evt-{random.randint(100000,999999)}",
                        "timestamp": ts,
                        "event_type": "failed_login",
                        "source": inj.get('source', 'HMI'),
                        "user": user,
                        "success": False,
                        "ip_address": ip,
                        "severity": "medium",
                        "details": {"reason":"invalid_password"}
                    }
                    out.append(rec)

            elif etype == 'plc_command':
                # single unauthorized command
                ts = (start + timedelta(seconds=inj.get('timestamp_offset_seconds', 0))).isoformat() + 'Z'
                rec = {
                    "event_id": f"evt-{random.randint(100000,999999)}",
                    "timestamp": ts,
                    "event_type": "plc_command",
                    "source": inj.get('source', 'PLC'),
                    "user": inj.get('user', ''),
                    "command": inj.get('command'),
                    "target_device": inj.get('target_device'),
                    "success": True,
                    "severity": "high" if inj.get('unauthorized') else "info",
                    "details": {"unauthorized": bool(inj.get('unauthorized', False))}
                }
                out.append(rec)

            else:
                ts = start.isoformat() + 'Z'
                rec = {
                    "event_id": f"evt-{random.randint(100000,999999)}",
                    "timestamp": ts,
                    "event_type": etype,
                    "source": inj.get('source', 'HMI'),
                    "user": inj.get('user', ''),
                    "success": inj.get('success', True),
                    "severity": inj.get('severity', 'low'),
                    "details": inj.get('details', {})
                }
                out.append(rec)

        return out

    def post_batch(self, records: List[Dict[str, Any]], endpoint: str):
        # POST in groups of 100
        for i in range(0, len(records), 100):
            batch = records[i:i+100]
            if not requests:
                print("requests library not available; skipping POST in this environment")
                return
            try:
                resp = requests.post(endpoint, json=batch, timeout=10)
                print(f"POST {endpoint} -> {resp.status_code}")
            except Exception as e:
                print("POST failed:", e)

    def run(self):
        telemetry = self.generate_telemetry()
        ot_logs = self.generate_ot_logs()

        print(f"Generated {len(telemetry)} telemetry records and {len(ot_logs)} OT logs (seed={self.seed})")

        # Validate a small sample
        for rec in telemetry[:3]:
            ok = self.validate_record(rec, self.telemetry_schema)
            if not ok:
                print("Telemetry validation failed for sample record")
                break

        for rec in ot_logs[:3]:
            ok = self.validate_record(rec, self.ot_schema)
            if not ok:
                print("OT log validation failed for sample record")
                break

        if self.dry_run or not self.api:
            # Print concise summary
            print("--- TELEMETRY SAMPLE (first 5) ---")
            for r in telemetry[:5]:
                print(json.dumps(r))
            print("--- OT LOG SAMPLE (first 5) ---")
            for r in ot_logs[:5]:
                print(json.dumps(r))
        else:
            # send to API in expected format
            # API expects list of sensor readings; we will send telemetry in batches
            if self.api:
                print(f"Posting telemetry to {self.api} (batches)")
                # The API in the template expects a list of SensorReadingInput objects; adapt accordingly
                formatted = []
                for t in telemetry:
                    formatted.append({
                        "sensor_id": t['device_id'],
                        "sensor_type": t['sensor_type'],
                        "value": t['value'],
                        "timestamp": t['timestamp']
                    })
                self.post_batch(formatted, self.api)


# helper for math
import math


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, help="Path to scenario JSON")
    parser.add_argument("--api", required=False, help="Optional API endpoint to POST telemetry")
    parser.add_argument("--dry-run", action="store_true", help="Do not POST; print generated records")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    args = parser.parse_args()

    scenario_path = Path(args.scenario)
    if not scenario_path.exists():
        print(f"Scenario not found: {scenario_path}")
        return

    scenario = load_json(scenario_path)
    sim = SimpleSimulator(scenario=scenario, api_endpoint=args.api, dry_run=args.dry_run or args.api is None, seed=args.seed)
    sim.run()


if __name__ == '__main__':
    main()
