"""
SmartGrid Sentinel - Configuration System
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn, field_validator, SecretStr
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum
import os


class GridZone(str, Enum):
    NAIROBI = "nairobi"
    MOMBASA = "mombasa"
    KISUMU = "kisumu"
    NAKURU = "nakuru"
    ELDORET = "eldoret"
    WESTERN = "western"
    CENTRAL = "central"
    COASTAL = "coastal"


class SensorType(str, Enum):
    VOLTAGE = "voltage"
    CURRENT = "current"
    FREQUENCY = "frequency"
    POWER_FACTOR = "power_factor"
    TEMPERATURE = "temperature"
    VIBRATION = "vibration"
    TRANSFORMER_OIL = "transformer_oil"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class Settings(BaseSettings):
    app_name: str = Field(default="SmartGrid Sentinel")
    app_version: str = Field(default="1.0.0")
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)

    grid_operator: str = Field(default="Kenya Power (KPLC)")
    grid_voltage_nominal: int = Field(default=220)
    grid_frequency_nominal: float = Field(default=50.0)
    grid_coverage_zones: List[GridZone] = Field(default=[zone for zone in GridZone])

    voltage_min_threshold: float = Field(default=0.95)
    voltage_max_threshold: float = Field(default=1.05)

    frequency_min_hz: float = Field(default=49.5)
    frequency_max_hz: float = Field(default=50.5)

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_workers: int = Field(default=8)

    database_url: PostgresDsn = Field(default="postgresql://grid_user:secure_grid_2026@localhost:5432/smartgrid_db")
    database_pool_size: int = Field(default=30)
    database_max_overflow: int = Field(default=20)

    enable_timescaledb: bool = Field(default=True)
    timescale_chunk_interval: str = Field(default="1 day")
    timescale_retention_days: int = Field(default=365)

    influxdb_url: Optional[str] = Field(default="http://localhost:8086")
    influxdb_token: Optional[SecretStr] = Field(default=None)
    influxdb_org: str = Field(default="smartgrid")
    influxdb_bucket: str = Field(default="grid_sensors")

    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_cache_ttl: int = Field(default=300)
    redis_max_connections: int = Field(default=100)

    watsonx_url: str = Field(default="https://us-south.ml.cloud.ibm.com")
    watsonx_api_key: SecretStr = Field(default="")
    watsonx_project_id: str = Field(default="")

    granite_model_id: str = Field(default="ibm/granite-3-8b-instruct")
    granite_max_tokens: int = Field(default=2000)
    granite_temperature: float = Field(default=0.2)

    sensor_count_total: int = Field(default=1000)
    sensor_polling_interval_seconds: int = Field(default=10)
    sensor_batch_size: int = Field(default=100)

    temperature_max_celsius: float = Field(default=85.0)
    vibration_max_mm_s: float = Field(default=10.0)
    oil_quality_min: float = Field(default=0.7)

    enable_scada_integration: bool = Field(default=True)
    scada_protocol: str = Field(default="Modbus TCP")
    scada_host: str = Field(default="localhost")
    scada_port: int = Field(default=502)
    scada_timeout: int = Field(default=5)

    enable_anomaly_detection: bool = Field(default=True)
    anomaly_detection_window_minutes: int = Field(default=60)
    anomaly_threshold_std_dev: float = Field(default=3.0)

    enable_predictive_maintenance: bool = Field(default=True)
    prediction_horizon_hours: int = Field(default=48)
    maintenance_alert_threshold: float = Field(default=0.7)

    enable_load_forecasting: bool = Field(default=True)
    forecast_horizon_hours: int = Field(default=24)
    forecast_update_interval_minutes: int = Field(default=15)

    enable_cyber_sentinel: bool = Field(default=True)
    cyber_threat_detection: bool = Field(default=True)
    failed_login_threshold: int = Field(default=5)
    unusual_command_detection: bool = Field(default=True)

    enable_sms_alerts: bool = Field(default=True)
    enable_email_alerts: bool = Field(default=True)
    enable_webhook_alerts: bool = Field(default=True)
    alert_phone_numbers: List[str] = Field(default=["+254700000001", "+254700000002"])
    alert_email_addresses: List[str] = Field(default=["grid-ops@kplc.co.ke", "maintenance@kplc.co.ke"])
    alert_webhook_url: Optional[str] = Field(default=None)

    twilio_account_sid: Optional[str] = Field(default=None)
    twilio_auth_token: Optional[SecretStr] = Field(default=None)
    twilio_phone_number: Optional[str] = Field(default=None)

    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_username: Optional[str] = Field(default=None)
    smtp_password: Optional[SecretStr] = Field(default=None)
    smtp_from_email: str = Field(default="alerts@smartgrid.ke")

    anomaly_model_path: Path = Field(default=Path("models/anomaly_detector.pkl"))
    failure_prediction_model_path: Path = Field(default=Path("models/failure_predictor.pkl"))
    load_forecast_model_path: Path = Field(default=Path("models/load_forecaster.pkl"))

    enable_auto_retraining: bool = Field(default=True)
    retrain_interval_days: int = Field(default=7)

    enable_grafana: bool = Field(default=True)
    grafana_url: str = Field(default="http://localhost:3000")
    grafana_api_key: Optional[SecretStr] = Field(default=None)

    enable_prometheus: bool = Field(default=True)
    prometheus_port: int = Field(default=9090)

    secret_key: SecretStr = Field(default=SecretStr("change-in-production-grid-security-key-32chars"))
    jwt_secret_key: SecretStr = Field(default=SecretStr("jwt-grid-sentinel-secret-32-characters"))
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)

    allowed_origins: List[str] = Field(default=["http://localhost:3000", "http://localhost:8000"])
    api_key_required: bool = Field(default=True)

    rate_limit_enabled: bool = Field(default=True)
    rate_limit_per_second: int = Field(default=100)

    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")
    celery_task_time_limit: int = Field(default=300)

    log_level: str = Field(default="INFO")
    log_file: Path = Field(default=Path("logs/smartgrid_sentinel.log"))
    log_rotation: str = Field(default="midnight")
    log_retention_days: int = Field(default=90)

    enable_data_export: bool = Field(default=True)
    export_format: str = Field(default="csv")
    export_directory: Path = Field(default=Path("exports"))

    enable_audit_logging: bool = Field(default=True)
    compliance_standards: List[str] = Field(default=["IEC 61850", "NERC CIP", "ISO 50001"])

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator('log_file', 'export_directory', 'anomaly_model_path')
    @classmethod
    def create_directories(cls, v: Path) -> Path:
        if v.name.endswith('.log') or v.name.endswith('.pkl'):
            v.parent.mkdir(parents=True, exist_ok=True)
        else:
            v.mkdir(parents=True, exist_ok=True)
        return v

    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def get_voltage_range(self) -> tuple[float, float]:
        return (
            self.grid_voltage_nominal * self.voltage_min_threshold,
            self.grid_voltage_nominal * self.voltage_max_threshold
        )

    def get_frequency_range(self) -> tuple[float, float]:
        return (self.frequency_min_hz, self.frequency_max_hz)


settings = Settings()
