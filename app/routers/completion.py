from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

from app.database import get_db
from app.models import (
    TestCompletion, TestVehicle, VehicleRealtimeData, Alarm, AccidentReport
)
from app.schemas.completion import (
    TestCompletionCreate, TestCompletionResponse, TestCompletionUpdate,
    MileageStatistics, SceneCoverageStatistics, DisengagementStatistics,
    MilestoneStats, CompletionGenerateReport, CompletionReviewReport
)

router = APIRouter(tags=["测试结题管理"])


def generate_report_number() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"TC-{timestamp}"


@router.post("", response_model=TestCompletionResponse, status_code=201)
async def create_completion(
    completion_in: TestCompletionCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TestVehicle).where(TestVehicle.id == completion_in.vehicle_id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")

    report_number = generate_report_number()
    completion = TestCompletion(
        company_id=vehicle.company_id,
        vehicle_id=completion_in.vehicle_id,
        report_number=report_number,
        title=completion_in.title,
        test_period_start=completion_in.test_period_start,
        test_period_end=completion_in.test_period_end,
        test_type=completion_in.test_type,
        test_area=completion_in.test_area,
        test_objectives=completion_in.test_objectives,
        test_scope=completion_in.test_scope,
        test_methodology=completion_in.test_methodology,
        test_results=completion_in.test_results,
        issues_encountered=completion_in.issues_encountered,
        improvements_made=completion_in.improvements_made,
        conclusions=completion_in.conclusions,
        recommendations=completion_in.recommendations,
    )
    db.add(completion)
    await db.commit()
    await db.refresh(completion)
    return completion


@router.get("", response_model=List[TestCompletionResponse])
async def list_completions(
    company_id: Optional[int] = None,
    vehicle_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TestCompletion).order_by(desc(TestCompletion.created_at))
    conditions = []
    if company_id:
        conditions.append(TestCompletion.company_id == company_id)
    if vehicle_id:
        conditions.append(TestCompletion.vehicle_id == vehicle_id)
    if status:
        conditions.append(TestCompletion.status == status)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    completions = result.scalars().all()
    return list(completions)


@router.get("/{completion_id}", response_model=TestCompletionResponse)
async def get_completion(completion_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TestCompletion).where(TestCompletion.id == completion_id)
    )
    completion = result.scalar_one_or_none()
    if not completion:
        raise HTTPException(status_code=404, detail="结题报告不存在")
    return completion


@router.put("/{completion_id}", response_model=TestCompletionResponse)
async def update_completion(
    completion_id: int,
    completion_in: TestCompletionUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TestCompletion).where(TestCompletion.id == completion_id)
    )
    completion = result.scalar_one_or_none()
    if not completion:
        raise HTTPException(status_code=404, detail="结题报告不存在")

    update_data = completion_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(completion, key, value)
    completion.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(completion)
    return completion


@router.delete("/{completion_id}", status_code=204)
async def delete_completion(completion_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TestCompletion).where(TestCompletion.id == completion_id)
    )
    completion = result.scalar_one_or_none()
    if not completion:
        raise HTTPException(status_code=404, detail="结题报告不存在")
    await db.delete(completion)
    await db.commit()
    return None


