from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.database import get_db
from app.models import (
    AccidentReport, TestVehicle, VehicleRealtimeData, RoadsideDevice, Alarm, User,
    AccidentDisposalStep
)
from app.schemas.accident import (
    AccidentReportCreate, AccidentReportResponse, AccidentReportUpdate,
    ResponsibilityDetermination, InsuranceClaimProcess,
    AccidentGenerateReport, AccidentAnalysisReport, NotificationResult,
    StepStatus, AccidentOneClickResponse,
    DisposalStepHistory, AccidentDisposalDetailResponse, StepRetryResponse
)

router = APIRouter(tags=["事故处理"])


VALID_STEPS = [
    "create_accident",
    "generate_analysis",
    "determine_liability",
    "trigger_insurance",
    "notify_police",
    "notify_rescue"
]

STEP_NAMES_CN = {
    "create_accident": "创建事故报告",
    "generate_analysis": "生成事故分析",
    "determine_liability": "责任划分",
    "trigger_insurance": "触发保险理赔",
    "notify_police": "通知交警",
    "notify_rescue": "通知救援"
}

STEP_ORDER = {
    "create_accident": 0,
    "generate_analysis": 1,
    "determine_liability": 2,
    "trigger_insurance": 3,
    "notify_police": 4,
    "notify_rescue": 5
}

SUBSEQUENT_STEPS = {
    "create_accident": ["generate_analysis", "determine_liability", "trigger_insurance", "notify_police", "notify_rescue"],
    "generate_analysis": ["determine_liability", "trigger_insurance", "notify_police", "notify_rescue"],
    "determine_liability": ["trigger_insurance", "notify_police", "notify_rescue"],
    "trigger_insurance": ["notify_police", "notify_rescue"],
    "notify_police": ["notify_rescue"],
    "notify_rescue": []
}


def generate_report_number() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"ACC-{timestamp}"


