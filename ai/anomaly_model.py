"""
AnomalyModel: IsolationForest-based detector with persistence.
"""
from typing import Optional, List, Dict, Any
import os
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


class AnomalyModel:
    def __init__(self, model_path: str = "models/anomaly_detector.pkl"):
        self.model_path = model_path
        self.scaler = StandardScaler()
        self.model: Optional[IsolationForest] = None
        # Try to load existing
        if os.path.exists(self.model_path):
            try:
                obj = joblib.load(self.model_path)
                self.model = obj.get('model')
                self.scaler = obj.get('scaler', self.scaler)
            except Exception:
                self.model = None

    def fit(self, X: np.ndarray):
        """Fit scaler and IsolationForest on training data X (n_samples, n_features)."""
        Xs = np.array(X)
        Xs_scaled = self.scaler.fit_transform(Xs)
        self.model = IsolationForest(contamination=0.05, random_state=42, n_estimators=200)
        self.model.fit(Xs_scaled)
        self._persist()

    def predict(self, X: np.ndarray) -> List[Dict[str, Any]]:
        """Return anomaly predictions and scores for rows in X."""
        if self.model is None:
            # model not trained; fall back to no anomalies
            return []
        Xs_scaled = self.scaler.transform(np.array(X))
        preds = self.model.predict(Xs_scaled)  # -1 anomaly, 1 normal
        scores = self.model.score_samples(Xs_scaled)
        out = []
        for i, (p, s) in enumerate(zip(preds, scores)):
            if p == -1:
                out.append({"index": i, "anomaly_score": float(-s)})
        return out

    def score_samples(self, X: np.ndarray) -> List[float]:
        if self.model is None:
            return [0.0] * len(X)
        Xs_scaled = self.scaler.transform(np.array(X))
        return list(map(float, self.model.score_samples(Xs_scaled)))

    def _persist(self):
        obj = {"model": self.model, "scaler": self.scaler}
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(obj, self.model_path)
