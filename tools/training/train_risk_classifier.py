"""
Train a supervised risk classifier from a labeled CSV and persist the model.

Example usage:
  python tools/training/train_risk_classifier.py --csv data/labeled_scenarios.csv --out models/risk_classifier.pkl
"""
from __future__ import annotations
import os
import pandas as pd
from ai.risk_classifier_supervised import RiskClassifier

DEFAULT_CSV = os.path.join('data', 'labeled_scenarios.csv')
DEFAULT_OUT = os.path.join('models', 'risk_classifier.pkl')


def train_from_csv(csv_path: str = None, out_path: str = None):
    csv_path = csv_path or DEFAULT_CSV
    out_path = out_path or DEFAULT_OUT
    df = pd.read_csv(csv_path)
    keys = RiskClassifier.feature_keys
    X = df[keys].values
    y = df['label'].values
    print(f"Training on {len(df)} samples...")
    model_path = RiskClassifier.train_and_persist(X, y, out_path=out_path)
    print(f"Saved model to {model_path}")


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--csv', type=str, default=DEFAULT_CSV)
    p.add_argument('--out', type=str, default=DEFAULT_OUT)
    args = p.parse_args()
    train_from_csv(args.csv, args.out)
