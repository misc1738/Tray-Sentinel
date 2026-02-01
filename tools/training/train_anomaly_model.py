"""
Train the IsolationForest anomaly model using synthetic normal telemetry.

This script generates configurable amounts of nominal telemetry (voltage) with
small Gaussian noise, fits the AnomalyModel, and persists it to disk.

Usage:
  python train_anomaly_model.py --samples 10000 --sensors 50 --model-out models/anomaly_detector.pkl
"""
from __future__ import annotations
import argparse
import random
import os
from pathlib import Path
import numpy as np

from ai.anomaly_model import AnomalyModel


def generate_nominal_data(n_sensors: int, samples_per_sensor: int, nominal: float = 220.0, noise_std: float = 0.5):
    X = []
    for s in range(n_sensors):
        for i in range(samples_per_sensor):
            value = random.gauss(nominal, noise_std)
            quality = max(0.9, min(1.0, random.gauss(0.995, 0.01)))
            X.append([value, quality])
    return np.array(X)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=10000, help="Total samples to generate (distributed across sensors)")
    parser.add_argument("--sensors", type=int, default=50, help="Number of sensors to simulate")
    parser.add_argument("--model-out", type=str, default="models/anomaly_detector.pkl", help="Path to save trained model")
    parser.add_argument("--nominal", type=float, default=220.0, help="Nominal voltage value")
    parser.add_argument("--noise-std", type=float, default=0.5, help="Standard deviation of sensor noise")
    args = parser.parse_args()

    samples_per_sensor = max(1, args.samples // max(1, args.sensors))
    print(f"Generating {args.sensors} sensors x {samples_per_sensor} samples (~{args.sensors * samples_per_sensor} samples)")

    X = generate_nominal_data(args.sensors, samples_per_sensor, nominal=args.nominal, noise_std=args.noise_std)

    model = AnomalyModel(model_path=args.model_out)
    print("Fitting anomaly model...")
    model.fit(X)
    print(f"Model trained and saved to {args.model_out}")


if __name__ == '__main__':
    main()
