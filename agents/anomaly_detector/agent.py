"""
Anomaly Detector Agent - simplified MVP version
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import numpy as np

from config import settings

logger = logging.getLogger(__name__)


class AnomalyDetectorAgent:
    def __init__(self):
        logger.info("AnomalyDetectorAgent initialized")

    def detect_anomalies(self, sensor_data: List[Dict[str, Any]], historical_baseline: Optional[Dict] = None) -> Dict[str, Any]:
        try:
            values = [r['value'] for r in sensor_data if 'value' in r]
            if not values:
                return {"anomalies_detected": 0, "anomalies": []}

            mean = float(np.mean(values))
            std = float(np.std(values))
            threshold = settings.settings.anomaly_threshold_std_dev if hasattr(settings, 'settings') else 3.0

            anomalies = []
            for i, v in enumerate(values):
                z = abs((v - mean) / (std if std > 0 else 1))
                if z > threshold:
                    anomalies.append({"index": i, "value": v, "z_score": float(z), "method": "z_score"})

            return {"anomalies_detected": len(anomalies), "anomalies": anomalies}

        except Exception as e:
            logger.error("Anomaly detection error: %s", e)
            return {"anomalies_detected": 0, "error": str(e)}
