from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text,
    ForeignKey, JSON, BigInteger, UniqueConstraint, Index, Table
)
from sqlalchemy.orm import relationship
from passlib.context import CryptContext

from app.database import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(200), nullable=False, index=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    phone = Column(String(20))
    password_hash = Column(String(255), nullable=False)
    company_license = Column(String(100))
    business_scope = Column(Text)
    status = Column(String(20), default="active")
    role = Column(String(20), default="enterprise")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vehicles = relationship("TestVehicle", back_populates="company", cascade="all, delete-orphan")
    routes = relationship("TestRoute", back_populates="company", cascade="all, delete-orphan")
    alarms = relationship("Alarm", back_populates="company", cascade="all, delete-orphan")
    accident_reports = relationship("AccidentReport", back_populates="company", cascade="all, delete-orphan")
    completion_reports = relationship("TestCompletion", back_populates="company", cascade="all, delete-orphan")
    maintenance_orders = relationship("MaintenanceWorkOrder", back_populates="company", cascade="all, delete-orphan")
    daily_reports = relationship("DailyReport", back_populates="company", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = pwd_context.hash(password)

    def check_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def to_dict(self):
        return {
            "id": self.id,
            "company_name": self.company_name,
            "username": self.username,
            "email": self.email,
            "phone": self.phone,
            "company_license": self.company_license,
            "business_scope": self.business_scope,
            "status": self.status,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


vehicle_route_association = Table(
    "vehicle_route_association",
    Base.metadata,
    Column("vehicle_id", Integer, ForeignKey("test_vehicles.id"), primary_key=True),
    Column("route_id", Integer, ForeignKey("test_routes.id"), primary_key=True),
    Column("assigned_at", DateTime, default=datetime.utcnow)
)


class TestVehicle(Base):
    __tablename__ = "test_vehicles"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    vin = Column(String(50), unique=True, nullable=False, index=True)
    license_plate = Column(String(20), unique=True, nullable=False, index=True)
    vehicle_model = Column(String(100), nullable=False)
    vehicle_type = Column(String(50))
    automation_level = Column(String(20))
    test_type = Column(String(50))
    test_area = Column(String(100))
    manufacture_date = Column(Date)
    registration_date = Column(Date)
    test_expiry_date = Column(Date, index=True)
    insurance_expiry_date = Column(Date, index=True)
    vehicle_config = Column(JSON)
    status = Column(String(20), default="idle")
    current_latitude = Column(Float)
    current_longitude = Column(Float)
    current_speed = Column(Float)
    mileage = Column(Float, default=0.0)
    disengagement_count = Column(Integer, default=0)
    scene_coverage = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("User", back_populates="vehicles")
    routes = relationship(
        "TestRoute",
        secondary=vehicle_route_association,
        back_populates="vehicles"
    )
    realtime_data = relationship("VehicleRealtimeData", back_populates="vehicle", cascade="all, delete-orphan")
    alarms = relationship("Alarm", back_populates="vehicle", cascade="all, delete-orphan")
    accident_reports = relationship("AccidentReport", back_populates="vehicle", cascade="all, delete-orphan")
    completion_reports = relationship("TestCompletion", back_populates="vehicle", cascade="all, delete-orphan")
    maintenance_orders = relationship("MaintenanceWorkOrder", back_populates="vehicle", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "company_name": self.company.company_name if self.company else None,
            "vin": self.vin,
            "license_plate": self.license_plate,
            "vehicle_model": self.vehicle_model,
            "vehicle_type": self.vehicle_type,
            "automation_level": self.automation_level,
            "test_type": self.test_type,
            "test_area": self.test_area,
            "manufacture_date": self.manufacture_date.isoformat() if self.manufacture_date else None,
            "registration_date": self.registration_date.isoformat() if self.registration_date else None,
            "test_expiry_date": self.test_expiry_date.isoformat() if self.test_expiry_date else None,
            "insurance_expiry_date": self.insurance_expiry_date.isoformat() if self.insurance_expiry_date else None,
            "vehicle_config": self.vehicle_config,
            "status": self.status,
            "current_latitude": self.current_latitude,
            "current_longitude": self.current_longitude,
            "current_speed": self.current_speed,
            "mileage": self.mileage,
            "disengagement_count": self.disengagement_count,
            "scene_coverage": self.scene_coverage,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class TestRoute(Base):
    __tablename__ = "test_routes"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    route_name = Column(String(100), nullable=False, index=True)
    route_code = Column(String(50), unique=True, nullable=False, index=True)
    route_type = Column(String(50))
    test_area = Column(String(100))
    start_point = Column(String(200))
    end_point = Column(String(200))
    waypoints = Column(JSON)
    total_distance = Column(Float)
    estimated_duration = Column(Integer)
    road_level = Column(String(50))
    traffic_condition = Column(String(50))
    weather_condition = Column(String(50))
    speed_limit = Column(Float)
    scheduled_start = Column(DateTime)
    scheduled_end = Column(DateTime)
    accident_risk_score = Column(Float)
    approval_status = Column(String(20), default="pending")
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    suggested_schedule = Column(JSON)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("User", back_populates="routes")
    vehicles = relationship(
        "TestVehicle",
        secondary=vehicle_route_association,
        back_populates="routes"
    )
    realtime_data = relationship("VehicleRealtimeData", back_populates="route")
    roadside_devices = relationship("RoadsideDevice", back_populates="route", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "company_name": self.company.company_name if self.company else None,
            "route_name": self.route_name,
            "route_code": self.route_code,
            "route_type": self.route_type,
            "test_area": self.test_area,
            "start_point": self.start_point,
            "end_point": self.end_point,
            "waypoints": self.waypoints,
            "total_distance": self.total_distance,
            "estimated_duration": self.estimated_duration,
            "road_level": self.road_level,
            "traffic_condition": self.traffic_condition,
            "weather_condition": self.weather_condition,
            "speed_limit": self.speed_limit,
            "scheduled_start": self.scheduled_start.isoformat() if self.scheduled_start else None,
            "scheduled_end": self.scheduled_end.isoformat() if self.scheduled_end else None,
            "accident_risk_score": self.accident_risk_score,
            "approval_status": self.approval_status,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejection_reason": self.rejection_reason,
            "suggested_schedule": self.suggested_schedule,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class VehicleRealtimeData(Base):
    __tablename__ = "vehicle_realtime_data"

    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, ForeignKey("test_vehicles.id"), nullable=False, index=True)
    route_id = Column(Integer, ForeignKey("test_routes.id"), index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float)
    speed = Column(Float)
    heading = Column(Float)
    acceleration = Column(Float)
    brake_status = Column(Boolean)
    throttle_position = Column(Float)
    steering_angle = Column(Float)
    gear = Column(String(10))
    engine_rpm = Column(Integer)
    fuel_level = Column(Float)
    battery_level = Column(Float)
    autopilot_enabled = Column(Boolean)
    autopilot_mode = Column(String(50))
    obstacle_detected = Column(Boolean)
    obstacle_distance = Column(Float)
    lane_departure = Column(Boolean)
    signal_light = Column(String(20))
    sensor_data = Column(JSON)
    error_codes = Column(JSON)
    received_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_vehicle_timestamp", "vehicle_id", "timestamp"),
    )

    vehicle = relationship("TestVehicle", back_populates="realtime_data")
    route = relationship("TestRoute", back_populates="realtime_data")

    def to_dict(self):
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "route_id": self.route_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "speed": self.speed,
            "heading": self.heading,
            "acceleration": self.acceleration,
            "brake_status": self.brake_status,
            "throttle_position": self.throttle_position,
            "steering_angle": self.steering_angle,
            "gear": self.gear,
            "engine_rpm": self.engine_rpm,
            "fuel_level": self.fuel_level,
            "battery_level": self.battery_level,
            "autopilot_enabled": self.autopilot_enabled,
            "autopilot_mode": self.autopilot_mode,
            "obstacle_detected": self.obstacle_detected,
            "obstacle_distance": self.obstacle_distance,
            "lane_departure": self.lane_departure,
            "signal_light": self.signal_light,
            "sensor_data": self.sensor_data,
            "error_codes": self.error_codes,
            "received_at": self.received_at.isoformat() if self.received_at else None
        }


class Alarm(Base):
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("test_vehicles.id"), nullable=False, index=True)
    alarm_type = Column(String(50), nullable=False, index=True)
    alarm_level = Column(String(20), nullable=False, index=True)
    alarm_code = Column(String(50), index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(20), default="pending", index=True)
    assigned_to = Column(String(80))
    acknowledged_by = Column(String(80))
    acknowledged_at = Column(DateTime)
    resolved_by = Column(String(80))
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)
    related_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    accident_report_id = Column(Integer, ForeignKey("accident_reports.id"))

    company = relationship("User", back_populates="alarms")
    vehicle = relationship("TestVehicle", back_populates="alarms")
    accident_report = relationship("AccidentReport", back_populates="alarms")

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "vehicle_id": self.vehicle_id,
            "license_plate": self.vehicle.license_plate if self.vehicle else None,
            "alarm_type": self.alarm_type,
            "alarm_level": self.alarm_level,
            "alarm_code": self.alarm_code,
            "title": self.title,
            "description": self.description,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes,
            "related_data": self.related_data,
            "accident_report_id": self.accident_report_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class AccidentReport(Base):
    __tablename__ = "accident_reports"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("test_vehicles.id"), nullable=False, index=True)
    report_number = Column(String(50), unique=True, nullable=False, index=True)
    accident_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    accident_time = Column(DateTime, nullable=False, index=True)
    location = Column(String(200), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    weather_condition = Column(String(50))
    road_condition = Column(String(50))
    traffic_condition = Column(String(50))
    speed_before = Column(Float)
    autopilot_mode = Column(String(50))
    driver_name = Column(String(80))
    driver_license = Column(String(50))
    passenger_count = Column(Integer, default=0)
    description = Column(Text)
    injuries = Column(Text)
    damages = Column(Text)
    vehicle_log_data = Column(JSON)
    roadside_sensor_data = Column(JSON)
    police_report = Column(String(200))
    insurance_claim_number = Column(String(50))
    insurance_status = Column(String(20), default="pending")
    evidence_files = Column(JSON)
    status = Column(String(20), default="under_investigation", index=True)
    conclusion = Column(Text)
    responsibility_determination = Column(JSON)
    responsible_party = Column(String(100))
    preventive_measures = Column(Text)
    police_notified = Column(Boolean, default=False)
    police_notified_at = Column(DateTime)
    rescue_notified = Column(Boolean, default=False)
    rescue_notified_at = Column(DateTime)
    blocked_at_step = Column(String(50))
    reported_by = Column(String(80))
    reported_at = Column(DateTime, default=datetime.utcnow)
    investigated_by = Column(String(80))
    closed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("User", back_populates="accident_reports")
    vehicle = relationship("TestVehicle", back_populates="accident_reports")
    alarms = relationship("Alarm", back_populates="accident_report")
    disposal_steps = relationship("AccidentDisposalStep", back_populates="accident", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "vehicle_id": self.vehicle_id,
            "license_plate": self.vehicle.license_plate if self.vehicle else None,
            "report_number": self.report_number,
            "accident_type": self.accident_type,
            "severity": self.severity,
            "accident_time": self.accident_time.isoformat() if self.accident_time else None,
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "weather_condition": self.weather_condition,
            "road_condition": self.road_condition,
            "traffic_condition": self.traffic_condition,
            "speed_before": self.speed_before,
            "autopilot_mode": self.autopilot_mode,
            "driver_name": self.driver_name,
            "driver_license": self.driver_license,
            "passenger_count": self.passenger_count,
            "description": self.description,
            "injuries": self.injuries,
            "damages": self.damages,
            "vehicle_log_data": self.vehicle_log_data,
            "roadside_sensor_data": self.roadside_sensor_data,
            "police_report": self.police_report,
            "insurance_claim_number": self.insurance_claim_number,
            "insurance_status": self.insurance_status,
            "evidence_files": self.evidence_files,
            "status": self.status,
            "conclusion": self.conclusion,
            "responsibility_determination": self.responsibility_determination,
            "responsible_party": self.responsible_party,
            "preventive_measures": self.preventive_measures,
            "police_notified": self.police_notified,
            "police_notified_at": self.police_notified_at.isoformat() if self.police_notified_at else None,
            "rescue_notified": self.rescue_notified,
            "rescue_notified_at": self.rescue_notified_at.isoformat() if self.rescue_notified_at else None,
            "reported_by": self.reported_by,
            "reported_at": self.reported_at.isoformat() if self.reported_at else None,
            "investigated_by": self.investigated_by,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class TestCompletion(Base):
    __tablename__ = "test_completion_reports"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("test_vehicles.id"), nullable=False, index=True)
    report_number = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    test_period_start = Column(Date, nullable=False)
    test_period_end = Column(Date, nullable=False)
    test_type = Column(String(50))
    test_area = Column(String(100))
    total_test_distance = Column(Float)
    total_test_duration = Column(Float)
    autopilot_distance = Column(Float)
    manual_distance = Column(Float)
    average_speed = Column(Float)
    max_speed = Column(Float)
    total_alarms = Column(Integer, default=0)
    critical_alarms = Column(Integer, default=0)
    safety_incidents = Column(Integer, default=0)
    disengagement_count = Column(Integer, default=0)
    scene_coverage_rate = Column(Float)
    scene_details = Column(JSON)
    system_reliability = Column(Float)
    test_objectives = Column(Text)
    test_scope = Column(Text)
    test_methodology = Column(Text)
    test_results = Column(Text)
    issues_encountered = Column(Text)
    improvements_made = Column(Text)
    conclusions = Column(Text)
    recommendations = Column(Text)
    attached_files = Column(JSON)
    status = Column(String(20), default="draft", index=True)
    submitted_by = Column(String(80))
    submitted_at = Column(DateTime)
    reviewed_by = Column(String(80))
    reviewed_at = Column(DateTime)
    review_comments = Column(Text)
    approved_by = Column(String(80))
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("User", back_populates="completion_reports")
    vehicle = relationship("TestVehicle", back_populates="completion_reports")

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "vehicle_id": self.vehicle_id,
            "license_plate": self.vehicle.license_plate if self.vehicle else None,
            "report_number": self.report_number,
            "title": self.title,
            "test_period_start": self.test_period_start.isoformat() if self.test_period_start else None,
            "test_period_end": self.test_period_end.isoformat() if self.test_period_end else None,
            "test_type": self.test_type,
            "test_area": self.test_area,
            "total_test_distance": self.total_test_distance,
            "total_test_duration": self.total_test_duration,
            "autopilot_distance": self.autopilot_distance,
            "manual_distance": self.manual_distance,
            "average_speed": self.average_speed,
            "max_speed": self.max_speed,
            "total_alarms": self.total_alarms,
            "critical_alarms": self.critical_alarms,
            "safety_incidents": self.safety_incidents,
            "disengagement_count": self.disengagement_count,
            "scene_coverage_rate": self.scene_coverage_rate,
            "scene_details": self.scene_details,
            "system_reliability": self.system_reliability,
            "test_objectives": self.test_objectives,
            "test_scope": self.test_scope,
            "test_methodology": self.test_methodology,
            "test_results": self.test_results,
            "issues_encountered": self.issues_encountered,
            "improvements_made": self.improvements_made,
            "conclusions": self.conclusions,
            "recommendations": self.recommendations,
            "attached_files": self.attached_files,
            "status": self.status,
            "submitted_by": self.submitted_by,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_comments": self.review_comments,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class RoadsideDevice(Base):
    __tablename__ = "roadside_devices"

    id = Column(Integer, primary_key=True)
    route_id = Column(Integer, ForeignKey("test_routes.id"), index=True)
    device_code = Column(String(50), unique=True, nullable=False, index=True)
    device_name = Column(String(100), nullable=False)
    device_type = Column(String(50), nullable=False, index=True)
    manufacturer = Column(String(100))
    model = Column(String(50))
    serial_number = Column(String(100))
    installation_date = Column(Date)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float)
    communication_type = Column(String(50))
    ip_address = Column(String(50))
    status = Column(String(20), default="online", index=True)
    last_heartbeat = Column(DateTime)
    offline_since = Column(DateTime)
    firmware_version = Column(String(50))
    hardware_version = Column(String(50))
    configuration = Column(JSON)
    maintenance_skills = Column(JSON)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    route = relationship("TestRoute", back_populates="roadside_devices")
    maintenance_orders = relationship("MaintenanceWorkOrder", back_populates="device", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "route_id": self.route_id,
            "route_name": self.route.route_name if self.route else None,
            "device_code": self.device_code,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serial_number": self.serial_number,
            "installation_date": self.installation_date.isoformat() if self.installation_date else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "communication_type": self.communication_type,
            "ip_address": self.ip_address,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "offline_since": self.offline_since.isoformat() if self.offline_since else None,
            "firmware_version": self.firmware_version,
            "hardware_version": self.hardware_version,
            "configuration": self.configuration,
            "maintenance_skills": self.maintenance_skills,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class MaintenanceWorkOrder(Base):
    __tablename__ = "maintenance_work_orders"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("test_vehicles.id"), index=True)
    device_id = Column(Integer, ForeignKey("roadside_devices.id"), index=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    maintenance_type = Column(String(50), nullable=False, index=True)
    priority = Column(String(20), default="normal", index=True)
    required_skills = Column(JSON)
    status = Column(String(20), default="pending", index=True)
    reported_by = Column(String(80))
    reported_at = Column(DateTime, default=datetime.utcnow)
    assigned_to = Column(String(80))
    assignee_id = Column(Integer)
    assignee_skills = Column(JSON)
    assigned_at = Column(DateTime)
    estimated_arrival = Column(DateTime)
    estimated_completion = Column(DateTime)
    scheduled_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    parts_used = Column(JSON)
    labor_hours = Column(Float)
    total_cost = Column(Float)
    work_done = Column(Text)
    findings = Column(Text)
    recommendations = Column(Text)
    inspection_results = Column(JSON)
    signature = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("User", back_populates="maintenance_orders")
    vehicle = relationship("TestVehicle", back_populates="maintenance_orders")
    device = relationship("RoadsideDevice", back_populates="maintenance_orders")

    def to_dict(self):
        return {
            "id": self.id,
            "company_id": self.company_id,
            "vehicle_id": self.vehicle_id,
            "device_id": self.device_id,
            "order_number": self.order_number,
            "title": self.title,
            "description": self.description,
            "maintenance_type": self.maintenance_type,
            "priority": self.priority,
            "required_skills": self.required_skills,
            "status": self.status,
            "reported_by": self.reported_by,
            "reported_at": self.reported_at.isoformat() if self.reported_at else None,
            "assigned_to": self.assigned_to,
            "assignee_skills": self.assignee_skills,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "estimated_arrival": self.estimated_arrival.isoformat() if self.estimated_arrival else None,
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "parts_used": self.parts_used,
            "labor_hours": self.labor_hours,
            "total_cost": self.total_cost,
            "work_done": self.work_done,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "inspection_results": self.inspection_results,
            "signature": self.signature,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class DataCatalog(Base):
    __tablename__ = "data_catalogs"

    id = Column(Integer, primary_key=True)
    catalog_code = Column(String(50), unique=True, nullable=False, index=True)
    catalog_name = Column(String(200), nullable=False, index=True)
    data_type = Column(String(50), nullable=False, index=True)
    data_source = Column(String(100))
    description = Column(Text)
    storage_location = Column(String(500))
    storage_format = Column(String(50))
    data_size = Column(BigInteger)
    record_count = Column(BigInteger)
    time_range_start = Column(DateTime)
    time_range_end = Column(DateTime)
    data_owner = Column(String(80))
    access_level = Column(String(20), default="internal")
    encryption_enabled = Column(Boolean, default=False)
    desensitization_enabled = Column(Boolean, default=False)
    desensitization_rules = Column(JSON)
    backup_enabled = Column(Boolean, default=True)
    retention_period = Column(Integer)
    data_schema = Column(JSON)
    sample_data = Column(JSON)
    quality_score = Column(Float)
    update_frequency = Column(String(50))
    last_updated = Column(DateTime)
    last_accessed = Column(DateTime)
    access_count = Column(Integer, default=0)
    status = Column(String(20), default="active", index=True)
    tags = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "catalog_code": self.catalog_code,
            "catalog_name": self.catalog_name,
            "data_type": self.data_type,
            "data_source": self.data_source,
            "description": self.description,
            "storage_location": self.storage_location,
            "storage_format": self.storage_format,
            "data_size": self.data_size,
            "record_count": self.record_count,
            "time_range_start": self.time_range_start.isoformat() if self.time_range_start else None,
            "time_range_end": self.time_range_end.isoformat() if self.time_range_end else None,
            "data_owner": self.data_owner,
            "access_level": self.access_level,
            "encryption_enabled": self.encryption_enabled,
            "desensitization_enabled": self.desensitization_enabled,
            "desensitization_rules": self.desensitization_rules,
            "backup_enabled": self.backup_enabled,
            "retention_period": self.retention_period,
            "data_schema": self.data_schema,
            "sample_data": self.sample_data,
            "quality_score": self.quality_score,
            "update_frequency": self.update_frequency,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "status": self.status,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    report_date = Column(Date, nullable=False, index=True)
    report_type = Column(String(50), default="daily")
    region = Column(String(100))
    total_vehicles = Column(Integer, default=0)
    active_vehicles = Column(Integer, default=0)
    total_test_distance = Column(Float, default=0.0)
    total_test_duration = Column(Float, default=0.0)
    autopilot_distance = Column(Float, default=0.0)
    manual_distance = Column(Float, default=0.0)
    max_speed_recorded = Column(Float)
    average_speed = Column(Float)
    total_alarms = Column(Integer, default=0)
    critical_alarms = Column(Integer, default=0)
    warning_alarms = Column(Integer, default=0)
    info_alarms = Column(Integer, default=0)
    alarms_resolved = Column(Integer, default=0)
    accident_rate = Column(Float, default=0.0)
    new_accidents = Column(Integer, default=0)
    ongoing_accidents = Column(Integer, default=0)
    total_maintenance_orders = Column(Integer, default=0)
    completed_maintenance = Column(Integer, default=0)
    pending_maintenance = Column(Integer, default=0)
    total_devices = Column(Integer, default=0)
    online_devices = Column(Integer, default=0)
    device_online_rate = Column(Float)
    data_upload_count = Column(BigInteger, default=0)
    data_upload_size = Column(BigInteger, default=0)
    operational_efficiency = Column(Float)
    safety_index = Column(Float)
    key_events = Column(Text)
    issues = Column(Text)
    notes = Column(Text)
    generated_by = Column(String(80))
    generated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("company_id", "report_date", "region", name="uq_company_report_date_region"),
    )

    company = relationship("User", back_populates="daily_reports")

    def to_dict(self):
        company_name = None
        try:
            if self.company is not None:
                company_name = self.company.company_name
        except Exception:
            pass
        return {
            "id": self.id,
            "company_id": self.company_id,
            "company_name": company_name,
            "report_date": self.report_date.isoformat() if self.report_date else None,
            "report_type": self.report_type,
            "region": self.region,
            "total_vehicles": self.total_vehicles,
            "active_vehicles": self.active_vehicles,
            "total_test_distance": self.total_test_distance,
            "total_test_duration": self.total_test_duration,
            "autopilot_distance": self.autopilot_distance,
            "manual_distance": self.manual_distance,
            "max_speed_recorded": self.max_speed_recorded,
            "average_speed": self.average_speed,
            "total_alarms": self.total_alarms,
            "critical_alarms": self.critical_alarms,
            "warning_alarms": self.warning_alarms,
            "info_alarms": self.info_alarms,
            "alarms_resolved": self.alarms_resolved,
            "accident_rate": self.accident_rate,
            "new_accidents": self.new_accidents,
            "ongoing_accidents": self.ongoing_accidents,
            "total_maintenance_orders": self.total_maintenance_orders,
            "completed_maintenance": self.completed_maintenance,
            "pending_maintenance": self.pending_maintenance,
            "total_devices": self.total_devices,
            "online_devices": self.online_devices,
            "device_online_rate": self.device_online_rate,
            "data_upload_count": self.data_upload_count,
            "data_upload_size": self.data_upload_size,
            "operational_efficiency": self.operational_efficiency,
            "safety_index": self.safety_index,
            "key_events": self.key_events,
            "issues": self.issues,
            "notes": self.notes,
            "generated_by": self.generated_by,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class MaintenanceStaff(Base):
    __tablename__ = "maintenance_staff"

    id = Column(Integer, primary_key=True)
    staff_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(80), nullable=False)
    phone = Column(String(20))
    email = Column(String(120))
    skills = Column(JSON)
    current_latitude = Column(Float)
    current_longitude = Column(Float)
    status = Column(String(20), default="available")
    workload = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "staff_code": self.staff_code,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "skills": self.skills,
            "current_latitude": self.current_latitude,
            "current_longitude": self.current_longitude,
            "status": self.status,
            "workload": self.workload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class SafetyOfficer(Base):
    __tablename__ = "safety_officers"

    id = Column(Integer, primary_key=True)
    officer_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(80), nullable=False)
    phone = Column(String(20))
    email = Column(String(120))
    license_number = Column(String(50))
    certification_level = Column(String(20))
    status = Column(String(20), default="on_duty")
    current_vehicle_id = Column(Integer, ForeignKey("test_vehicles.id"))
    workload = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    current_vehicle = relationship("TestVehicle", foreign_keys=[current_vehicle_id])

    def to_dict(self):
        return {
            "id": self.id,
            "officer_code": self.officer_code,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "license_number": self.license_number,
            "certification_level": self.certification_level,
            "status": self.status,
            "current_vehicle_id": self.current_vehicle_id,
            "workload": self.workload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class AccidentDisposalStep(Base):
    __tablename__ = "accident_disposal_steps"

    id = Column(Integer, primary_key=True)
    accident_id = Column(Integer, ForeignKey("accident_reports.id"), nullable=False, index=True)
    step_name = Column(String(50), nullable=False, index=True)
    attempt_number = Column(Integer, default=1)
    status = Column(String(20), nullable=False)
    message = Column(Text)
    error = Column(Text)
    result_data = Column(JSON)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    accident = relationship("AccidentReport", back_populates="disposal_steps")

    __table_args__ = (
        UniqueConstraint("accident_id", "step_name", "attempt_number", name="uq_accident_step_attempt"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "accident_id": self.accident_id,
            "step_name": self.step_name,
            "attempt_number": self.attempt_number,
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "result_data": self.result_data,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.started_at and self.completed_at else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
