"""
Feature engineering helpers for SmartGrid Sentinel.

Provides a single public function `extract_features` that consumes a list of
sensor readings and anomaly records and returns a compact feature dict matching
the supervised classifier's expected keys.

This module focuses on deterministic, testable aggregations (max/min/mean/std)
and simple cyber counters. It is intentionally small so it can be extended later
to include rolling/historical features pulled from DB.
"""
from __future__ import annotations
from typing import List, Dict, Any
import statistics


FEATURE_KEYS = ['max_voltage', 'min_voltage', 'voltage_std', 'freq_std', 'anomaly_score', 'failed_logins', 'unauth_cmds']


def extract_features(sensor_readings: List[Dict[str, Any]], anomalies: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a compact dict with keys matching FEATURE_KEYS.

    sensor_readings: list of dicts with at least 'value' numeric field.
    anomalies: list of anomaly dicts that may include counts for failed_logins/unauth_cmds
    """
    anomalies = anomalies or []
    values = [float(r.get('value', 0.0)) for r in sensor_readings if isinstance(r.get('value', None), (int, float))]
    max_v = max(values) if values else 0.0
    min_v = min(values) if values else 0.0
    voltage_std = float(statistics.pstdev(values)) if len(values) > 1 else 0.0

    # frequency sensors might be interleaved; for now set placeholder
    freq_std = 0.0

    anomaly_score = float(sum([a.get('anomaly_score', 0.0) for a in anomalies])) if anomalies else 0.0
    failed_logins = int(sum([a.get('failed_logins', 0) for a in anomalies])) if anomalies else 0
    unauth_cmds = int(sum([a.get('unauth_cmds', 0) for a in anomalies])) if anomalies else 0

    return {
        'max_voltage': max_v,
        'min_voltage': min_v,
        'voltage_std': voltage_std,
        'freq_std': freq_std,
        'anomaly_score': anomaly_score,
        'failed_logins': failed_logins,
        'unauth_cmds': unauth_cmds,
    }