async def save_disposal_step(
    db: AsyncSession,
    accident_id: int,
    step_name: str,
    status: str,
    message: str = "",
    error: str = None,
    result_data: dict = None,
    started_at: datetime = None,
    completed_at: datetime = None,
) -> AccidentDisposalStep:
    result = await db.execute(
        select(AccidentDisposalStep).where(
            and_(
                AccidentDisposalStep.accident_id == accident_id,
                AccidentDisposalStep.step_name == step_name
            )
        ).order_by(desc(AccidentDisposalStep.attempt_number))
    )
    last_step = result.scalar_one_or_none()
    attempt_number = last_step.attempt_number + 1 if last_step else 1

    step = AccidentDisposalStep(
        accident_id=accident_id,
        step_name=step_name,
        attempt_number=attempt_number,
        status=status,
        message=message,
        error=error,
        result_data=result_data,
        started_at=started_at,
        completed_at=completed_at,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


async def step_generate_analysis(
    db: AsyncSession,
    accident: AccidentReport,
    vehicle: TestVehicle,
    accident_in: AccidentReportCreate = None
) -> tuple[bool, str, dict, Exception]:
    started_at = datetime.utcnow()
    try:
        log_data_list = []
        if accident.vehicle_log_data:
            if isinstance(accident.vehicle_log_data, list):
                log_data_list = accident.vehicle_log_data
            elif isinstance(accident.vehicle_log_data, dict) and "logs" in accident.vehicle_log_data:
                log_data_list = accident.vehicle_log_data["logs"]

        log_analysis = {
            "data": log_data_list,
            "abnormal_events": _detect_abnormal_events(log_data_list),
            "autopilot_engaged": accident.autopilot_mode == "autopilot"
        }
        sensor_analysis = {"data": accident.roadside_sensor_data or {}}

        timeline = _reconstruct_timeline(log_data_list, accident.accident_time)
        liability = _determine_liability(log_analysis, sensor_analysis, [], accident.id, accident.report_number)

        analysis_summary = {
            "report_number": accident.report_number,
            "accident_summary": {
                "vehicle_id": accident.vehicle_id,
                "license_plate": vehicle.license_plate,
                "accident_time": accident.accident_time.isoformat(),
                "location": accident.location,
                "severity": accident.severity
            },
            "timeline_reconstruction": timeline,
            "recommended_actions": _generate_recommendations(liability, log_analysis)
        }

        return True, "事故分析报告生成成功", analysis_summary, None, started_at, datetime.utcnow()
    except Exception as e:
        return False, "事故分析报告生成失败", None, e, started_at, datetime.utcnow()


async def step_determine_liability(
    db: AsyncSession,
    accident: AccidentReport,
) -> tuple[bool, str, dict, Exception]:
    started_at = datetime.utcnow()
    try:
        log_data_list = []
        if accident.vehicle_log_data:
            if isinstance(accident.vehicle_log_data, list):
                log_data_list = accident.vehicle_log_data
            elif isinstance(accident.vehicle_log_data, dict) and "logs" in accident.vehicle_log_data:
                log_data_list = accident.vehicle_log_data["logs"]
        log_analysis = {
            "data": log_data_list,
            "abnormal_events": _detect_abnormal_events(log_data_list)
        }
        sensor_data = accident.roadside_sensor_data or {}
        sensor_analysis = {"data": sensor_data}

        liability = _determine_liability(log_analysis, sensor_analysis, [], accident.id, accident.report_number)

        accident.responsibility_determination = {
            "responsible_parties": [p.model_dump() if hasattr(p, 'model_dump') else p for p in liability.responsible_parties],
            "responsibility_distribution": liability.responsibility_distribution,
            "determination_basis": liability.determination_basis
        }
        primary_party = liability.responsible_parties[0].get("party") if liability.responsible_parties else None
        accident.responsible_party = primary_party
        await db.commit()
        await db.refresh(accident)

        liability_result = {
            "accident_id": liability.accident_id,
            "report_number": liability.report_number,
            "responsible_parties": liability.responsible_parties,
            "responsibility_distribution": liability.responsibility_distribution,
            "determination_basis": liability.determination_basis,
            "determination_date": liability.determination_date.isoformat(),
            "determined_by": liability.determined_by
        }

        return True, "责任划分完成", liability_result, None, started_at, datetime.utcnow()
    except Exception as e:
        return False, "责任划分失败", None, e, started_at, datetime.utcnow()


async def step_trigger_insurance(
    db: AsyncSession,
    accident: AccidentReport,
) -> tuple[bool, str, dict, Exception]:
    started_at = datetime.utcnow()
    try:
        claim_number = f"INS-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        estimated_amount = _estimate_insurance_amount(accident)

        accident.insurance_claim_number = claim_number
        accident.insurance_status = "submitted"
        await db.commit()
        await db.refresh(accident)

        result = {
            "claim_number": claim_number,
            "estimated_amount": estimated_amount
        }

        return True, f"保险理赔已触发，预估金额 {estimated_amount} 元", result, None, started_at, datetime.utcnow()
    except Exception as e:
        return False, "保险理赔触发失败", None, e, started_at, datetime.utcnow()


async def step_notify_police(
    db: AsyncSession,
    accident: AccidentReport,
) -> tuple[bool, str, dict, Exception]:
    started_at = datetime.utcnow()
    try:
        if not accident.police_notified:
            accident.police_notified = True
            accident.police_notified_at = datetime.utcnow()
            await db.commit()
            await db.refresh(accident)

        result = {
            "notified": True,
            "notified_at": accident.police_notified_at.isoformat() if accident.police_notified_at else None
        }

        return True, f"已通知交警处理事故编号 {accident.report_number}", result, None, started_at, datetime.utcnow()
    except Exception as e:
        return False, "交警通知失败", None, e, started_at, datetime.utcnow()


async def step_notify_rescue(
    db: AsyncSession,
    accident: AccidentReport,
) -> tuple[bool, str, dict, Exception]:
    started_at = datetime.utcnow()
    try:
        if not accident.rescue_notified:
            accident.rescue_notified = True
            accident.rescue_notified_at = datetime.utcnow()
            await db.commit()
            await db.refresh(accident)

        result = {
            "notified": True,
            "notified_at": accident.rescue_notified_at.isoformat() if accident.rescue_notified_at else None
        }

        return True, f"已通知救援前往事故地点 {accident.location}", result, None, started_at, datetime.utcnow()
    except Exception as e:
        return False, "救援通知失败", None, e, started_at, datetime.utcnow()


async def execute_disposal_step(
    db: AsyncSession,
    accident: AccidentReport,
    step_name: str,
    vehicle: TestVehicle = None,
    accident_in: AccidentReportCreate = None
) -> tuple[bool, str, dict, Exception, datetime, datetime, any]:
    step_functions = {
        "generate_analysis": lambda: step_generate_analysis(db, accident, vehicle, accident_in),
        "determine_liability": lambda: step_determine_liability(db, accident),
        "trigger_insurance": lambda: step_trigger_insurance(db, accident),
        "notify_police": lambda: step_notify_police(db, accident),
        "notify_rescue": lambda: step_notify_rescue(db, accident),
    }

    step_func = step_functions.get(step_name)
    if not step_func:
        return False, f"未知步骤: {step_name}", None, ValueError(f"未知步骤: {step_name}"), datetime.utcnow(), datetime.utcnow(), None

    started_at = datetime.utcnow()
    if accident_in and accident_in.simulate_failure_step and accident_in.simulate_failure_step == step_name:
        error_msg = f"模拟{STEP_NAMES_CN.get(step_name, step_name)}步骤失败（测试用）"
        await save_disposal_step(
            db, accident.id, step_name,
            "failed",
            message=error_msg, error=error_msg,
            result_data=None,
            started_at=started_at, completed_at=datetime.utcnow()
        )
        return False, error_msg, None, Exception(error_msg), started_at, datetime.utcnow()

    success, message, result_data, error, _, completed_at = await step_func()

    await save_disposal_step(
        db, accident.id, step_name,
        "success" if success else "failed",
        message=message, error=str(error) if error else None,
        result_data=result_data,
        started_at=started_at, completed_at=completed_at
    )

    return success, message, result_data, error, started_at, completed_at


async def run_disposal_from_step(
    db: AsyncSession,
    accident: AccidentReport,
    start_step: str,
    vehicle: TestVehicle = None,
    accident_in: AccidentReportCreate = None
) -> List[StepStatus]:
    steps: List[StepStatus] = []
    step_names = SUBSEQUENT_STEPS.get(start_step, [])
    if start_step != "create_accident":
        step_names = [start_step] + SUBSEQUENT_STEPS.get(start_step, [])

    current_step = start_step
    blocked = False

    for step_name in step_names:
        if blocked:
            steps.append(StepStatus(
                step=step_name,
                success=False,
                message=f"已跳过，因前序步骤 {STEP_NAMES_CN.get(current_step, current_step)} 失败",
                executed_at=datetime.utcnow(),
                error="blocked_by_previous_failure"
            ))
            continue

        success, message, result_data, error, started_at, completed_at = await execute_disposal_step(
            db, accident, step_name, vehicle, accident_in
        )

        step_status = StepStatus(
            step=step_name,
            success=success,
            message=message,
            executed_at=completed_at,
            error=str(error) if error else None,
            result_data=result_data
        )
        steps.append(step_status)

        if not success:
            blocked = True
            current_step = step_name
            accident.blocked_at_step = step_name
            await db.commit()
            await db.refresh(accident)
            break

    if not blocked:
        accident.blocked_at_step = None
        await db.commit()
        await db.refresh(accident)

    return steps


@router.post("", response_model=AccidentOneClickResponse, status_code=201)
async def create_accident(
    accident_in: AccidentReportCreate,
    db: AsyncSession = Depends(get_db)
):
    steps: List[StepStatus] = []
    analysis_summary = None
    liability_result = None
    insurance_claim_number = None
    police_notified_at = None
    rescue_notified_at = None

    result = await db.execute(
        select(TestVehicle).where(TestVehicle.id == accident_in.vehicle_id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        step_status = StepStatus(
            step="create_accident",
            success=False,
            message="创建事故报告失败",
            executed_at=datetime.utcnow(),
            error="车辆不存在"
        )
        steps.append(step_status)
        return AccidentOneClickResponse(
            accident_id=0,
            report_number="",
            steps=steps,
            all_succeeded=False,
            blocked_at_step="create_accident"
        )

    report_number = generate_report_number()
    create_started = datetime.utcnow()
    accident = AccidentReport(
        company_id=vehicle.company_id,
        vehicle_id=accident_in.vehicle_id,
        report_number=report_number,
        accident_type=accident_in.accident_type,
        severity=accident_in.severity,
        accident_time=accident_in.accident_time,
        location=accident_in.location,
        latitude=accident_in.latitude,
        longitude=accident_in.longitude,
        weather_condition=accident_in.weather_condition,
        road_condition=accident_in.road_condition,
        traffic_condition=accident_in.traffic_condition,
        speed_before=accident_in.speed_before,
        autopilot_mode=accident_in.autopilot_mode,
        driver_name=accident_in.driver_name,
        driver_license=accident_in.driver_license,
        passenger_count=accident_in.passenger_count,
        description=accident_in.description,
        injuries=accident_in.injuries,
        damages=accident_in.damages,
        vehicle_log_data=accident_in.vehicle_log_data,
        roadside_sensor_data=accident_in.roadside_sensor_data,
    )
    db.add(accident)
    await db.commit()
    await db.refresh(accident)
    create_completed = datetime.utcnow()

    await save_disposal_step(
        db, accident.id, "create_accident", "success",
        message="事故报告创建成功",
        started_at=create_started, completed_at=create_completed
    )
    steps.append(StepStatus(
        step="create_accident",
        success=True,
        message="事故报告创建成功",
        executed_at=create_completed
    ))

    disposal_steps = await run_disposal_from_step(
        db, accident, "generate_analysis", vehicle, accident_in
    )
    steps.extend(disposal_steps)

    for s in disposal_steps:
        if s.success:
            if s.step == "generate_analysis" and s.error is None:
                analysis_summary = s.result_data
            elif s.step == "determine_liability":
                liability_result = s.result_data
            elif s.step == "trigger_insurance":
                if s.result_data and "claim_number" in s.result_data:
                    insurance_claim_number = s.result_data["claim_number"]
                else:
                    insurance_claim_number = s.message
            elif s.step == "notify_police":
                police_notified_at = s.executed_at
            elif s.step == "notify_rescue":
                rescue_notified_at = s.executed_at

    all_succeeded = all(s.success for s in steps)

    await db.refresh(accident)

    return AccidentOneClickResponse(
        accident_id=accident.id,
        report_number=accident.report_number,
        analysis_summary=analysis_summary,
        liability_result=liability_result,
        insurance_claim_number=insurance_claim_number,
        police_notified_at=police_notified_at,
        rescue_notified_at=rescue_notified_at,
        steps=steps,
        all_succeeded=all_succeeded,
        blocked_at_step=accident.blocked_at_step
    )


@router.get("", response_model=List[AccidentReportResponse])
async def list_accidents(
    company_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(AccidentReport).order_by(desc(AccidentReport.accident_time))
    conditions = []
    if company_id:
        conditions.append(AccidentReport.company_id == company_id)
    if vehicle_id:
        conditions.append(AccidentReport.vehicle_id == vehicle_id)
    if status:
        conditions.append(AccidentReport.status == status)
    if severity:
        conditions.append(AccidentReport.severity == severity)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    accidents = result.scalars().all()
    return list(accidents)


@router.get("/{accident_id}", response_model=AccidentReportResponse)
async def get_accident(accident_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AccidentReport).where(AccidentReport.id == accident_id)
    )
    accident = result.scalar_one_or_none()
    if not accident:
        raise HTTPException(status_code=404, detail="事故报告不存在")
    return accident


@router.put("/{accident_id}", response_model=AccidentReportResponse)
async def update_accident(
    accident_id: int,
    accident_in: AccidentReportUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AccidentReport).where(AccidentReport.id == accident_id)
    )
    accident = result.scalar_one_or_none()
    if not accident:
        raise HTTPException(status_code=404, detail="事故报告不存在")

    update_data = accident_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(accident, key, value)
    accident.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(accident)
    return accident


@router.delete("/{accident_id}", status_code=204)
async def delete_accident(accident_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AccidentReport).where(AccidentReport.id == accident_id)
    )
    accident = result.scalar_one_or_none()
    if not accident:
        raise HTTPException(status_code=404, detail="事故报告不存在")
    await db.delete(accident)
    await db.commit()
    return None


@router.post("/generate-report", response_model=AccidentAnalysisReport)
async def generate_accident_report(
    params: AccidentGenerateReport,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TestVehicle).where(TestVehicle.id == params.vehicle_id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")

    accident_time = params.accident_time or datetime.utcnow()
    window_start = accident_time - timedelta(minutes=params.window_minutes)
    window_end = accident_time + timedelta(minutes=params.window_minutes)

    log_result = await db.execute(
        select(VehicleRealtimeData)
        .where(
            and_(
                VehicleRealtimeData.vehicle_id == params.vehicle_id,
                VehicleRealtimeData.timestamp >= window_start,
                VehicleRealtimeData.timestamp <= window_end,
            )
        )
        .order_by(VehicleRealtimeData.timestamp)
    )
    vehicle_logs = log_result.scalars().all()

    latitude = vehicle.current_latitude
    longitude = vehicle.current_longitude
    if vehicle_logs:
        last_log = vehicle_logs[-1]
        latitude = last_log.latitude
        longitude = last_log.longitude

    device_result = await db.execute(
        select(RoadsideDevice).where(RoadsideDevice.status == "online")
    )
    devices = device_result.scalars().all()
    nearby_devices = []
    for dev in devices:
        if dev.latitude and dev.longitude and latitude and longitude:
            distance = ((dev.latitude - latitude) ** 2 + (dev.longitude - longitude) ** 2) ** 0.5
            if distance < 0.01:
                nearby_devices.append(dev)

    log_data_list = [log.to_dict() for log in vehicle_logs]
    device_data_list = [dev.to_dict() for dev in nearby_devices]

    log_analysis = {
        "total_log_points": len(log_data_list),
        "time_range": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat()
        },
        "max_speed": max([l.get("speed", 0) or 0 for l in log_data_list]) if log_data_list else 0,
        "avg_speed": sum([l.get("speed", 0) or 0 for l in log_data_list]) / len(log_data_list) if log_data_list else 0,
        "autopilot_engaged": any([l.get("autopilot_enabled", False) for l in log_data_list]),
        "abnormal_events": _detect_abnormal_events(log_data_list)
    }

    sensor_analysis = {
        "nearby_devices_count": len(nearby_devices),
        "devices": [
            {
                "device_code": d.get("device_code"),
                "device_type": d.get("device_type"),
                "device_name": d.get("device_name"),
                "status": d.get("status")
            }
            for d in device_data_list
        ]
    }

    report_number = generate_report_number()
    timeline = _reconstruct_timeline(log_data_list, accident_time)
    liability = _determine_liability(log_analysis, sensor_analysis, vehicle_logs, params.vehicle_id, report_number)

    return AccidentAnalysisReport(
        report_number=report_number,
        accident_summary={
            "vehicle_id": params.vehicle_id,
            "license_plate": vehicle.license_plate,
            "accident_time": accident_time.isoformat(),
            "location": f"{latitude}, {longitude}" if latitude and longitude else "未知",
            "severity": _assess_severity(log_analysis)
        },
        vehicle_log_analysis=log_analysis,
        roadside_sensor_analysis=sensor_analysis,
        timeline_reconstruction=timeline,
        liability_determination=liability,
        recommended_actions=_generate_recommendations(liability, log_analysis),
        generated_at=datetime.utcnow()
    )


@router.post("/{accident_id}/determine-liability", response_model=ResponsibilityDetermination)
async def determine_accident_liability(
    accident_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AccidentReport).where(AccidentReport.id == accident_id)
    )
    accident = result.scalar_one_or_none()
    if not accident:
        raise HTTPException(status_code=404, detail="事故报告不存在")

    log_data_list = accident.vehicle_log_data or []
    sensor_data = accident.roadside_sensor_data or {}
    log_analysis = {
        "data": log_data_list,
        "abnormal_events": _detect_abnormal_events(log_data_list)
    }
    sensor_analysis = {"data": sensor_data}

    liability = _determine_liability(log_analysis, sensor_analysis, [], accident.id, accident.report_number)

    accident.responsibility_determination = {
        "responsible_parties": [p.model_dump() if hasattr(p, 'model_dump') else p for p in liability.responsible_parties],
        "responsibility_distribution": liability.responsibility_distribution,
        "determination_basis": liability.determination_basis
    }
    primary_party = liability.responsible_parties[0].get("party") if liability.responsible_parties else None
    accident.responsible_party = primary_party
    await db.commit()
    await db.refresh(accident)

    return liability


