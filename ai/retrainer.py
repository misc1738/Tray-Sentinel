"""
Retraining helper: build training set from incidents with operator-corrected labels
and retrain the supervised risk classifier.
"""
from __future__ import annotations
import json
from typing import Optional
from database.connection import SessionLocal
from database.models import Incident
from ai.risk_classifier_supervised import RiskClassifier


def retrain_from_feedback(out_path: Optional[str] = None, min_samples: int = 10) -> dict:
    """Collect incidents with `correct_label` and `features` and retrain classifier.

    Returns a dict with status and trained samples count.
    """
    session = SessionLocal()
    try:
        rows = session.query(Incident).filter(Incident.correct_label.isnot(None), Incident.features.isnot(None)).all()
        X = []
        y = []
        for r in rows:
            try:
                feat = json.loads(r.features)
                # keep only expected keys
                vec = [float(feat.get(k, 0.0)) for k in RiskClassifier.feature_keys]
                X.append(vec)
                y.append(r.correct_label)
            except Exception:
                continue
        if len(X) < min_samples:
            return {"trained": False, "reason": "not_enough_samples", "samples": len(X)}
        # train and persist
        path = RiskClassifier.train_and_persist(X, y, out_path=out_path)
        return {"trained": True, "model_path": path, "samples": len(X)}
    finally:
        session.close()
