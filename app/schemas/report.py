from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, field_validator


class DailyReportBase(BaseModel):
    company_id: int
    report_date: date
    report_type: Optional[str] = "daily"
    region: Optional[str] = None
    total_vehicles: Optional[int] = 0
    active_vehicles: Optional[int] = 0
    total_test_distance: Optional[float] = 0.0
    total_test_duration: Optional[float] = 0.0
    autopilot_distance: Optional[float] = 0.0
    manual_distance: Optional[float] = 0.0
    max_speed_recorded: Optional[float] = None
    average_speed: Optional[float] = None
    total_alarms: Optional[int] = 0
    critical_alarms: Optional[int] = 0
    warning_alarms: Optional[int] = 0
    info_alarms: Optional[int] = 0
    alarms_resolved: Optional[int] = 0
    accident_rate: Optional[float] = 0.0
    new_accidents: Optional[int] = 0
    ongoing_accidents: Optional[int] = 0
    total_maintenance_orders: Optional[int] = 0
    completed_maintenance: Optional[int] = 0
    pending_maintenance: Optional[int] = 0
    total_devices: Optional[int] = 0
    online_devices: Optional[int] = 0
    device_online_rate: Optional[float] = None
    data_upload_count: Optional[int] = 0
    data_upload_size: Optional[int] = 0
    operational_efficiency: Optional[float] = None
    safety_index: Optional[float] = None
    key_events: Optional[str] = None
    issues: Optional[str] = None
    notes: Optional[str] = None
    generated_by: Optional[str] = None
    generated_at: Optional[datetime] = None

    @field_validator("report_type")
    @classmethod
    def validate_report_type(cls, v: str) -> str:
        valid_types = ["daily", "weekly", "monthly", "quarterly", "yearly"]
        if v.lower() not in valid_types:
            raise ValueError(f"报告类型必须是: {', '.join(valid_types)}")
        return v.lower()


class DailyReportCreate(DailyReportBase):
    pass


class DailyReportUpdate(BaseModel):
    report_type: Optional[str] = None
    region: Optional[str] = None
    total_vehicles: Optional[int] = None
    active_vehicles: Optional[int] = None
    total_test_distance: Optional[float] = None
    total_test_duration: Optional[float] = None
    autopilot_distance: Optional[float] = None
    manual_distance: Optional[float] = None
    max_speed_recorded: Optional[float] = None
    average_speed: Optional[float] = None
    total_alarms: Optional[int] = None
    critical_alarms: Optional[int] = None
    warning_alarms: Optional[int] = None
    info_alarms: Optional[int] = None
    alarms_resolved: Optional[int] = None
    accident_rate: Optional[float] = None
    new_accidents: Optional[int] = None
    ongoing_accidents: Optional[int] = None
    total_maintenance_orders: Optional[int] = None
    completed_maintenance: Optional[int] = None
    pending_maintenance: Optional[int] = None
    total_devices: Optional[int] = None
    online_devices: Optional[int] = None
    device_online_rate: Optional[float] = None
    data_upload_count: Optional[int] = None
    data_upload_size: Optional[int] = None
    operational_efficiency: Optional[float] = None
    safety_index: Optional[float] = None
    key_events: Optional[str] = None
    issues: Optional[str] = None
    notes: Optional[str] = None
    generated_by: Optional[str] = None
    generated_at: Optional[datetime] = None


class DailyReportResponse(DailyReportBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VehicleStatistics(BaseModel):
    total_vehicles: int
    active_vehicles: int
    active_rate: float
    total_test_distance: float
    total_test_duration: float
    autopilot_distance: float
    manual_distance: float
    autopilot_ratio: float

    class Config:
        from_attributes = True


class AlarmStatistics(BaseModel):
    total_alarms: int
    critical_alarms: int
    warning_alarms: int
    info_alarms: int
    alarms_resolved: int
    resolution_rate: float
    alarm_types: Optional[Dict[str, int]] = None

    class Config:
        from_attributes = True


class SafetyStatistics(BaseModel):
    accident_rate: float
    new_accidents: int
    ongoing_accidents: int
    safety_index: float
    critical_incidents: int

    class Config:
        from_attributes = True


class DeviceStatistics(BaseModel):
    total_devices: int
    online_devices: int
    offline_devices: int
    device_online_rate: float
    maintenance_pending: int

    class Config:
        from_attributes = True


class MultiDimensionReport(BaseModel):
    report_date: date
    vehicle_stats: VehicleStatistics
    alarm_stats: AlarmStatistics
    safety_stats: SafetyStatistics
    device_stats: DeviceStatistics
    operational_efficiency: Optional[float] = None
    summary: Optional[str] = None

    class Config:
        from_attributes = True