@router.get("/vehicle/{vehicle_id}/stats", response_model=MilestoneStats)
async def get_vehicle_milestone_stats(
    vehicle_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TestVehicle).where(TestVehicle.id == vehicle_id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")

    if not start_date:
        start_date = vehicle.created_at.date() if vehicle.created_at else date.today() - timedelta(days=365)
    if not end_date:
        end_date = date.today()

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    log_result = await db.execute(
        select(VehicleRealtimeData)
        .where(
            and_(
                VehicleRealtimeData.vehicle_id == vehicle_id,
                VehicleRealtimeData.timestamp >= start_dt,
                VehicleRealtimeData.timestamp <= end_dt,
            )
        )
        .order_by(VehicleRealtimeData.timestamp)
    )
    logs = log_result.scalars().all()

    log_list = [log.to_dict() for log in logs]

    total_distance, autopilot_distance, manual_distance = _calculate_mileage(log_list)
    total_duration = _calculate_duration(log_list)
    avg_speed, max_speed = _calculate_speeds(log_list)
    disengagement_count = _count_disengagements(log_list, vehicle.disengagement_count)
    scene_coverage_rate, scene_details = _calculate_scene_coverage(vehicle, log_list)
    total_alarms, critical_alarms = await _count_alarms(vehicle_id, start_dt, end_dt, db)
    safety_incidents = await _count_safety_incidents(vehicle_id, start_dt, end_dt, db)
    system_reliability = _calculate_reliability(disengagement_count, total_distance)

    return MilestoneStats(
        total_test_distance=total_distance,
        autopilot_distance=autopilot_distance,
        manual_distance=manual_distance,
        total_test_duration=total_duration,
        average_speed=avg_speed,
        max_speed=max_speed,
        disengagement_count=disengagement_count,
        scene_coverage_rate=scene_coverage_rate,
        scene_details=scene_details,
        total_alarms=total_alarms,
        critical_alarms=critical_alarms,
        safety_incidents=safety_incidents,
        system_reliability=system_reliability
    )


@router.post("/generate-report", response_model=TestCompletionResponse)
async def generate_completion_report(
    params: CompletionGenerateReport,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TestVehicle).where(TestVehicle.id == params.vehicle_id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")

    if not params.test_period_start:
        params.test_period_start = vehicle.created_at.date() if vehicle.created_at else date.today() - timedelta(days=365)
    if not params.test_period_end:
        params.test_period_end = date.today()
    if not params.title:
        params.title = f"{vehicle.license_plate} 测试结题报告"

    stats = await get_vehicle_milestone_stats(
        vehicle_id=params.vehicle_id,
        start_date=params.test_period_start,
        end_date=params.test_period_end,
        db=db
    )

    report_number = generate_report_number()
    completion = TestCompletion(
        company_id=vehicle.company_id,
        vehicle_id=params.vehicle_id,
        report_number=report_number,
        title=params.title,
        test_period_start=params.test_period_start,
        test_period_end=params.test_period_end,
        test_type=vehicle.test_type,
        test_area=vehicle.test_area,
        total_test_distance=stats.total_test_distance,
        total_test_duration=stats.total_test_duration,
        autopilot_distance=stats.autopilot_distance,
        manual_distance=stats.manual_distance,
        average_speed=stats.average_speed,
        max_speed=stats.max_speed,
        total_alarms=stats.total_alarms,
        critical_alarms=stats.critical_alarms,
        safety_incidents=stats.safety_incidents,
        disengagement_count=stats.disengagement_count,
        scene_coverage_rate=stats.scene_coverage_rate,
        scene_details=stats.scene_details,
        system_reliability=stats.system_reliability,
        test_objectives=f"完成{vehicle.test_type or '自动驾驶'}测试，验证系统安全性和可靠性",
        test_scope=f"测试区域：{vehicle.test_area or '指定测试区域'}，测试周期：{params.test_period_start} 至 {params.test_period_end}",
        test_methodology="基于车辆实时运行数据、场景覆盖数据及告警记录进行综合评估",
        test_results=_generate_test_results_text(stats),
        issues_encountered=_generate_issues_text(stats),
        improvements_made="根据测试中发现的问题，持续优化自动驾驶算法和安全策略",
        conclusions=_generate_conclusions_text(stats),
        recommendations=_generate_recommendations_text(stats),
        status="draft",
    )
    db.add(completion)
    await db.commit()
    await db.refresh(completion)
    return completion


@router.get("/{completion_id}/review-report", response_model=CompletionReviewReport)
async def get_completion_review_report(
    completion_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TestCompletion).where(TestCompletion.id == completion_id)
    )
    completion = result.scalar_one_or_none()
    if not completion:
        raise HTTPException(status_code=404, detail="结题报告不存在")

    mileage_summary = {
        "total_test_distance_km": completion.total_test_distance or 0,
        "autopilot_distance_km": completion.autopilot_distance or 0,
        "manual_distance_km": completion.manual_distance or 0,
        "autopilot_ratio": (
            round((completion.autopilot_distance or 0) / (completion.total_test_distance or 1) * 100, 2)
            if completion.total_test_distance and completion.total_test_distance > 0 else 0
        ),
        "total_duration_hours": round((completion.total_test_duration or 0) / 3600, 2),
        "average_speed_kmh": round(completion.average_speed or 0, 2),
        "max_speed_kmh": round(completion.max_speed or 0, 2)
    }

    scene_coverage = {
        "coverage_rate": round((completion.scene_coverage_rate or 0) * 100, 2),
        "details": completion.scene_details or {}
    }

    disengagement_analysis = {
        "total_count": completion.disengagement_count or 0,
        "per_100km": (
            round((completion.disengagement_count or 0) / (completion.total_test_distance or 1) * 100, 4)
            if completion.total_test_distance and completion.total_test_distance > 0 else 0
        )
    }

    alarm_statistics = {
        "total": completion.total_alarms or 0,
        "critical": completion.critical_alarms or 0,
        "critical_ratio": (
            round((completion.critical_alarms or 0) / (completion.total_alarms or 1) * 100, 2)
            if completion.total_alarms and completion.total_alarms > 0 else 0
        )
    }

    safety_assessment = {
        "safety_incidents": completion.safety_incidents or 0,
        "incident_per_1000km": (
            round((completion.safety_incidents or 0) / (completion.total_test_distance or 1) * 1000, 4)
            if completion.total_test_distance and completion.total_test_distance > 0 else 0
        )
    }

    review_status = completion.status
    if completion.status == "draft":
        review_status = "待提交"
    elif completion.status == "submitted":
        review_status = "待评审"
    elif completion.status == "reviewed":
        review_status = "已评审"
    elif completion.status == "approved":
        review_status = "已通过"
    elif completion.status == "rejected":
        review_status = "已驳回"

    return CompletionReviewReport(
        report_number=completion.report_number,
        title=completion.title,
        test_period={
            "start": completion.test_period_start.isoformat() if completion.test_period_start else None,
            "end": completion.test_period_end.isoformat() if completion.test_period_end else None
        },
        mileage_summary=mileage_summary,
        scene_coverage=scene_coverage,
        disengagement_analysis=disengagement_analysis,
        alarm_statistics=alarm_statistics,
        safety_assessment=safety_assessment,
        system_reliability=round(completion.system_reliability or 0, 4),
        conclusions=completion.conclusions or "",
        recommendations=_parse_recommendations(completion.recommendations),
        review_status=review_status,
        generated_at=datetime.utcnow()
    )


@router.post("/{completion_id}/submit", response_model=TestCompletionResponse)
async def submit_completion_report(
    completion_id: int,
    submitted_by: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TestCompletion).where(TestCompletion.id == completion_id)
    )
    completion = result.scalar_one_or_none()
    if not completion:
        raise HTTPException(status_code=404, detail="结题报告不存在")

    completion.status = "submitted"
    completion.submitted_by = submitted_by
    completion.submitted_at = datetime.utcnow()
    completion.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(completion)
    return completion


