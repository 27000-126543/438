from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, field_validator


class VehicleRealtimeDataBase(BaseModel):
    vehicle_id: int
    route_id: Optional[int] = None
    timestamp: Optional[datetime] = None
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    acceleration: Optional[float] = None
    brake_status: Optional[bool] = None
    throttle_position: Optional[float] = None
    steering_angle: Optional[float] = None
    gear: Optional[str] = None
    engine_rpm: Optional[int] = None
    fuel_level: Optional[float] = None
    battery_level: Optional[float] = None
    autopilot_enabled: Optional[bool] = None
    autopilot_mode: Optional[str] = None
    obstacle_detected: Optional[bool] = None
    obstacle_distance: Optional[float] = None
    lane_departure: Optional[bool] = None
    signal_light: Optional[str] = None
    sensor_data: Optional[Dict[str, Any]] = None
    error_codes: Optional[List[str]] = None
    received_at: Optional[datetime] = None


class VehicleRealtimeDataCreate(VehicleRealtimeDataBase):
    pass


class VehicleRealtimeDataUpdate(BaseModel):
    route_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    speed: Optional[float] = None
    heading: Optional[float] = None
    acceleration: Optional[float] = None
    brake_status: Optional[bool] = None
    throttle_position: Optional[float] = None
    steering_angle: Optional[float] = None
    gear: Optional[str] = None
    engine_rpm: Optional[int] = None
    fuel_level: Optional[float] = None
    battery_level: Optional[float] = None
    autopilot_enabled: Optional[bool] = None
    autopilot_mode: Optional[str] = None
    obstacle_detected: Optional[bool] = None
    obstacle_distance: Optional[float] = None
    lane_departure: Optional[bool] = None
    signal_light: Optional[str] = None
    sensor_data: Optional[Dict[str, Any]] = None
    error_codes: Optional[List[str]] = None


class VehicleRealtimeDataResponse(VehicleRealtimeDataBase):
    id: int

    class Config:
        from_attributes = True


class VehicleDeviationDetection(BaseModel):
    vehicle_id: int
    license_plate: str
    is_deviated: bool
    deviation_distance: Optional[float] = None
    planned_route_id: Optional[int] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    deviation_details: Optional[str] = None
    detected_at: datetime

    class Config:
        from_attributes = True


class VehicleSpeedingDetection(BaseModel):
    vehicle_id: int
    license_plate: str
    is_speeding: bool
    current_speed: Optional[float] = None
    speed_limit: Optional[float] = None
    speeding_percentage: Optional[float] = None
    detected_at: datetime

    class Config:
        from_attributes = True


class AlarmBase(BaseModel):
    company_id: int
    vehicle_id: int
    alarm_type: str
    alarm_level: str
    alarm_code: Optional[str] = None
    title: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: Optional[datetime] = None
    status: Optional[str] = "pending"
    assigned_to: Optional[str] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    related_data: Optional[Dict[str, Any]] = None
    accident_report_id: Optional[int] = None

    @field_validator("alarm_level")
    @classmethod
    def validate_alarm_level(cls, v: str) -> str:
        valid_levels = ["info", "warning", "critical", "emergency"]
        if v.lower() not in valid_levels:
            raise ValueError(f"告警级别必须是: {', '.join(valid_levels)}")
        return v.lower()


class AlarmCreate(AlarmBase):
    pass


class AlarmUpdate(BaseModel):
    alarm_type: Optional[str] = None
    alarm_level: Optional[str] = None
    alarm_code: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    related_data: Optional[Dict[str, Any]] = None
    accident_report_id: Optional[int] = None


class AlarmResponse(AlarmBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
