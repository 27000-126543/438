from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, field_validator


class DeviceHeartbeat(BaseModel):
    device_code: str
    status: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    firmware_version: Optional[str] = None
    sensor_data: Optional[Dict[str, Any]] = None
    error_codes: Optional[List[str]] = None


class RoadsideDeviceBase(BaseModel):
    route_id: Optional[int] = None
    device_code: str
    device_name: str
    device_type: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    installation_date: Optional[date] = None
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    communication_type: Optional[str] = None
    ip_address: Optional[str] = None
    status: Optional[str] = "online"
    last_heartbeat: Optional[datetime] = None
    offline_since: Optional[datetime] = None
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    maintenance_skills: Optional[List[str]] = None
    description: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_device_status(cls, v: str) -> str:
        valid_statuses = ["online", "offline", "maintenance", "faulty", "decommissioned"]
        if v.lower() not in valid_statuses:
            raise ValueError(f"设备状态必须是: {', '.join(valid_statuses)}")
        return v.lower()


class RoadsideDeviceCreate(RoadsideDeviceBase):
    pass


class RoadsideDeviceUpdate(BaseModel):
    route_id: Optional[int] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    installation_date: Optional[date] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    communication_type: Optional[str] = None
    ip_address: Optional[str] = None
    status: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    offline_since: Optional[datetime] = None
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    maintenance_skills: Optional[List[str]] = None
    description: Optional[str] = None


class RoadsideDeviceResponse(RoadsideDeviceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeviceOfflineDetection(BaseModel):
    device_id: int
    device_code: str
    device_name: str
    is_offline: bool
    last_heartbeat: Optional[datetime] = None
    offline_duration_minutes: Optional[float] = None
    offline_since: Optional[datetime] = None

    class Config:
        from_attributes = True


class MaintenanceWorkOrderBase(BaseModel):
    company_id: int
    vehicle_id: Optional[int] = None
    device_id: Optional[int] = None
    order_number: str
    title: str
    description: Optional[str] = None
    maintenance_type: str
    priority: Optional[str] = "normal"
    required_skills: Optional[List[str]] = None
    status: Optional[str] = "pending"
    reported_by: Optional[str] = None
    reported_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    assignee_skills: Optional[List[str]] = None
    assigned_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    parts_used: Optional[Dict[str, Any]] = None
    labor_hours: Optional[float] = None
    total_cost: Optional[float] = None
    work_done: Optional[str] = None
    findings: Optional[str] = None
    recommendations: Optional[str] = None
    inspection_results: Optional[Dict[str, Any]] = None
    signature: Optional[str] = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        valid_priorities = ["low", "normal", "high", "urgent", "critical"]
        if v.lower() not in valid_priorities:
            raise ValueError(f"优先级必须是: {', '.join(valid_priorities)}")
        return v.lower()

    @field_validator("status")
    @classmethod
    def validate_order_status(cls, v: str) -> str:
        valid_statuses = [
            "pending", "assigned", "scheduled", "in_progress",
            "on_hold", "completed", "cancelled", "rejected"
        ]
        if v.lower() not in valid_statuses:
            raise ValueError(f"工单状态必须是: {', '.join(valid_statuses)}")
        return v.lower()


class MaintenanceWorkOrderCreate(MaintenanceWorkOrderBase):
    pass


class MaintenanceWorkOrderUpdate(BaseModel):
    vehicle_id: Optional[int] = None
    device_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    maintenance_type: Optional[str] = None
    priority: Optional[str] = None
    required_skills: Optional[List[str]] = None
    status: Optional[str] = None
    reported_by: Optional[str] = None
    reported_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    assignee_skills: Optional[List[str]] = None
    assigned_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    parts_used: Optional[Dict[str, Any]] = None
    labor_hours: Optional[float] = None
    total_cost: Optional[float] = None
    work_done: Optional[str] = None
    findings: Optional[str] = None
    recommendations: Optional[str] = None
    inspection_results: Optional[Dict[str, Any]] = None
    signature: Optional[str] = None


class MaintenanceWorkOrderResponse(MaintenanceWorkOrderBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AssignmentBasis(BaseModel):
    skill_score: float
    skill_weight: float
    distance_score: float
    distance_weight: float
    workload_score: float
    workload_weight: float
    total_score: float
    skill_match_ratio: float
    distance_km: float
    current_workload: int

    class Config:
        from_attributes = True


class EscalationRule(BaseModel):
    level: int
    condition: str
    action: str
    notify_roles: List[str]
    timeout_minutes: int

    class Config:
        from_attributes = True


class CandidateRanking(BaseModel):
    staff_id: int
    staff_name: str
    rank: int
    total_score: float
    skill_score: float
    distance_score: float
    workload_score: float
    skill_match_ratio: float
    distance_km: Optional[float] = None
    current_workload: int
    eligible: bool
    elimination_reason: Optional[str] = None
    elimination_details: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class MaintenanceAssignment(BaseModel):
    work_order_id: int
    order_number: str
    assigned_staff_id: Optional[int] = None
    assigned_staff_name: Optional[str] = None
    matched_skills: Optional[List[str]] = None
    missing_skills: Optional[List[str]] = None
    estimated_arrival_time: Optional[datetime] = None
    estimated_completion_time: Optional[datetime] = None
    assignment_basis: Optional[AssignmentBasis] = None
    escalation_rules: Optional[List[EscalationRule]] = None
    success: bool = False
    reason: Optional[str] = None
    message: Optional[str] = None
    pending_reason_detail: Optional[Dict[str, Any]] = None
    candidate_rankings: Optional[List[CandidateRanking]] = None
    total_candidates: Optional[int] = None
    eligible_count: Optional[int] = None

    class Config:
        from_attributes = True
