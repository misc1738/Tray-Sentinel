"""
SmartGrid Sentinel Orchestrator - coordinates agents
"""
from typing import Dict, Any, List
from datetime import datetime
import logging

from agents.grid_monitor.agent import GridMonitorAgent
from agents.anomaly_detector.agent import AnomalyDetectorAgent
from ai.anomaly_model import AnomalyModel
from ai.risk_classifier import score_risk
from ai.explainer import explain_incident
from ai.risk_classifier_supervised import RiskClassifier
from ai.feature_engineering import extract_features
from agents.demand_forecaster.agent import DemandForecasterAgent
from agents.maintenance_predictor.agent import MaintenancePredictorAgent
from agents.cyber_sentinel.agent import CyberSentinelAgent
from database.connection import SessionLocal
from database.models import Incident
import json

logger = logging.getLogger(__name__)


class SmartGridOrchestrator:
    """Coordinates all agents and handles high-level orchestration."""

    def __init__(self):
        logger.info("Initializing SmartGridOrchestrator...")
        self.grid_monitor = GridMonitorAgent()
        self.anomaly_detector = AnomalyDetectorAgent()
        # AI helper modules
        self.anomaly_model = AnomalyModel()
        self.demand_forecaster = DemandForecasterAgent()
        self.maintenance_predictor = MaintenancePredictorAgent()
        self.cyber_sentinel = CyberSentinelAgent()
        # Supervised risk classifier (optional)
        try:
            self.risk_classifier = RiskClassifier()
            if not self.risk_classifier.loaded:
                self.risk_classifier = None
        except Exception:
            self.risk_classifier = None

    async def process_sensor_data_stream(self, sensor_readings: List[Dict[str, Any]]) -> Dict[str, Any]:
        start = datetime.utcnow()

        # Run grid monitoring and anomaly detection synchronously for simplicity
        grid_health = self.grid_monitor.monitor_real_time(sensor_readings)
        anomalies = self.anomaly_detector.detect_anomalies(sensor_readings)

        # Try ML-based detection on numerical features
        try:
            X = [[r.get('value', 0.0), r.get('quality', r.get('quality_indicator', 1.0))] for r in sensor_readings]
            ml_anoms = self.anomaly_model.predict(X)
            for ma in ml_anoms:
                anomalies.setdefault('anomalies', [])
                anomalies['anomalies'].append({'index': ma['index'], 'anomaly_score': ma['anomaly_score'], 'method': 'ml'})
                anomalies['anomalies_detected'] = anomalies.get('anomalies_detected', 0) + 1
        except Exception:
            # proceed even if ML module fails
            pass

        forecast = self.demand_forecaster.forecast_demand()
        maintenance = self.maintenance_predictor.predict_failures()
        cyber = self.cyber_sentinel.monitor_scada_security()

        # Risk scoring
        asset_criticality = 2  # default medium criticality; in real system pull from inventory
        cyber_signals = 0
        try:
            # If a supervised classifier is available, prefer it
            if self.risk_classifier is not None:
                # build a compact feature dict used by the supervised model
                feat = extract_features(sensor_readings, anomalies.get('anomalies', []))
                sc_res = self.risk_classifier.predict_risk(feat)
                risk = {'score': float(sc_res.get('score', 0.0)), 'label': sc_res.get('label', 'Low')}
                # Try to build an explanation using the templated explainer as before
                explanation = explain_incident({"samples": sensor_readings}, anomalies.get('anomalies', []), risk)
                # If SHAP is available, attach shap contributions (best-effort)
                try:
                    from ai.shap_explainer import ShapExplainer
                    se = ShapExplainer()
                    shap_vals = se.explain(self.risk_classifier.model, [list(feat.values())], list(feat.keys()))
                    explanation.setdefault('shap', shap_vals)
                except Exception:
                    pass
            else:
                risk = score_risk(anomalies.get('anomalies', []), asset_criticality=asset_criticality, cyber_signals=cyber_signals)
                explanation = explain_incident({"samples": sensor_readings}, anomalies.get('anomalies', []), risk)
        except Exception:
            risk = {"score": 0.0, "label": "Low"}
            explanation = {}

        critical_alerts = []
        if grid_health.get('alerts'):
            critical_alerts.extend(grid_health['alerts'])
        if anomalies.get('anomalies_detected', 0) > 0:
            critical_alerts.append({"type": "anomalies_detected", "count": anomalies['anomalies_detected']})
        if cyber.get('threats_detected', 0) > 0:
            critical_alerts.append({"type": "cyber_threat", "count": cyber['threats_detected']})

        status = {
            "status": "operational" if not critical_alerts else "degraded",
            "critical_alerts": len(critical_alerts)
        }

        processing_time = (datetime.utcnow() - start).total_seconds()

        # Persist incident to DB (best-effort)
        incident_id = None
        try:
            session = SessionLocal()
            sensor_ids = list({r.get('device_id') for r in sensor_readings if r.get('device_id')})
            # build compact features for persistence so incidents can be used for retraining
            compact_features = {
                'max_voltage': float(max([r.get('value', 0.0) for r in sensor_readings]) if sensor_readings else 0.0),
                'min_voltage': float(min([r.get('value', 0.0) for r in sensor_readings]) if sensor_readings else 0.0),
                'voltage_std': float(__import__('statistics').pstdev([r.get('value', 0.0) for r in sensor_readings]) if len(sensor_readings) > 1 else 0.0),
                'freq_std': 0.0,
                'anomaly_score': float(risk.get('score', 0.0)),
                'failed_logins': int(sum([a.get('failed_logins', 0) for a in anomalies.get('anomalies', [])]) if anomalies.get('anomalies') else 0),
                'unauth_cmds': int(sum([a.get('unauth_cmds', 0) for a in anomalies.get('anomalies', [])]) if anomalies.get('anomalies') else 0),
            }

            inc = Incident(
                timestamp=datetime.utcnow(),
                sensor_ids=','.join(sensor_ids),
                risk_label=risk.get('label'),
                risk_score=float(risk.get('score', 0.0)),
                explanation=str(explanation),
                recommendations='; '.join(explanation.get('recommendations', [])) if isinstance(explanation, dict) else '',
                features=json.dumps(compact_features),
            )
            session.add(inc)
            session.commit()
            incident_id = inc.id
        except Exception:
            try:
                session.rollback()
            except Exception:
                pass
            incident_id = None
        finally:
            try:
                session.close()
            except Exception:
                pass

        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "system_status": status,
            "grid_health": grid_health,
            "anomalies": anomalies,
            "risk": risk,
            "explanation": explanation,
            "incident_id": incident_id,
            "load_forecast": forecast,
            "maintenance_alerts": maintenance,
            "cyber_security": cyber,
            "critical_alerts": critical_alerts,
            "processing_time_seconds": processing_time,
            "sensors_processed": len(sensor_readings)
        }
