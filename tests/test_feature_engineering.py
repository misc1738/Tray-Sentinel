"""
Tests for feature extraction module.
"""
from ai.feature_engineering import extract_features


def test_extract_features_basic():
    readings = [
        {'value': 330.0},
        {'value': 328.5},
        {'value': 329.2},
    ]
    anomalies = [
        {'anomaly_score': 0.1, 'failed_logins': 0, 'unauth_cmds': 0},
        {'anomaly_score': 0.0, 'failed_logins': 1, 'unauth_cmds': 0},
    ]
    f = extract_features(readings, anomalies)
    assert f['max_voltage'] >= 330.0
    assert f['min_voltage'] <= 328.5
    assert 'voltage_std' in f
    assert f['failed_logins'] == 1
    assert f['unauth_cmds'] == 0
