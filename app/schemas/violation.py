from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ViolationBase(BaseModel):
    vehicle_id: int
    violation_type: str
    violation_time: datetime
    location: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    description: Optional[str] = None
    evidence_url: Optional[str] = None
    status: Optional[str] = "pending"
    fine_amount: Optional[float] = None
    points: Optional[int] = None


class ViolationCreate(ViolationBase):
    pass


class ViolationUpdate(BaseModel):
    violation_type: Optional[str] = None
    violation_time: Optional[datetime] = None
    location: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    description: Optional[str] = None
    evidence_url: Optional[str] = None
    status: Optional[str] = None
    fine_amount: Optional[float] = None
    points: Optional[int] = None


class ViolationInDB(ViolationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Violation(ViolationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
