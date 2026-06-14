from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


VALID_AUTOMATION_LEVELS = {"L1", "L2", "L3", "L4", "L5"}


class TestVehicleBase(BaseModel):
    vin: str
    license_plate: str
    vehicle_model: str
    vehicle_type: Optional[str] = None
    automation_level: Optional[str] = None
    test_type: Optional[str] = None
    test_area: Optional[str] = None
    manufacture_date: Optional[date] = None
    registration_date: Optional[date] = None
    test_expiry_date: Optional[date] = None
    insurance_expiry_date: Optional[date] = None
    vehicle_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = "idle"
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    current_speed: Optional[float] = None
    mileage: Optional[float] = 0.0
    disengagement_count: Optional[int] = 0
    scene_coverage: Optional[Dict[str, Any]] = None

    @field_validator("automation_level")
    @classmethod
    def validate_automation_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_AUTOMATION_LEVELS:
            raise ValueError(f"自动化等级必须是 L1-L5 中的一个，当前值: {v}")
        return v

    @field_validator("insurance_expiry_date")
    @classmethod
    def check_insurance_expiry(cls, v: Optional[date]) -> Optional[date]:
        if v and v < date.today():
            raise ValueError("保险已过期")
        return v


class TestVehicleCreate(TestVehicleBase):
    company_id: Optional[int] = None


class TestVehicleRegister(TestVehicleBase):
    pass


class VehicleRegisterCreate(BaseModel):
    vin: Optional[str] = None
    license_plate: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_type: Optional[str] = None
    automation_level: Optional[str] = None
    test_type: Optional[str] = None
    test_area: Optional[str] = None
    manufacture_date: Optional[date] = None
    registration_date: Optional[date] = None
    test_expiry_date: Optional[date] = None
    insurance_expiry_date: Optional[date] = None
    vehicle_config: Optional[Dict[str, Any]] = None


class TestVehicleUpdate(BaseModel):
    vehicle_type: Optional[str] = None
    automation_level: Optional[str] = None
    test_type: Optional[str] = None
    test_area: Optional[str] = None
    manufacture_date: Optional[date] = None
    registration_date: Optional[date] = None
    test_expiry_date: Optional[date] = None
    insurance_expiry_date: Optional[date] = None
    vehicle_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    current_speed: Optional[float] = None
    mileage: Optional[float] = None
    disengagement_count: Optional[int] = None
    scene_coverage: Optional[Dict[str, Any]] = None


class TestVehicleResponse(TestVehicleBase):
    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VehicleInsuranceStatus(BaseModel):
    vehicle_id: int
    vin: str
    license_plate: str
    insurance_expiry_date: Optional[date] = None
    is_expired: bool
    days_until_expiry: Optional[int] = None

    class Config:
        from_attributes = True
