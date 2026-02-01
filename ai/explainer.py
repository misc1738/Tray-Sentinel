"""
Explainable output generator: creates plain-language explanations and recommendations.
Uses SHAP if available; falls back to template-based explanations.
"""
from typing import Dict, Any, List, Optional
import math

try:
    import shap
    HAS_SHAP = True
except Exception:
    HAS_SHAP = False


def explain_incident(sensor_summary: Dict[str, Any], anomalies: List[Dict[str, Any]], risk: Dict[str, Any], cyber_events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Return a structured explanation with plain-language summary and recommended actions."""
    # Structured evidence
    evidence = {
        "affected_devices": list({r.get('device_id') for r in sensor_summary.get('samples', []) if r.get('device_id')}),
        "anomaly_count": len(anomalies),
        "anomaly_examples": anomalies[:3]
    }

    # Plain-language summary
    devs = evidence['affected_devices']
    devs_text = ', '.join(devs) if devs else 'one or more devices'
    summary = f"{risk['label']} risk — {len(anomalies)} anomalous readings detected on {devs_text}."

    # Add more detail if available
    if anomalies:
        top = anomalies[0]
        if 'anomaly_score' in top:
            summary += f" Largest anomaly score: {top['anomaly_score']:.2f}."
        if 'z_score' in top:
            summary += f" Max z-score: {top['z_score']:.2f}."

    # Recommendations mapping
    recs: List[str] = []
    if risk['label'] == 'Low':
        recs.append("Continue monitoring and log for baseline; no immediate action required.")
    elif risk['label'] == 'Medium':
        recs.append("Increase telemetry sampling for affected devices to 1s for the next 15 minutes.")
        recs.append("Inspect local voltage regulation equipment and verify sensor calibrations.")
        if cyber_events:
            recs.append("Review and block suspicious remote IPs; check HMI access logs.")
    else:
        recs.append("Isolate affected feeder and dispatch field crew immediately.")
        recs.append("Preserve logs and evidence for forensic analysis.")

    # Optional SHAP-based feature contributions (if model+features provided in sensor_summary)
    contributions = None
    if HAS_SHAP and sensor_summary.get('model') and sensor_summary.get('features'):
        try:
            model = sensor_summary['model']
            X = sensor_summary['features']
            expl = shap.Explainer(model)
            shap_vals = expl(X)
            contributions = shap_vals.values.tolist() if hasattr(shap_vals, 'values') else None
        except Exception:
            contributions = None

    return {
        "summary": summary,
        "evidence": evidence,
        "recommendations": recs,
        "risk_score": risk,
        "feature_contributions": contributions
    }