@router.post("/{accident_id}/trigger-insurance", response_model=InsuranceClaimProcess)
async def trigger_insurance_claim(
    accident_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AccidentReport).where(AccidentReport.id == accident_id)
    )
    accident = result.scalar_one_or_none()
    if not accident:
        raise HTTPException(status_code=404, detail="事故报告不存在")

    claim_number = f"INS-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    estimated_amount = _estimate_insurance_amount(accident)

    accident.insurance_claim_number = claim_number
    accident.insurance_status = "submitted"
    await db.commit()
    await db.refresh(accident)

    return InsuranceClaimProcess(
        accident_id=accident_id,
        claim_number=claim_number,
        current_stage="submitted",
        stage_history=[{"stage": "submitted", "timestamp": datetime.utcnow().isoformat()}],
        estimated_amount=estimated_amount
    )


@router.post("/{accident_id}/notify-police", response_model=NotificationResult)
async def notify_police(
    accident_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AccidentReport).where(AccidentReport.id == accident_id)
    )
    accident = result.scalar_one_or_none()
    if not accident:
        raise HTTPException(status_code=404, detail="事故报告不存在")

    if accident.police_notified:
        return NotificationResult(
            notified=True,
            notified_at=accident.police_notified_at,
            message="交警已通知"
        )

    accident.police_notified = True
    accident.police_notified_at = datetime.utcnow()
    await db.commit()
    await db.refresh(accident)

    return NotificationResult(
        notified=True,
        notified_at=accident.police_notified_at,
        message=f"已通知交警处理事故编号 {accident.report_number}"
    )


