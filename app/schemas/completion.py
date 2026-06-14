from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, field_validator


class TestCompletionBase(BaseModel):
    company_id: int
    vehicle_id: int
    report_number: str
    title: str
    test_period_start: date
    test_period_end: date
    test_type: Optional[str] = None
    test_area: Optional[str] = None
    total_test_distance: Optional[float] = None
    total_test_duration: Optional[float] = None
    autopilot_distance: Optional[float] = None
    manual_distance: Optional[float] = None
    average_speed: Optional[float] = None
    max_speed: Optional[float] = None
    total_alarms: Optional[int] = 0
    critical_alarms: Optional[int] = 0
    safety_incidents: Optional[int] = 0
    disengagement_count: Optional[int] = 0
    scene_coverage_rate: Optional[float] = None
    scene_details: Optional[Dict[str, Any]] = None
    system_reliability: Optional[float] = None
    test_objectives: Optional[str] = None
    test_scope: Optional[str] = None
    test_methodology: Optional[str] = None
    test_results: Optional[str] = None
    issues_encountered: Optional[str] = None
    improvements_made: Optional[str] = None
    conclusions: Optional[str] = None
    recommendations: Optional[str] = None
    attached_files: Optional[List[str]] = None
    status: Optional[str] = "draft"
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_comments: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    @field_validator("test_period_end")
    @classmethod
    def check_test_period(cls, v: date, info: Any) -> date:
        test_period_start = info.data.get("test_period_start")
        if v and test_period_start and v < test_period_start:
            raise ValueError("测试结束日期不能早于开始日期")
        return v

    @field_validator("scene_coverage_rate")
    @classmethod
    def check_coverage_rate(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("场景覆盖率应在 0-100 之间")
        return v


class TestCompletionCreate(TestCompletionBase):
    pass


class TestCompletionUpdate(BaseModel):
    title: Optional[str] = None
    test_period_start: Optional[date] = None
    test_period_end: Optional[date] = None
    test_type: Optional[str] = None
    test_area: Optional[str] = None
    total_test_distance: Optional[float] = None
    total_test_duration: Optional[float] = None
    autopilot_distance: Optional[float] = None
    manual_distance: Optional[float] = None
    average_speed: Optional[float] = None
    max_speed: Optional[float] = None
    total_alarms: Optional[int] = None
    critical_alarms: Optional[int] = None
    safety_incidents: Optional[int] = None
    disengagement_count: Optional[int] = None
    scene_coverage_rate: Optional[float] = None
    scene_details: Optional[Dict[str, Any]] = None
    system_reliability: Optional[float] = None
    test_objectives: Optional[str] = None
    test_scope: Optional[str] = None
    test_methodology: Optional[str] = None
    test_results: Optional[str] = None
    issues_encountered: Optional[str] = None
    improvements_made: Optional[str] = None
    conclusions: Optional[str] = None
    recommendations: Optional[str] = None
    attached_files: Optional[List[str]] = None
    status: Optional[str] = None
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_comments: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


class TestCompletionResponse(TestCompletionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MileageStatistics(BaseModel):
    vehicle_id: int
    total_distance: float
    autopilot_distance: float
    manual_distance: float
    autopilot_ratio: float
    report_period_start: date
    report_period_end: date

    class Config:
        from_attributes = True


class SceneCoverageStatistics(BaseModel):
    vehicle_id: int
    coverage_rate: float
    scene_details: Dict[str, Any]
    missing_scenes: Optional[List[str]] = None

    class Config:
        from_attributes = True


class DisengagementStatistics(BaseModel):
    vehicle_id: int
    total_disengagements: int
    disengagement_rate_per_km: float
    disengagement_reasons: Dict[str, int]
    report_period_start: date
    report_period_end: date

    class Config:
        from_attributes = True


class MilestoneStats(BaseModel):
    total_test_distance: float
    autopilot_distance: float
    manual_distance: float
    total_test_duration: float
    average_speed: float
    max_speed: float
    disengagement_count: int
    scene_coverage_rate: float
    scene_details: Dict[str, Any]
    total_alarms: int
    critical_alarms: int
    safety_incidents: int
    system_reliability: float

    class Config:
        from_attributes = True


class CompletionGenerateReport(BaseModel):
    vehicle_id: int
    test_period_start: Optional[date] = None
    test_period_end: Optional[date] = None
    title: Optional[str] = None


class CompletionReviewReport(BaseModel):
    report_number: str
    title: str
    test_period: Dict[str, Any]
    mileage_summary: Dict[str, Any]
    scene_coverage: Dict[str, Any]
    disengagement_analysis: Dict[str, Any]
    alarm_statistics: Dict[str, Any]
    safety_assessment: Dict[str, Any]
    system_reliability: float
    conclusions: str
    recommendations: List[str]
    review_status: str
    generated_at: datetime
