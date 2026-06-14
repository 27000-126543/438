from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, field_validator


class TestRouteBase(BaseModel):
    route_name: str
    route_code: str
    route_type: Optional[str] = None
    test_area: Optional[str] = None
    start_point: Optional[str] = None
    end_point: Optional[str] = None
    waypoints: Optional[List[Dict[str, Any]]] = None
    total_distance: Optional[float] = None
    estimated_duration: Optional[int] = None
    road_level: Optional[str] = None
    traffic_condition: Optional[str] = None
    weather_condition: Optional[str] = None
    speed_limit: Optional[float] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    accident_risk_score: Optional[float] = None
    approval_status: Optional[str] = "pending"
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    suggested_schedule: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

    @field_validator("speed_limit")
    @classmethod
    def check_speed_limit(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("限速不能为负数")
        return v

    @field_validator("scheduled_end")
    @classmethod
    def check_schedule(cls, v: Optional[datetime], info: Any) -> Optional[datetime]:
        scheduled_start = info.data.get("scheduled_start")
        if v and scheduled_start and v < scheduled_start:
            raise ValueError("结束时间不能早于开始时间")
        return v


class TestRouteCreate(TestRouteBase):
    vehicle_ids: Optional[List[int]] = None


class TestRouteUpdate(BaseModel):
    route_name: Optional[str] = None
    route_type: Optional[str] = None
    start_point: Optional[str] = None
    end_point: Optional[str] = None
    waypoints: Optional[List[Dict[str, Any]]] = None
    total_distance: Optional[float] = None
    estimated_duration: Optional[int] = None
    road_level: Optional[str] = None
    traffic_condition: Optional[str] = None
    weather_condition: Optional[str] = None
    speed_limit: Optional[float] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    accident_risk_score: Optional[float] = None
    approval_status: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    suggested_schedule: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    vehicle_ids: Optional[List[int]] = None


class TestRouteResponse(TestRouteBase):
    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RouteConflictDetection(BaseModel):
    route_id: int
    route_name: str
    conflict_type: str
    conflict_details: str
    conflict_routes: Optional[List[int]] = None
    severity: str
    suggestion: Optional[str] = None

    class Config:
        from_attributes = True


class RouteRecommendation(BaseModel):
    route_name: str
    start_point: str
    end_point: str
    waypoints: List[Dict[str, Any]]
    total_distance: float
    estimated_duration: int
    road_level: str
    traffic_condition: str
    weather_condition: str
    speed_limit: float
    accident_risk_score: float
    risk_factors: List[str]
    safety_tips: List[str]

    class Config:
        from_attributes = True


class RouteRecommendationRequest(BaseModel):
    start_point: Optional[str] = None
    end_point: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    road_level: Optional[str] = None
    traffic_condition: Optional[str] = None
    weather_condition: Optional[str] = None
    vehicle_type: Optional[str] = None
    automation_level: Optional[str] = None
    preferred_route_type: Optional[str] = None


class ScheduleConflict(BaseModel):
    conflicting_route_id: int
    conflicting_route_name: str
    conflict_type: str
    conflicting_start: datetime
    conflicting_end: datetime
    suggested_start: datetime
    suggested_end: datetime


class RouteApplicationResponse(BaseModel):
    status: str
    recommended_routes: List[RouteRecommendation]
    conflicts: Optional[List[ScheduleConflict]] = None
    risk_score: Optional[float] = None
    suggested_speed_limit: Optional[float] = None
    suggested_schedule: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

    class Config:
        from_attributes = True