@router.post("/{accident_id}/notify-rescue", response_model=NotificationResult)
async def notify_rescue(
    accident_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AccidentReport).where(AccidentReport.id == accident_id)
    )
    accident = result.scalar_one_or_none()
    if not accident:
        raise HTTPException(status_code=404, detail="事故报告不存在")

    if accident.rescue_notified:
        return NotificationResult(
            notified=True,
            notified_at=accident.rescue_notified_at,
            message="救援已通知"
        )

    accident.rescue_notified = True
    accident.rescue_notified_at = datetime.utcnow()
    await db.commit()
    await db.refresh(accident)

    return NotificationResult(
        notified=True,
        notified_at=accident.rescue_notified_at,
        message=f"已通知救援前往事故地点 {accident.location}"
    )


def _detect_abnormal_events(log_data_list: list) -> list:
    events = []
    for log in log_data_list:
        speed = log.get("speed", 0) or 0
        acceleration = log.get("acceleration", 0) or 0
        brake = log.get("brake_status", False)
        lane_departure = log.get("lane_departure", False)
        obstacle = log.get("obstacle_detected", False)

        if speed > 120:
            events.append({"type": "speeding", "speed": speed, "timestamp": log.get("timestamp")})
        if abs(acceleration) > 8:
            events.append({"type": "sudden_acceleration", "value": acceleration, "timestamp": log.get("timestamp")})
        if brake and acceleration < -5:
            events.append({"type": "emergency_brake", "timestamp": log.get("timestamp")})
        if lane_departure:
            events.append({"type": "lane_departure", "timestamp": log.get("timestamp")})
        if obstacle and (log.get("obstacle_distance", 100) or 100) < 3:
            events.append({"type": "close_obstacle", "distance": log.get("obstacle_distance"), "timestamp": log.get("timestamp")})
    return events


