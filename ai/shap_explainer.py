"""
Light wrapper around SHAP explainability.

If SHAP isn't installed this module degrades gracefully and returns an empty list
from the explain method.
"""
from __future__ import annotations
from typing import List, Any
import numpy as np


class ShapExplainer:
    def __init__(self):
        try:
            import shap  # type: ignore
            self._shap = shap
        except Exception:
            self._shap = None

    def explain(self, model: Any, X, feature_names: List[str]) -> List[dict]:
        """Return a list of {feature, value, contribution} dicts for the first sample in X.

        X is a 2-D array-like with shape (n_samples, n_features).
        """
        if self._shap is None:
            return []
        try:
            # Use TreeExplainer for tree models when available
            try:
                explainer = self._shap.TreeExplainer(model)
            except Exception:
                explainer = self._shap.KernelExplainer(model.predict_proba, X)
            shap_vals = explainer.shap_values(X)
            # shap_values can be [classes][n_samples][n_features] for classifier
            # we'll summarize by taking the absolute mean across class contributions for the first sample
            if isinstance(shap_vals, list):
                vals = np.mean(np.abs(np.stack([sv[0] for sv in shap_vals], axis=0)), axis=0)
            else:
                vals = shap_vals[0]
            out = []
            for i, name in enumerate(feature_names):
                out.append({"feature": name, "value": float(X[0][i]), "contribution": float(vals[i])})
            return out
        except Exception:
            return []
