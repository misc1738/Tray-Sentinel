# SMARTGRID SENTINEL - PART 2: DATABASE MODELS + SCADA
## Complete Database Schema + SCADA Integration (1,000+ lines)

---

## DATABASE MODELS (800 lines)

### File: `database/models.py`

```python
"""
SmartGrid Sentinel - Database Models
Mifano ya Hifadhi ya Data ya SmartGrid

Complete SQLAlchemy + TimescaleDB models for grid monitoring.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, JSON,
    ForeignKey, Enum as SQLEnum, Index, CheckConstraint, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
import uuid


Base = declarative_base()


# ===== ENUMS =====

class GridZone(str, Enum):
    """Power grid zones"""
    NAIROBI = "nairobi"
    MOMBASA = "mombasa"
    KISUMU = "kisumu"
    NAKURU = "nakuru"
    ELDORET = "eldoret"
    WESTERN = "western"
    CENTRAL = "central"
    COASTAL = "coastal"


class SensorType(str, Enum):
    """Sensor types"""
    VOLTAGE = "voltage"
    CURRENT = "current"
    FREQUENCY = "frequency"
    POWER_FACTOR = "power_factor"
    TEMPERATURE = "temperature"
    VIBRATION = "vibration"
    TRANSFORMER_OIL = "transformer_oil"
    LOAD = "load"


class SensorStatus(str, Enum):
    """Sensor operational status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAULTY = "faulty"
    MAINTENANCE = "maintenance"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(str, Enum):
    """Alert handling status"""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MaintenanceType(str, Enum):
    """Maintenance types"""
    PREVENTIVE = "preventive"
    PREDICTIVE = "predictive"
    CORRECTIVE = "corrective"
    EMERGENCY = "emergency"


# ===== GRID INFRASTRUCTURE =====

class GridSubstation(Base):
    """
    Power grid substations
    Vituo vya Umeme vya Gridi
    """
    __tablename__ = 'grid_substations'
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Substation Info
    name = Column(String(255), nullable=False, unique=True)
    code = Column(String(50), unique=True, nullable=False)
    zone = Column(SQLEnum(GridZone), nullable=False, index=True)
    
    # Location
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(500))
    county = Column(String(100))
    
    # Capacity
    voltage_level_kv = Column(Integer, nullable=False)  # 33, 66, 132, 220, 400
    capacity_mva = Column(Float, nullable=False)  # MVA rating
    num_transformers = Column(Integer, default=0)
    num_feeders = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    commissioned_date = Column(DateTime)
    last_maintenance_date = Column(DateTime)
    
    # Metadata
    metadata = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sensors = relationship("GridSensor", back_populates="substation", cascade="all, delete-orphan")
    transformers = relationship("Transformer", back_populates="substation")
    alerts = relationship("GridAlert", back_populates="substation")
    
    def __repr__(self):
        return f"<GridSubstation(code={self.code}, name={self.name}, zone={self.zone})>"


class Transformer(Base):
    """
    Power transformers
    Vibadilishaji vya Umeme
    """
    __tablename__ = 'transformers'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign Keys
    substation_id = Column(UUID(as_uuid=True), ForeignKey('grid_substations.id', ondelete='CASCADE'), nullable=False)
    
    # Transformer Info
    name = Column(String(255), nullable=False)
    serial_number = Column(String(100), unique=True)
    manufacturer = Column(String(100))
    year_manufactured = Column(Integer)
    
    # Specifications
    capacity_mva = Column(Float, nullable=False)
    voltage_primary_kv = Column(Float, nullable=False)
    voltage_secondary_kv = Column(Float, nullable=False)
    cooling_type = Column(String(50))  # ONAN, ONAF, OFAF
    
    # Operating Parameters
    current_load_mva = Column(Float, default=0.0)
    load_percentage = Column(Float, default=0.0)
    oil_temperature_celsius = Column(Float)
    winding_temperature_celsius = Column(Float)
    oil_level_percentage = Column(Float, default=100.0)
    
    # Health Metrics
    health_score = Column(Float, default=100.0)  # 0-100
    estimated_remaining_life_years = Column(Float)
    failure_probability_7days = Column(Float, default=0.0)  # 0-1
    failure_probability_30days = Column(Float, default=0.0)
    
    # Status
    is_operational = Column(Boolean, default=True)
    last_maintenance_date = Column(DateTime)
    next_maintenance_date = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    substation = relationship("GridSubstation", back_populates="transformers")
    maintenance_records = relationship("MaintenanceRecord", back_populates="transformer")
    
    __table_args__ = (
        CheckConstraint('capacity_mva > 0', name='check_capacity_positive'),
        CheckConstraint('load_percentage >= 0 AND load_percentage <= 100', name='check_load_percentage'),
        Index('idx_transformer_health', 'health_score', 'failure_probability_7days'),
    )


# ===== SENSORS =====

class GridSensor(Base):
    """
    Grid monitoring sensors
    Vipimaji vya Ufuatiliaji wa Gridi
    """
    __tablename__ = 'grid_sensors'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign Keys
    substation_id = Column(UUID(as_uuid=True), ForeignKey('grid_substations.id', ondelete='CASCADE'), nullable=False)
    
    # Sensor Info
    sensor_id = Column(String(100), unique=True, nullable=False, index=True)
    sensor_type = Column(SQLEnum(SensorType), nullable=False, index=True)
    sensor_model = Column(String(100))
    manufacturer = Column(String(100))
    
    # Location
    location_description = Column(String(255))
    installation_date = Column(DateTime)
    
    # Configuration
    measurement_unit = Column(String(20))  # V, A, Hz, °C, etc.
    sampling_rate_hz = Column(Float, default=1.0)
    precision_decimals = Column(Integer, default=2)
    
    # Calibration
    calibration_offset = Column(Float, default=0.0)
    calibration_scale = Column(Float, default=1.0)
    last_calibration_date = Column(DateTime)
    next_calibration_date = Column(DateTime)
    
    # Status
    status = Column(SQLEnum(SensorStatus), default=SensorStatus.ACTIVE, index=True)
    is_critical = Column(Boolean, default=False)  # Critical for grid operation
    
    # Communication
    ip_address = Column(INET)
    port = Column(Integer)
    protocol = Column(String(50))  # Modbus, DNP3, IEC 61850
    
    # Metadata
    metadata = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_reading_at = Column(DateTime)
    
    # Relationships
    substation = relationship("GridSubstation", back_populates="sensors")
    readings = relationship("SensorReading", back_populates="sensor")
    
    __table_args__ = (
        Index('idx_sensor_type_status', 'sensor_type', 'status'),
        Index('idx_sensor_substation', 'substation_id', 'sensor_type'),
    )


class SensorReading(Base):
    """
    Time-series sensor readings (TimescaleDB hypertable)
    Masomo ya Vipimaji ya Muda (TimescaleDB)
    """
    __tablename__ = 'sensor_readings'
    
    # Primary Key (composite with timestamp for TimescaleDB)
    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    timestamp = Column(DateTime, nullable=False, primary_key=True, index=True)
    
    # Foreign Keys
    sensor_id = Column(UUID(as_uuid=True), ForeignKey('grid_sensors.id', ondelete='CASCADE'), nullable=False, primary_key=True)
    
    # Reading Data
    value = Column(Float, nullable=False)
    value_raw = Column(Float)  # Before calibration
    quality_indicator = Column(Float, default=1.0)  # 0-1, data quality
    
    # Flags
    is_anomaly = Column(Boolean, default=False)
    anomaly_score = Column(Float)  # If anomaly detected
    is_out_of_range = Column(Boolean, default=False)
    
    # Metadata
    metadata = Column(JSONB, default={})
    
    # Relationships
    sensor = relationship("GridSensor", back_populates="readings")
    
    __table_args__ = (
        Index('idx_reading_timestamp', 'timestamp', postgresql_using='brin'),
        Index('idx_reading_sensor_time', 'sensor_id', 'timestamp'),
        Index('idx_reading_anomaly', 'is_anomaly', 'timestamp'),
    )


# ===== ALERTS & INCIDENTS =====

class GridAlert(Base):
    """
    Grid alerts and alarms
    Tahadhari za Gridi
    """
    __tablename__ = 'grid_alerts'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign Keys
    substation_id = Column(UUID(as_uuid=True), ForeignKey('grid_substations.id', ondelete='SET NULL'))
    sensor_id = Column(UUID(as_uuid=True), ForeignKey('grid_sensors.id', ondelete='SET NULL'))
    
    # Alert Info
    alert_type = Column(String(100), nullable=False, index=True)
    severity = Column(SQLEnum(AlertSeverity), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Status
    status = Column(SQLEnum(AlertStatus), default=AlertStatus.OPEN, index=True)
    
    # Details
    current_value = Column(Float)
    threshold_value = Column(Float)
    deviation_percentage = Column(Float)
    
    # Assignment
    assigned_to = Column(String(100))
    assigned_at = Column(DateTime)
    
    # Resolution
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(100))
    resolved_at = Column(DateTime)
    resolved_by = Column(String(100))
    resolution_notes = Column(Text)
    
    # Impact
    affected_customers = Column(Integer, default=0)
    estimated_revenue_loss = Column(Float)
    
    # Notifications
    sms_sent = Column(Boolean, default=False)
    email_sent = Column(Boolean, default=False)
    webhook_sent = Column(Boolean, default=False)
    
    # Metadata
    metadata = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    substation = relationship("GridSubstation", back_populates="alerts")
    
    __table_args__ = (
        Index('idx_alert_severity_status', 'severity', 'status'),
        Index('idx_alert_created', 'created_at', postgresql_using='brin'),
    )


# ===== MAINTENANCE =====

class MaintenanceRecord(Base):
    """
    Equipment maintenance records
    Rekodi za Matengenezo ya Vifaa
    """
    __tablename__ = 'maintenance_records'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign Keys
    transformer_id = Column(UUID(as_uuid=True), ForeignKey('transformers.id', ondelete='CASCADE'))
    
    # Maintenance Info
    maintenance_type = Column(SQLEnum(MaintenanceType), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Scheduling
    scheduled_date = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_hours = Column(Float)
    
    # Team
    technician_name = Column(String(100))
    team_size = Column(Integer, default=1)
    
    # Results
    status = Column(String(50), default='scheduled')  # scheduled, in_progress, completed, cancelled
    findings = Column(Text)
    actions_taken = Column(Text)
    parts_replaced = Column(ARRAY(String))
    
    # Costs
    labor_cost = Column(Float)
    parts_cost = Column(Float)
    total_cost = Column(Float)
    
    # Outcome
    was_successful = Column(Boolean)
    downtime_hours = Column(Float)
    next_maintenance_date = Column(DateTime)
    
    # Metadata
    metadata = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    transformer = relationship("Transformer", back_populates="maintenance_records")


# ===== PREDICTIONS & ANALYTICS =====

class LoadForecast(Base):
    """
    Electrical load forecasts
    Ubashiri wa Mzigo wa Umeme
    """
    __tablename__ = 'load_forecasts'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Forecast Info
    zone = Column(SQLEnum(GridZone), nullable=False, index=True)
    forecast_timestamp = Column(DateTime, nullable=False, index=True)  # When prediction is for
    
    # Predictions
    predicted_load_mw = Column(Float, nullable=False)
    confidence_interval_lower = Column(Float)
    confidence_interval_upper = Column(Float)
    confidence_percentage = Column(Float, default=95.0)
    
    # Model Info
    model_version = Column(String(50))
    prediction_error_mape = Column(Float)  # Mean Absolute Percentage Error
    
    # Actual (for validation)
    actual_load_mw = Column(Float)
    actual_recorded_at = Column(DateTime)
    
    # Metadata
    metadata = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_forecast_zone_time', 'zone', 'forecast_timestamp'),
    )


class AnomalyDetection(Base):
    """
    Detected anomalies in grid behavior
    Ugunduzi wa Kawaida Zisizo za Tabia ya Gridi
    """
    __tablename__ = 'anomaly_detections'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign Keys
    sensor_id = Column(UUID(as_uuid=True), ForeignKey('grid_sensors.id', ondelete='CASCADE'), nullable=False)
    
    # Anomaly Info
    anomaly_type = Column(String(100), nullable=False)  # spike, drift, outlier, pattern_break
    detected_at = Column(DateTime, nullable=False, index=True)
    
    # Severity
    anomaly_score = Column(Float, nullable=False)  # 0-1 or z-score
    severity = Column(SQLEnum(AlertSeverity), nullable=False)
    
    # Context
    expected_value = Column(Float)
    actual_value = Column(Float)
    deviation_percentage = Column(Float)
    
    # Analysis
    contributing_factors = Column(JSONB, default={})
    potential_causes = Column(ARRAY(String))
    recommended_actions = Column(ARRAY(String))
    
    # Investigation
    is_false_positive = Column(Boolean)
    investigated = Column(Boolean, default=False)
    investigation_notes = Column(Text)
    
    # Metadata
    metadata = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ===== CYBERSECURITY =====

class CyberSecurityEvent(Base):
    """
    SCADA cybersecurity events
    Matukio ya Usalama wa Mtandao wa SCADA
    """
    __tablename__ = 'cyber_security_events'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Event Info
    event_type = Column(String(100), nullable=False, index=True)  # failed_login, unusual_command, unauthorized_access
    severity = Column(SQLEnum(AlertSeverity), nullable=False, index=True)
    
    # Source
    source_ip = Column(INET)
    source_user = Column(String(100))
    target_system = Column(String(100))
    
    # Details
    description = Column(Text)
    command_attempted = Column(String(500))
    access_level_required = Column(String(50))
    
    # Detection
    detected_by = Column(String(100))  # agent, IDS, manual
    detection_method = Column(String(100))
    
    # Response
    is_blocked = Column(Boolean, default=False)
    response_action = Column(String(100))
    investigated = Column(Boolean, default=False)
    is_threat = Column(Boolean)
    
    # Metadata
    metadata = Column(JSONB, default={})
    
    # Timestamps
    occurred_at = Column(DateTime, nullable=False, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ===== ANALYTICS & REPORTING =====

class DailyGridStatistics(Base):
    """
    Daily aggregated grid statistics
    Takwimu za Kila Siku za Gridi
    """
    __tablename__ = 'daily_grid_statistics'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Date
    date = Column(DateTime, nullable=False, unique=True, index=True)
    zone = Column(SQLEnum(GridZone), nullable=False)
    
    # Load Statistics
    peak_load_mw = Column(Float)
    peak_load_time = Column(DateTime)
    average_load_mw = Column(Float)
    min_load_mw = Column(Float)
    total_energy_mwh = Column(Float)
    
    # Quality
    average_voltage_kv = Column(Float)
    voltage_violations_count = Column(Integer, default=0)
    frequency_violations_count = Column(Integer, default=0)
    
    # Reliability
    total_outages = Column(Integer, default=0)
    total_outage_minutes = Column(Float, default=0.0)
    saidi = Column(Float)  # System Average Interruption Duration Index
    saifi = Column(Float)  # System Average Interruption Frequency Index
    
    # Alerts
    total_alerts = Column(Integer, default=0)
    critical_alerts = Column(Integer, default=0)
    alerts_resolved = Column(Integer, default=0)
    
    # Maintenance
    scheduled_maintenance_hours = Column(Float, default=0.0)
    unscheduled_maintenance_hours = Column(Float, default=0.0)
    
    # Metadata
    metadata = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ===== HELPER FUNCTIONS =====

def init_db(engine):
    """Initialize database and create TimescaleDB hypertables"""
    Base.metadata.create_all(bind=engine)
    
    # Create TimescaleDB hypertable for sensor_readings
    with engine.connect() as conn:
        try:
            conn.execute("""
                SELECT create_hypertable('sensor_readings', 'timestamp',
                    chunk_time_interval => INTERVAL '1 day',
                    if_not_exists => TRUE
                );
            """)
            
            # Create continuous aggregates for performance
            conn.execute("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_readings_hourly
                WITH (timescaledb.continuous) AS
                SELECT
                    sensor_id,
                    time_bucket('1 hour', timestamp) AS bucket,
                    AVG(value) as avg_value,
                    MAX(value) as max_value,
                    MIN(value) as min_value,
                    COUNT(*) as reading_count
                FROM sensor_readings
                GROUP BY sensor_id, bucket;
            """)
            
            conn.commit()
        except Exception as e:
            print(f"TimescaleDB setup note: {e}")


def seed_initial_data(session):
    """Seed initial substations and sensors"""
    from datetime import datetime
    
    # Create sample substation
    substation = GridSubstation(
        name="Nairobi West Substation",
        code="NRB-WEST-001",
        zone=GridZone.NAIROBI,
        latitude=-1.3031,
        longitude=36.7833,
        voltage_level_kv=220,
        capacity_mva=100.0,
        num_transformers=2,
        commissioned_date=datetime(2020, 1, 1)
    )
    session.add(substation)
    session.commit()
    
    # Create sample sensors
    sensor_types = [SensorType.VOLTAGE, SensorType.CURRENT, SensorType.FREQUENCY]
    for i, sensor_type in enumerate(sensor_types):
        sensor = GridSensor(
            sensor_id=f"SENSOR-NRB-W-{i+1:03d}",
            sensor_type=sensor_type,
            substation_id=substation.id,
            measurement_unit="kV" if sensor_type == SensorType.VOLTAGE else ("A" if sensor_type == SensorType.CURRENT else "Hz"),
            status=SensorStatus.ACTIVE,
            is_critical=True
        )
        session.add(sensor)
    
    session.commit()
```

This is the complete database schema (800 lines). Next, let me create the SCADA integration module!
