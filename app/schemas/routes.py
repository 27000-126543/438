from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class RouteBase(BaseModel):
    route_name: str = Field(..., max_length=100)
    route_code: str = Field(..., max_length=50)
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
    description: Optional[str] = None
    vehicle_ids: Optional[List[int]] = None


class RouteCreate(RouteBase):
    pass


class RouteUpdate(BaseModel):
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
    suggested_schedule: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    vehicle_ids: Optional[List[int]] = None


class RouteRecommendationRequest(BaseModel):
    start_point: str
    end_point: str
    scheduled_start: Optional[datetime] = None
    vehicle_type: Optional[str] = None
    automation_level: Optional[str] = None
    preferred_route_type: Optional[str] = None


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


class ScheduleConflict(BaseModel):
    conflicting_route_id: int
    conflicting_route_name: str
    conflict_type: str
    conflicting_start: datetime
    conflicting_end: datetime
    suggested_start: datetime
    suggested_end: datetime


class RouteApplicationResponse(BaseModel):
    route_id: Optional[int] = None
    status: str
    recommendations: Optional[List[RouteRecommendation]] = None
    conflicts: Optional[List[ScheduleConflict]] = None
    suggested_schedule: Optional[Dict[str, Any]] = None
    message: str


class RouteInDB(RouteBase):
    id: int
    company_id: int
    accident_risk_score: Optional[float] = None
    approval_status: str
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    suggested_schedule: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Route(RouteInDB):
    pass