def _reconstruct_timeline(log_data_list: list, accident_time: datetime) -> list:
    timeline = []
    for log in sorted(log_data_list, key=lambda x: x.get("timestamp", "")):
        ts = log.get("timestamp")
        timeline.append({
            "timestamp": ts,
            "event": "车辆运行数据点",
            "speed": log.get("speed"),
            "autopilot": log.get("autopilot_enabled"),
            "details": {
                "latitude": log.get("latitude"),
                "longitude": log.get("longitude"),
                "brake": log.get("brake_status"),
                "obstacle": log.get("obstacle_detected")
            }
        })
    timeline.append({
        "timestamp": accident_time.isoformat(),
        "event": "事故发生时刻",
        "details": {}
    })
    return timeline


def _determine_liability(log_analysis: dict, sensor_analysis: dict, vehicle_logs, accident_id: int = 0, report_number: str = "") -> ResponsibilityDetermination:
    events = log_analysis.get("abnormal_events", [])
    autopilot = log_analysis.get("autopilot_engaged", False)

    evidence = []
    responsibility_ratio = {}

    if autopilot:
        evidence.append("事故发生时自动驾驶系统处于启用状态")
        responsibility_ratio["自动驾驶系统"] = 60.0
        responsibility_ratio["安全员/驾驶员"] = 40.0
        responsible_party = "自动驾驶系统"
    else:
        evidence.append("事故发生时为人工驾驶模式")
        responsibility_ratio["驾驶员"] = 80.0
        responsibility_ratio["其他方"] = 20.0
        responsible_party = "驾驶员"

    speeding_events = [e for e in events if e["type"] == "speeding"]
    if speeding_events:
        evidence.append(f"检测到超速行为，最高速度 {max(e['speed'] for e in speeding_events)} km/h")

    brake_events = [e for e in events if e["type"] == "emergency_brake"]
    if brake_events:
        evidence.append(f"检测到紧急制动操作，共 {len(brake_events)} 次")

    responsible_parties = [{"party": k, "ratio": v} for k, v in responsibility_ratio.items()]
    basis = "基于车辆日志数据、路侧传感器数据分析及自动驾驶模式判定结果"

    return ResponsibilityDetermination(
        accident_id=accident_id,
        report_number=report_number,
        responsible_parties=responsible_parties,
        responsibility_distribution=responsibility_ratio,
        determination_basis=basis,
        determination_date=datetime.utcnow(),
        determined_by="系统自动判定"
    )


