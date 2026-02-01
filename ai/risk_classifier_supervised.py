"""
Supervised risk classifier wrapper.

Provides a small sklearn pipeline (StandardScaler + RandomForest) with helper
methods to train, persist, load, and predict from compact feature dicts.
"""
from __future__ import annotations
import os
from typing import Dict, Any, List
import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier

DEFAULT_MODEL_PATH = os.path.join("models", "risk_classifier.pkl")


class RiskClassifier:
    """Wrapper around a sklearn pipeline.

    Feature order expected by this wrapper (keys):
      ['max_voltage','min_voltage','voltage_std','freq_std','anomaly_score','failed_logins','unauth_cmds']
    """

    feature_keys = ['max_voltage', 'min_voltage', 'voltage_std', 'freq_std', 'anomaly_score', 'failed_logins', 'unauth_cmds']

    def __init__(self, model_path: str = None):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.model = None
        self.loaded = False
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.loaded = True
            except Exception:
                self.model = None
                self.loaded = False

    @staticmethod
    def train_and_persist(X, y, out_path: str = None):
        out_path = out_path or DEFAULT_MODEL_PATH
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(n_estimators=100, random_state=42))
        ])
        pipe.fit(X, y)
        joblib.dump(pipe, out_path)
        return out_path

    def _vector_from_dict(self, features: Dict[str, Any]) -> List[float]:
        return [float(features.get(k, 0.0)) for k in self.feature_keys]

    def predict_risk(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Return {'label': str, 'score': float} where score is a numeric risk score.

        Score mapping: p(High)*1.0 + p(Medium)*0.5
        """
        if not self.loaded or self.model is None:
            raise RuntimeError("Risk classifier model not loaded")
        x = np.array([self._vector_from_dict(features)])
        probs = self.model.predict_proba(x)[0]
        classes = list(self.model.classes_)
        prob_map = {classes[i]: float(probs[i]) for i in range(len(classes))}
        score = prob_map.get('High', 0.0) * 1.0 + prob_map.get('Medium', 0.0) * 0.5
        label = self.model.predict(x)[0]
        return {"label": str(label), "score": float(score), "probs": prob_map}

    def predict_proba(self, features: Dict[str, Any]) -> Dict[str, float]:
        if not self.loaded or self.model is None:
            raise RuntimeError("Risk classifier model not loaded")
        x = np.array([self._vector_from_dict(features)])
        probs = self.model.predict_proba(x)[0]
        classes = list(self.model.classes_)
        return {classes[i]: float(probs[i]) for i in range(len(classes))}