@router.post("/{completion_id}/review", response_model=TestCompletionResponse)
async def review_completion_report(
    completion_id: int,
    reviewed_by: str,
    review_comments: Optional[str] = None,
    approve: bool = False,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TestCompletion).where(TestCompletion.id == completion_id)
    )
    completion = result.scalar_one_or_none()
    if not completion:
        raise HTTPException(status_code=404, detail="结题报告不存在")

    completion.reviewed_by = reviewed_by
    completion.reviewed_at = datetime.utcnow()
    completion.review_comments = review_comments
    completion.updated_at = datetime.utcnow()

    if approve:
        completion.status = "approved"
        completion.approved_by = reviewed_by
        completion.approved_at = datetime.utcnow()
    else:
        completion.status = "reviewed"

    await db.commit()
    await db.refresh(completion)
    return completion


def _calculate_mileage(log_list: List[Dict[str, Any]]) -> tuple:
    total_distance = 0.0
    autopilot_distance = 0.0
    manual_distance = 0.0

    if len(log_list) < 2:
        return total_distance, autopilot_distance, manual_distance

    for i in range(1, len(log_list)):
        prev = log_list[i - 1]
        curr = log_list[i]

        lat1, lon1 = prev.get("latitude"), prev.get("longitude")
        lat2, lon2 = curr.get("latitude"), curr.get("longitude")

        if lat1 and lon1 and lat2 and lon2:
            segment = _haversine_distance(lat1, lon1, lat2, lon2)
            total_distance += segment

            if curr.get("autopilot_enabled"):
                autopilot_distance += segment
            else:
                manual_distance += segment

    return round(total_distance, 4), round(autopilot_distance, 4), round(manual_distance, 4)


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _calculate_duration(log_list: List[Dict[str, Any]]) -> float:
    if len(log_list) < 2:
        return 0.0
    start_ts = log_list[0].get("timestamp")
    end_ts = log_list[-1].get("timestamp")
    if start_ts and end_ts:
        if isinstance(start_ts, str):
            start_ts = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
        if isinstance(end_ts, str):
            end_ts = datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
        return (end_ts - start_ts).total_seconds()
    return 0.0


