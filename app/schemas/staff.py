from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, field_validator


class MaintenanceStaffBase(BaseModel):
    staff_code: str
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    skills: Optional[List[str]] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    status: Optional[str] = "available"
    workload: Optional[int] = 0

    @field_validator("status")
    @classmethod
    def validate_staff_status(cls, v: str) -> str:
        valid_statuses = ["available", "busy", "on_leave", "offline", "disabled"]
        if v.lower() not in valid_statuses:
            raise ValueError(f"状态必须是: {', '.join(valid_statuses)}")
        return v.lower()


class MaintenanceStaffCreate(MaintenanceStaffBase):
    pass


class MaintenanceStaffUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    skills: Optional[List[str]] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    status: Optional[str] = None
    workload: Optional[int] = None


class MaintenanceStaffResponse(MaintenanceStaffBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SafetyOfficerBase(BaseModel):
    officer_code: str
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    license_number: Optional[str] = None
    certification_level: Optional[str] = None
    status: Optional[str] = "on_duty"
    current_vehicle_id: Optional[int] = None
    workload: Optional[int] = 0

    @field_validator("status")
    @classmethod
    def validate_officer_status(cls, v: str) -> str:
        valid_statuses = ["on_duty", "off_duty", "on_leave", "in_vehicle", "disabled"]
        if v.lower() not in valid_statuses:
            raise ValueError(f"状态必须是: {', '.join(valid_statuses)}")
        return v.lower()

    @field_validator("certification_level")
    @classmethod
    def validate_certification_level(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_levels = ["junior", "intermediate", "senior", "expert"]
        if v.lower() not in valid_levels:
            raise ValueError(f"资质级别必须是: {', '.join(valid_levels)}")
        return v.lower()


class SafetyOfficerCreate(SafetyOfficerBase):
    pass


class SafetyOfficerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    license_number: Optional[str] = None
    certification_level: Optional[str] = None
    status: Optional[str] = None
    current_vehicle_id: Optional[int] = None
    workload: Optional[int] = None


class SafetyOfficerResponse(SafetyOfficerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
