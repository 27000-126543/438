from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, field_validator


class AccidentReportBase(BaseModel):
    company_id: int
    vehicle_id: int
    report_number: str
    accident_type: str
    severity: str
    accident_time: datetime
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    weather_condition: Optional[str] = None
    road_condition: Optional[str] = None
    traffic_condition: Optional[str] = None
    speed_before: Optional[float] = None
    autopilot_mode: Optional[str] = None
    driver_name: Optional[str] = None
    driver_license: Optional[str] = None
    passenger_count: Optional[int] = 0
    description: Optional[str] = None
    injuries: Optional[str] = None
    damages: Optional[str] = None
    vehicle_log_data: Optional[Any] = None
    roadside_sensor_data: Optional[Dict[str, Any]] = None
    police_report: Optional[str] = None
    insurance_claim_number: Optional[str] = None
    insurance_status: Optional[str] = "pending"
    evidence_files: Optional[List[str]] = None
    status: Optional[str] = "under_investigation"
    conclusion: Optional[str] = None
    responsibility_determination: Optional[Dict[str, Any]] = None
    responsible_party: Optional[str] = None
    preventive_measures: Optional[str] = None
    police_notified: Optional[bool] = False
    police_notified_at: Optional[datetime] = None
    rescue_notified: Optional[bool] = False
    rescue_notified_at: Optional[datetime] = None
    reported_by: Optional[str] = None
    reported_at: Optional[datetime] = None
    investigated_by: Optional[str] = None
    closed_at: Optional[datetime] = None

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        valid_severities = ["minor", "moderate", "severe", "fatal"]
        if v.lower() not in valid_severities:
            raise ValueError(f"事故严重程度必须是: {', '.join(valid_severities)}")
        return v.lower()

    @field_validator("insurance_status")
    @classmethod
    def validate_insurance_status(cls, v: str) -> str:
        valid_statuses = ["pending", "submitted", "reviewing", "approved", "rejected", "paid"]
        if v.lower() not in valid_statuses:
            raise ValueError(f"保险状态必须是: {', '.join(valid_statuses)}")
        return v.lower()


class AccidentReportCreate(AccidentReportBase):
    simulate_failure_step: Optional[str] = None


class AccidentReportUpdate(BaseModel):
    accident_type: Optional[str] = None
    severity: Optional[str] = None
    accident_time: Optional[datetime] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    weather_condition: Optional[str] = None
    road_condition: Optional[str] = None
    traffic_condition: Optional[str] = None
    speed_before: Optional[float] = None
    autopilot_mode: Optional[str] = None
    driver_name: Optional[str] = None
    driver_license: Optional[str] = None
    passenger_count: Optional[int] = None
    description: Optional[str] = None
    injuries: Optional[str] = None
    damages: Optional[str] = None
    vehicle_log_data: Optional[Any] = None
    roadside_sensor_data: Optional[Dict[str, Any]] = None
    police_report: Optional[str] = None
    insurance_claim_number: Optional[str] = None
    insurance_status: Optional[str] = None
    evidence_files: Optional[List[str]] = None
    status: Optional[str] = None
    conclusion: Optional[str] = None
    responsibility_determination: Optional[Dict[str, Any]] = None
    responsible_party: Optional[str] = None
    preventive_measures: Optional[str] = None
    police_notified: Optional[bool] = None
    police_notified_at: Optional[datetime] = None
    rescue_notified: Optional[bool] = None
    rescue_notified_at: Optional[datetime] = None
    reported_by: Optional[str] = None
    reported_at: Optional[datetime] = None
    investigated_by: Optional[str] = None
    closed_at: Optional[datetime] = None


class AccidentReportResponse(AccidentReportBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ResponsibilityDetermination(BaseModel):
    accident_id: int
    report_number: str
    responsible_parties: List[Dict[str, Any]]
    responsibility_distribution: Dict[str, float]
    determination_basis: str
    determination_date: datetime
    determined_by: str

    class Config:
        from_attributes = True


class InsuranceClaimProcess(BaseModel):
    accident_id: int
    claim_number: str
    current_stage: str
    stage_history: List[Dict[str, Any]]
    estimated_amount: Optional[float] = None
    approved_amount: Optional[float] = None
    paid_amount: Optional[float] = None
    next_action: Optional[str] = None
    deadline: Optional[datetime] = None

    class Config:
        from_attributes = True


class AccidentGenerateReport(BaseModel):
    vehicle_id: int
    accident_time: Optional[datetime] = None
    window_minutes: int = 30


class AccidentAnalysisReport(BaseModel):
    report_number: str
    accident_summary: Dict[str, Any]
    vehicle_log_analysis: Dict[str, Any]
    roadside_sensor_analysis: Dict[str, Any]
    timeline_reconstruction: List[Dict[str, Any]]
    liability_determination: ResponsibilityDetermination
    recommended_actions: List[str]
    generated_at: datetime

    class Config:
        from_attributes = True


class NotificationResult(BaseModel):
    notified: bool
    notified_at: Optional[datetime] = None
    message: str

    class Config:
        from_attributes = True


class StepStatus(BaseModel):
    step: str
    success: bool
    message: str
    executed_at: Optional[datetime] = None
    error: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None


class AccidentOneClickResponse(BaseModel):
    accident_id: int
    report_number: str
    analysis_summary: Optional[Dict[str, Any]] = None
    liability_result: Optional[Dict[str, Any]] = None
    insurance_claim_number: Optional[str] = None
    police_notified_at: Optional[datetime] = None
    rescue_notified_at: Optional[datetime] = None
    steps: List[StepStatus]
    all_succeeded: bool
    blocked_at_step: Optional[str] = None

    class Config:
        from_attributes = True


class DisposalStepHistory(BaseModel):
    id: int
    step_name: str
    attempt_number: int
    status: str
    message: Optional[str] = None
    error: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class SubsequentStepExecution(BaseModel):
    step_name: str
    success: bool
    status: str
    message: str
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AccidentDisposalDetailResponse(BaseModel):
    accident_id: int
    report_number: str
    overall_status: str
    all_succeeded: bool
    failed_step: Optional[str] = None
    blocked_at_step: Optional[str] = None
    total_attempts: int
    timeline: List[DisposalStepHistory]

    class Config:
        from_attributes = True


class StepRetryResponse(BaseModel):
    accident_id: int
    step_name: str
    attempt_number: int
    status: str
    success: bool
    message: str
    error: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    subsequent_executed: List[SubsequentStepExecution] = []
    new_blocked_at_step: Optional[str] = None
    all_succeeded: Optional[bool] = None
