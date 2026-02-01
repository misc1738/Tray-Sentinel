"""
Generate labeled scenario CSVs for training a supervised risk classifier.

This script synthesizes compact features (one row per scenario) and a label
('Low','Medium','High') using simple rules. The dataset is intentionally
simple so it can bootstrap a supervised model for demo and testing.
"""
from __future__ import annotations
import csv
import random
import os
from typing import Dict, Any

DEFAULT_OUT = os.path.join("data", "labeled_scenarios.csv")


def synthesize_row(seed: int = None) -> Dict[str, Any]:
    if seed is not None:
        random.seed(seed)
    # nominal ranges
    volt_mean = random.uniform(320.0, 330.0)
    volt_spike = random.choice([0.0, random.uniform(5.0, 60.0)])  # occasional spike
    max_voltage = volt_mean + volt_spike
    min_voltage = volt_mean - random.uniform(0.5, 3.0)
    voltage_std = random.uniform(0.1, 3.0) + (volt_spike / 20.0)
    freq_std = random.uniform(0.0, 0.2)
    anomaly_score = (volt_spike / 60.0) + random.uniform(0.0, 0.2)

    # cyber signals
    failed_logins = random.choices([0, 0, 0, 1, 2, 5], k=1)[0]
    unauth_cmds = random.choices([0, 0, 0, 0, 1, 3], k=1)[0]

    # rule-based label for generation:
    severity = 'Low'
    if (volt_spike > 20.0) or unauth_cmds >= 2 or failed_logins >= 5 or anomaly_score > 0.6:
        severity = 'High'
    elif (volt_spike > 5.0) or unauth_cmds >= 1 or failed_logins >= 2 or anomaly_score > 0.3:
        severity = 'Medium'

    return {
        'max_voltage': round(max_voltage, 3),
        'min_voltage': round(min_voltage, 3),
        'voltage_std': round(voltage_std, 4),
        'freq_std': round(freq_std, 4),
        'anomaly_score': round(anomaly_score, 4),
        'failed_logins': int(failed_logins),
        'unauth_cmds': int(unauth_cmds),
        'label': severity
    }


def generate_csv(rows: int = 1000, out: str = None, seed: int = None):
    out = out or DEFAULT_OUT
    os.makedirs(os.path.dirname(out), exist_ok=True)
    keys = ['max_voltage', 'min_voltage', 'voltage_std', 'freq_std', 'anomaly_score', 'failed_logins', 'unauth_cmds', 'label']
    with open(out, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for i in range(rows):
            row = synthesize_row(seed=(seed + i) if seed is not None else None)
            w.writerow(row)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--rows', type=int, default=2000)
    p.add_argument('--out', type=str, default=DEFAULT_OUT)
    p.add_argument('--seed', type=int, default=42)
    args = p.parse_args()
    print(f"Generating {args.rows} labeled scenarios to {args.out}...")
    generate_csv(rows=args.rows, out=args.out, seed=args.seed)
    print("Done.")
