"""
Grid Monitor Agent - simplified implementation for MVP
"""
from typing import Dict, List, Any
from datetime import datetime
import logging
import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)


class GridMonitorAgent:
    def __init__(self):
        logger.info("GridMonitorAgent initialized")

    def monitor_real_time(self, sensor_readings: List[Dict[str, Any]], time_window_minutes: int = 5) -> Dict[str, Any]:
        try:
            voltage_readings = [r for r in sensor_readings if r.get('sensor_type') == 'voltage']
            if not voltage_readings:
                return {"status": "no_data", "health_score": 100, "alerts": []}

            voltages = [r['value'] for r in voltage_readings]
            nominal_voltage = settings.grid_voltage_nominal
            avg_voltage = float(np.mean(voltages))
            min_voltage = float(np.min(voltages))
            max_voltage = float(np.max(voltages))

            min_v, max_v = settings.get_voltage_range()
            violations = []
            if min_voltage < min_v:
                violations.append(f"Undervoltage detected: {min_voltage:.2f} < {min_v:.2f}")
            if max_voltage > max_v:
                violations.append(f"Overvoltage detected: {max_voltage:.2f} > {max_v:.2f}")

            severity = None
            if violations:
                severity = 'warning'

            alerts = []
            for v in violations:
                alerts.append({"type": "voltage_violation", "severity": severity, "message": v, "timestamp": datetime.utcnow().isoformat()})

            health_score = 100 - (len(violations) * 10)
            return {
                "status": "violations" if violations else "normal",
                "health_score": int(max(0, health_score)),
                "average_voltage_kv": round(avg_voltage, 2),
                "min_voltage_kv": round(min_voltage, 2),
                "max_voltage_kv": round(max_voltage, 2),
                "alerts": alerts
            }

        except Exception as e:
            logger.error("Grid monitoring error: %s", e)
            return {"status": "error", "error": str(e)}