def _assess_severity(log_analysis: dict) -> str:
    events = log_analysis.get("abnormal_events", [])
    if len(events) >= 5 or log_analysis.get("max_speed", 0) > 100:
        return "severe"
    elif len(events) >= 2:
        return "moderate"
    return "minor"


def _generate_recommendations(liability: ResponsibilityDetermination, log_analysis: dict) -> list:
    recommendations = [
        "保留所有相关证据文件和日志数据",
        "配合交警部门进行事故调查",
        "及时通知保险公司进行定损理赔"
    ]
    if any("自动驾驶系统" in str(p.get("party", "")) for p in liability.responsible_parties):
        recommendations.append("对自动驾驶算法进行回滚分析和缺陷排查")
    if any(e["type"] == "speeding" for e in log_analysis.get("abnormal_events", [])):
        recommendations.append("加强车辆速度管控，优化限速策略")
    return recommendations


def _estimate_insurance_amount(accident: AccidentReport) -> float:
    base_amount = 5000.0
    if accident.severity == "moderate":
        base_amount = 20000.0
    elif accident.severity == "severe":
        base_amount = 100000.0
    if accident.injuries:
        base_amount += 50000.0
    return base_amount


@router.get("/{accident_id}/disposal", response_model=AccidentDisposalDetailResponse)
async def get_accident_disposal_detail(
    accident_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AccidentReport).where(AccidentReport.id == accident_id)
    )
    accident = result.scalar_one_or_none()
    if not accident:
        raise HTTPException(status_code=404, detail="事故报告不存在")

    result = await db.execute(
        select(AccidentDisposalStep)
        .where(AccidentDisposalStep.accident_id == accident_id)
        .order_by(AccidentDisposalStep.started_at, AccidentDisposalStep.attempt_number)
    )
    all_steps = result.scalars().all()

    all_steps = sorted(all_steps, key=lambda s: (
        s.started_at or datetime.min,
        STEP_ORDER.get(s.step_name, 99),
        s.attempt_number
    ))

    latest_status = {}
    for step in all_steps:
        if step.step_name not in latest_status or step.attempt_number > latest_status[step.step_name].attempt_number:
            latest_status[step.step_name] = step

    failed_step = None
    all_succeeded = True
    for step_name in VALID_STEPS:
        if step_name not in latest_status:
            all_succeeded = False
            failed_step = step_name
            break
        if latest_status[step_name].status != "success":
            all_succeeded = False
            if failed_step is None:
                failed_step = step_name

    total_attempts = sum(1 for s in all_steps)

    if all_succeeded:
        overall_status = "completed"
    elif failed_step:
        overall_status = f"failed_at_{failed_step}"
    else:
        overall_status = "in_progress"

    step_histories = []
    for step in all_steps:
        step_histories.append(DisposalStepHistory(
            id=step.id,
            step_name=step.step_name,
            attempt_number=step.attempt_number,
            status=step.status,
            message=step.message,
            error=step.error,
            result_data=step.result_data,
            started_at=step.started_at,
            completed_at=step.completed_at,
            duration_seconds=step.to_dict().get("duration_seconds")
        ))

    return AccidentDisposalDetailResponse(
        accident_id=accident.id,
        report_number=accident.report_number,
        overall_status=overall_status,
        all_succeeded=all_succeeded,
        failed_step=failed_step,
        blocked_at_step=accident.blocked_at_step,
        total_attempts=total_attempts,
        timeline=step_histories
    )