def _calculate_speeds(log_list: List[Dict[str, Any]]) -> tuple:
    speeds = [log.get("speed", 0) or 0 for log in log_list]
    if not speeds:
        return 0.0, 0.0
    avg_speed = sum(speeds) / len(speeds)
    max_speed = max(speeds)
    return round(avg_speed, 2), round(max_speed, 2)


def _count_disengagements(log_list: List[Dict[str, Any]], vehicle_count: int) -> int:
    count = 0
    autopilot_prev = False
    for log in log_list:
        current = log.get("autopilot_enabled", False)
        if autopilot_prev and not current:
            count += 1
        autopilot_prev = current
    return max(count, vehicle_count or 0)


def _calculate_scene_coverage(vehicle: TestVehicle, log_list: List[Dict[str, Any]]) -> tuple:
    default_scenes = {
        "城市道路": False,
        "高速公路": False,
        "乡村道路": False,
        "停车场": False,
        "隧道": False,
        "桥梁": False,
        "夜间行驶": False,
        "雨天行驶": False,
        "拥堵路段": False,
        "变道超车": False,
        "红绿灯路口": False,
        "无保护左转": False,
        "环岛通行": False,
        "行人避让": False,
        "非机动车避让": False
    }

    scene_config = vehicle.scene_coverage or {}
    scene_details = {**default_scenes, **scene_config}

    total_scenes = len(scene_details)
    covered_scenes = sum(1 for v in scene_details.values() if v)
    coverage_rate = covered_scenes / total_scenes if total_scenes > 0 else 0.0

    return round(coverage_rate, 4), scene_details


async def _count_alarms(vehicle_id: int, start_dt: datetime, end_dt: datetime, db: AsyncSession) -> tuple:
    stmt = select(Alarm).where(
        and_(
            Alarm.vehicle_id == vehicle_id,
            Alarm.timestamp >= start_dt,
            Alarm.timestamp <= end_dt,
        )
    )
    result = await db.execute(stmt)
    alarms = result.scalars().all()
    total = len(alarms)
    critical = sum(1 for a in alarms if a.alarm_level == "critical")
    return total, critical


