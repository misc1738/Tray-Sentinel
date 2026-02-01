"""
Basic test that runs the labeled scenario generator, trains a risk classifier,
and asserts the trained classifier can predict labels.
"""
from __future__ import annotations
import os
import tempfile
from tools.training.generate_labeled_scenarios import generate_csv
from tools.training.train_risk_classifier import train_from_csv
from ai.risk_classifier_supervised import RiskClassifier


def test_risk_classifier_workflow(tmp_path):
    out_csv = tmp_path / "labeled.csv"
    out_model = tmp_path / "risk.pkl"
    generate_csv(rows=200, out=str(out_csv), seed=123)
    train_from_csv(csv_path=str(out_csv), out_path=str(out_model))
    rc = RiskClassifier(model_path=str(out_model))
    assert rc.loaded
    # create a sample feature vector
    sample = {
        'max_voltage': 340.0,
        'min_voltage': 318.0,
        'voltage_std': 6.0,
        'freq_std': 0.1,
        'anomaly_score': 0.7,
        'failed_logins': 1,
        'unauth_cmds': 0
    }
    res = rc.predict_risk(sample)
    assert 'label' in res and res['label'] in {'Low', 'Medium', 'High'}
