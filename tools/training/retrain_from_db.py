"""
CLI helper to trigger retraining from DB incidents with corrected labels.

Usage:
  python tools/training/retrain_from_db.py --min-samples 20 --out models/risk_classifier.pkl
"""
from __future__ import annotations
import argparse
from ai.retrainer import retrain_from_feedback


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--min-samples', type=int, default=10)
    p.add_argument('--out', type=str, default=None)
    args = p.parse_args()
    res = retrain_from_feedback(out_path=args.out, min_samples=args.min_samples)
    print(res)


if __name__ == '__main__':
    main()