async def _count_safety_incidents(vehicle_id: int, start_dt: datetime, end_dt: datetime, db: AsyncSession) -> int:
    stmt = select(AccidentReport).where(
        and_(
            AccidentReport.vehicle_id == vehicle_id,
            AccidentReport.accident_time >= start_dt,
            AccidentReport.accident_time <= end_dt,
        )
    )
    result = await db.execute(stmt)
    return len(result.scalars().all())


def _calculate_reliability(disengagement_count: int, total_distance: float) -> float:
    if total_distance <= 0:
        return 0.0
    mtbf = total_distance / max(disengagement_count, 1)
    if mtbf >= 1000:
        return 0.999
    elif mtbf >= 500:
        return 0.99
    elif mtbf >= 100:
        return 0.95
    elif mtbf >= 50:
        return 0.85
    else:
        return 0.7


def _generate_test_results_text(stats: MilestoneStats) -> str:
    return (
        f"测试总里程：{stats.total_test_distance:.2f} 公里，其中自动驾驶里程 {stats.autopilot_distance:.2f} 公里，"
        f"人工驾驶里程 {stats.manual_distance:.2f} 公里。平均速度 {stats.average_speed:.2f} km/h，"
        f"最高速度 {stats.max_speed:.2f} km/h。脱管次数共 {stats.disengagement_count} 次，"
        f"场景覆盖率 {stats.scene_coverage_rate * 100:.2f}%。期间发生告警 {stats.total_alarms} 次，"
        f"其中严重告警 {stats.critical_alarms} 次，安全事件 {stats.safety_incidents} 次。"
        f"系统可靠度评估为 {stats.system_reliability * 100:.2f}%。"
    )


def _generate_issues_text(stats: MilestoneStats) -> str:
    issues = []
    if stats.disengagement_count > 10:
        issues.append(f"脱管次数偏高（{stats.disengagement_count}次），需分析脱管原因并优化算法")
    if stats.scene_coverage_rate < 0.7:
        issues.append(f"场景覆盖率较低（{stats.scene_coverage_rate * 100:.2f}%），建议补充测试场景")
    if stats.critical_alarms > 5:
        issues.append(f"严重告警数量较多（{stats.critical_alarms}次），需重点关注相关模块")
    if stats.system_reliability < 0.9:
        issues.append(f"系统可靠度有待提升（当前 {stats.system_reliability * 100:.2f}%）")
    return "；".join(issues) if issues else "测试期间未发现重大问题"


def _generate_conclusions_text(stats: MilestoneStats) -> str:
    if stats.system_reliability >= 0.95 and stats.scene_coverage_rate >= 0.8:
        return (
            f"本次测试总体表现良好，系统可靠度达到 {stats.system_reliability * 100:.2f}%，"
            f"场景覆盖率 {stats.scene_coverage_rate * 100:.2f}%，满足测试结题要求。"
        )
    elif stats.system_reliability >= 0.85:
        return (
            f"本次测试基本达到预期目标，系统可靠度 {stats.system_reliability * 100:.2f}%，"
            f"仍有优化空间，建议在后续测试中持续改进。"
        )
    else:
        return (
            f"本次测试存在较多待改进项，系统可靠度仅 {stats.system_reliability * 100:.2f}%，"
            f"建议进行优化后重新测试。"
        )


def _generate_recommendations_text(stats: MilestoneStats) -> str:
    recs = [
        "持续收集路测数据，优化自动驾驶算法模型",
        "定期开展安全培训，提升安全员应急处置能力",
        "完善数据日志系统，确保关键数据完整可追溯"
    ]
    if stats.disengagement_count > 0:
        recs.append("深入分析每次脱管原因，针对性优化感知和决策模块")
    if stats.scene_coverage_rate < 0.9:
        recs.append("扩展测试场景库，增加复杂场景覆盖度")
    if stats.critical_alarms > 0:
        recs.append("建立严重告警快速响应机制，及时排查潜在风险")
    return "；".join(recs)


def _parse_recommendations(text: Optional[str]) -> List[str]:
    if not text:
        return []
    return [r.strip() for r in text.replace("；", ";").split(";") if r.strip()]