@router.post("/{accident_id}/retry/{step_name}", response_model=StepRetryResponse)
async def retry_disposal_step(
    accident_id: int,
    step_name: str,
    db: AsyncSession = Depends(get_db)
):
    from app.schemas.accident import SubsequentStepExecution

    if step_name not in VALID_STEPS:
        raise HTTPException(
            status_code=400,
            detail=f"无效的步骤名称，必须是: {', '.join(VALID_STEPS)}"
        )

    if step_name == "create_accident":
        raise HTTPException(
            status_code=400,
            detail="创建事故报告步骤不可重试，请重新提交新事故"
        )

    result = await db.execute(
        select(AccidentReport).where(AccidentReport.id == accident_id)
    )
    accident = result.scalar_one_or_none()
    if not accident:
        raise HTTPException(status_code=404, detail="事故报告不存在")

    result = await db.execute(
        select(TestVehicle).where(TestVehicle.id == accident.vehicle_id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="关联车辆不存在")

    before_steps_result = await db.execute(
        select(AccidentDisposalStep.attempt_number).where(
            and_(
                AccidentDisposalStep.accident_id == accident_id,
                AccidentDisposalStep.step_name == step_name
            )
        ).order_by(desc(AccidentDisposalStep.attempt_number))
    )
    attempt_before = before_steps_result.scalar() or 0

    step_executions = await run_disposal_from_step(
        db, accident, step_name, vehicle
    )

    retry_step_result = None
    for s in step_executions:
        if s.step == step_name:
            retry_step_result = s
            break

    if not retry_step_result:
        raise HTTPException(status_code=500, detail="重试失败，未找到步骤结果")

    after_steps_result = await db.execute(
        select(AccidentDisposalStep).where(
            and_(
                AccidentDisposalStep.accident_id == accident_id,
                AccidentDisposalStep.attempt_number > attempt_before
            )
        ).order_by(
            AccidentDisposalStep.started_at,
            AccidentDisposalStep.step_name
        )
    )
    new_steps_from_db = after_steps_result.scalars().all()

    retry_step_db = None
    subsequent_steps_db = []
    for step_db in new_steps_from_db:
        if step_db.step_name == step_name and retry_step_db is None:
            retry_step_db = step_db
        else:
            subsequent_steps_db.append(step_db)

    if not retry_step_db:
        retry_step_db_result = await db.execute(
            select(AccidentDisposalStep).where(
                and_(
                    AccidentDisposalStep.accident_id == accident_id,
                    AccidentDisposalStep.step_name == step_name
                )
            ).order_by(desc(AccidentDisposalStep.attempt_number))
        )
        retry_step_db = retry_step_db_result.scalars().first()

    retry_started_at = retry_step_db.started_at if retry_step_db else retry_step_result.executed_at
    retry_completed_at = retry_step_db.completed_at if retry_step_db else retry_step_result.executed_at
    retry_result_data = retry_step_db.result_data if retry_step_db else None

    subsequent_executions = []
    if subsequent_steps_db:
        for step_db in subsequent_steps_db:
            subsequent_executions.append(SubsequentStepExecution(
                step_name=step_db.step_name,
                success=step_db.status == "success",
                status=step_db.status,
                message=step_db.message or "",
                error=step_db.error,
                started_at=step_db.started_at,
                completed_at=step_db.completed_at,
                result_data=step_db.result_data
            ))
    else:
        for s in step_executions:
            if s.step != step_name:
                step_db_result = await db.execute(
                    select(AccidentDisposalStep).where(
                        and_(
                            AccidentDisposalStep.accident_id == accident_id,
                            AccidentDisposalStep.step_name == s.step,
                            AccidentDisposalStep.attempt_number > attempt_before
                        )
                    ).order_by(desc(AccidentDisposalStep.attempt_number))
                )
                step_db_obj = step_db_result.scalars().first()
                subsequent_executions.append(SubsequentStepExecution(
                    step_name=s.step,
                    success=s.success,
                    status="success" if s.success else "failed",
                    message=s.message,
                    error=s.error,
                    started_at=step_db_obj.started_at if step_db_obj else s.executed_at,
                    completed_at=step_db_obj.completed_at if step_db_obj else s.executed_at,
                    result_data=step_db_obj.result_data if step_db_obj else None
                ))

    attempt_number = (retry_step_db.attempt_number if retry_step_db else attempt_before + 1)

    all_succeeded = retry_step_result.success and all(s.success for s in subsequent_executions)

    return StepRetryResponse(
        accident_id=accident.id,
        step_name=step_name,
        attempt_number=attempt_number,
        status="success" if retry_step_result.success else "failed",
        success=retry_step_result.success,
        message=retry_step_result.message,
        error=retry_step_result.error,
        result_data=retry_result_data,
        started_at=retry_started_at,
        completed_at=retry_completed_at,
        subsequent_executed=subsequent_executions,
        new_blocked_at_step=accident.blocked_at_step,
        all_succeeded=all_succeeded
    )
