"""
Simple rule-based risk classifier for SmartGrid Sentinel.
Converts anomalies + context into a numeric score and a label (Low/Medium/High).
"""
from typing import Dict, Any, List


def score_risk(anomalies: List[Dict[str, Any]], asset_criticality: int = 1, cyber_signals: int = 0) -> Dict[str, Any]:
    """Compute a risk score and label.

    - anomalies: list of anomaly dicts, each may include 'anomaly_score' or 'z_score'
    - asset_criticality: 1 (low) .. 3 (high)
    - cyber_signals: count of correlated cyber/security events
    """
    score = 0.0

    # anomaly magnitude component
    for a in anomalies:
        if 'anomaly_score' in a:
            score += min(5.0, float(a['anomaly_score']))
        elif 'z_score' in a:
            score += min(5.0, float(a['z_score']) / 2.0)
        else:
            score += 1.0

    # persistence / count
    score += 0.5 * len(anomalies)

    # asset criticality multiplier
    score *= (1.0 + 0.5 * (asset_criticality - 1))

    # cyber signals add weight
    score += cyber_signals * 2.0

    # map to label
    if score >= 8.0:
        label = 'High'
    elif score >= 4.0:
        label = 'Medium'
    else:
        label = 'Low'

    return {"score": round(score, 2), "label": label}
