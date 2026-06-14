import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_db
from app.auth import get_current_user
from app.models import TestRoute, TestVehicle, AccidentReport, User, vehicle_route_association
from app.schemas.route import (
    TestRouteCreate, TestRouteUpdate, TestRouteResponse,
    RouteConflictDetection, RouteRecommendationRequest,
    RouteRecommendation, RouteApplicationResponse, ScheduleConflict
)

router = APIRouter(tags=["测试路线申请"])

TRAFFIC_CONDITIONS = ["smooth", "moderate", "congested", "blocked"]
WEATHER_CONDITIONS = ["clear", "cloudy", "rainy", "snowy", "foggy", "stormy"]
ROAD_LEVELS = ["highway", "urban_primary", "urban_secondary", "rural", "test_track"]


def generate_route_code() -> str:
    return f"RT{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4].upper()}"


def calculate_risk_score(
    traffic_condition: str,
    weather_condition: str,
    accident_count: int,
    road_level: str
) -> float:
    score = 0.0
    traffic_weights = {"smooth": 0.05, "moderate": 0.15, "congested": 0.30, "blocked": 0.50}
    weather_weights = {"clear": 0.05, "cloudy": 0.10, "rainy": 0.25, "snowy": 0.35, "foggy": 0.40, "stormy": 0.50}
    road_weights = {"highway": 0.15, "urban_primary": 0.20, "urban_secondary": 0.25, "rural": 0.30, "test_track": 0.10}

    score += traffic_weights.get(traffic_condition, 0.20)
    score += weather_weights.get(weather_condition, 0.20)
    score += road_weights.get(road_level, 0.20)
    score += min(accident_count * 0.05, 0.30)

    return round(min(score, 1.0), 3)


def recommend_speed_limit(road_level: str, weather_condition: str, traffic_condition: str) -> float:
    base_speeds = {
        "highway": 100.0,
        "urban_primary": 60.0,
        "urban_secondary": 40.0,
        "rural": 50.0,
        "test_track": 80.0
    }
    base = base_speeds.get(road_level, 50.0)

    weather_factors = {"clear": 1.0, "cloudy": 0.95, "rainy": 0.75, "snowy": 0.50, "foggy": 0.60, "stormy": 0.40}
    traffic_factors = {"smooth": 1.0, "moderate": 0.85, "congested": 0.60, "blocked": 0.30}

    limit = base * weather_factors.get(weather_condition, 0.8) * traffic_factors.get(traffic_condition, 0.8)
    return round(limit, 1)


def generate_safety_tips(weather_condition: str, traffic_condition: str, risk_score: float) -> List[str]:
    tips = []
    if weather_condition in ["rainy", "snowy", "stormy"]:
        tips.append("恶劣天气，请注意路面湿滑，保持安全车距")
    if weather_condition == "foggy":
        tips.append("大雾天气，请开启雾灯，降低车速行驶")
    if traffic_condition in ["congested", "blocked"]:
        tips.append("交通拥堵，建议错峰出行或选择替代路线")
    if risk_score > 0.6:
        tips.append("该路线风险较高，请安排经验丰富的安全员随车")
    if risk_score > 0.4:
        tips.append("建议开启全部自动驾驶辅助功能，保持人工监控")
    if not tips:
        tips.append("路况良好，按规范操作即可")
    return tips


async def check_schedule_conflicts(
    db: AsyncSession,
    company_id: int,
    scheduled_start: datetime,
    scheduled_end: datetime,
    exclude_route_id: Optional[int] = None
) -> List[ScheduleConflict]:
    conflicts = []
    query = select(TestRoute).where(
        and_(
            TestRoute.company_id == company_id,
            TestRoute.scheduled_start.isnot(None),
            TestRoute.scheduled_end.isnot(None),
            or_(
                and_(TestRoute.scheduled_start <= scheduled_start, TestRoute.scheduled_end >= scheduled_start),
                and_(TestRoute.scheduled_start <= scheduled_end, TestRoute.scheduled_end >= scheduled_end),
                and_(TestRoute.scheduled_start >= scheduled_start, TestRoute.scheduled_end <= scheduled_end)
            )
        )
    )
    if exclude_route_id:
        query = query.where(TestRoute.id != exclude_route_id)

    result = await db.execute(query)
    existing_routes = result.scalars().all()

    for route in existing_routes:
        gap = timedelta(minutes=30)
        if route.scheduled_end and route.scheduled_end < scheduled_start:
            conflict_type = "时间接近"
            suggested_start = route.scheduled_end + gap
            duration = scheduled_end - scheduled_start
            suggested_end = suggested_start + duration
        elif route.scheduled_start and scheduled_end < route.scheduled_start:
            conflict_type = "时间接近"
            duration = scheduled_end - scheduled_start
            suggested_end = route.scheduled_start - gap
            suggested_start = suggested_end - duration
        else:
            conflict_type = "时间重叠"
            duration = scheduled_end - scheduled_start
            suggested_start = route.scheduled_end + gap
            suggested_end = suggested_start + duration

        conflicts.append(ScheduleConflict(
            conflicting_route_id=route.id,
            conflicting_route_name=route.route_name,
            conflict_type=conflict_type,
            conflicting_start=route.scheduled_start,
            conflicting_end=route.scheduled_end,
            suggested_start=suggested_start,
            suggested_end=suggested_end
        ))

    return conflicts


@router.post("/recommend", response_model=RouteApplicationResponse, status_code=status.HTTP_200_OK)
async def recommend_safe_routes(
    request: RouteRecommendationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company_id = current_user.id
    company = current_user

    start_point = request.start_point
    end_point = request.end_point
    scheduled_start = request.scheduled_start or datetime.utcnow()
    estimated_duration_min = 45
    scheduled_end = scheduled_start + timedelta(minutes=estimated_duration_min)

    conflicts = await check_schedule_conflicts(db, company_id, scheduled_start, scheduled_end)

    accident_query = select(AccidentReport).where(
        and_(
            AccidentReport.company_id == company_id,
            AccidentReport.accident_time >= datetime.utcnow() - timedelta(days=180)
        )
    )
    accident_result = await db.execute(accident_query)
    recent_accidents = accident_result.scalars().all()
    accident_count = len(recent_accidents)

    recommendations = []
    for i in range(3):
        road_level = ROAD_LEVELS[i % len(ROAD_LEVELS)]
        traffic = TRAFFIC_CONDITIONS[i % len(TRAFFIC_CONDITIONS)]
        weather = WEATHER_CONDITIONS[i % len(WEATHER_CONDITIONS)]

        risk_score = calculate_risk_score(traffic, weather, accident_count, road_level)
        speed_limit = recommend_speed_limit(road_level, weather, traffic)

        waypoints = [
            {"index": 0, "name": start_point, "lat": 39.9042 + i * 0.01, "lng": 116.4074 + i * 0.01},
            {"index": 1, "name": f"途经点{i+1}", "lat": 39.9142 + i * 0.01, "lng": 116.4174 + i * 0.01},
            {"index": 2, "name": end_point, "lat": 39.9242 + i * 0.01, "lng": 116.4274 + i * 0.01}
        ]

        risk_factors = []
        if traffic in ["congested", "blocked"]:
            risk_factors.append(f"交通状况：{traffic}")
        if weather in ["rainy", "snowy", "foggy", "stormy"]:
            risk_factors.append(f"天气状况：{weather}")
        if accident_count > 0:
            risk_factors.append(f"近180天历史事故{accident_count}起")
        if risk_score > 0.5:
            risk_factors.append("综合风险较高")

        recommendations.append(RouteRecommendation(
            route_name=f"推荐路线{i+1}-{road_level}",
            start_point=start_point,
            end_point=end_point,
            waypoints=waypoints,
            total_distance=round(15.0 + i * 3.5, 1),
            estimated_duration=estimated_duration_min + i * 15,
            road_level=road_level,
            traffic_condition=traffic,
            weather_condition=weather,
            speed_limit=speed_limit,
            accident_risk_score=risk_score,
            risk_factors=risk_factors,
            safety_tips=generate_safety_tips(weather, traffic, risk_score)
        ))

    recommendations.sort(key=lambda r: r.accident_risk_score)

    overall_risk = min(r.accident_risk_score for r in recommendations) if recommendations else 0.0
    overall_speed = min(r.speed_limit for r in recommendations) if recommendations else 60.0

    response = RouteApplicationResponse(
        status="recommended",
        recommended_routes=recommendations,
        conflicts=conflicts if conflicts else None,
        risk_score=overall_risk,
        suggested_speed_limit=overall_speed,
        suggested_schedule={
            "original_start": scheduled_start.isoformat(),
            "original_end": scheduled_end.isoformat(),
            "adjusted": bool(conflicts) and len(conflicts) > 0
        } if conflicts else None,
        message=f"已生成{len(recommendations)}条路线推荐" + (f"，检测到{len(conflicts)}个时间冲突" if conflicts else "")
    )

    return response


@router.post("/apply", response_model=TestRouteResponse, status_code=status.HTTP_201_CREATED)
async def apply_for_route(
    route_data: TestRouteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company_id = current_user.id
    company = current_user

    existing = await db.execute(select(TestRoute).where(TestRoute.route_code == route_data.route_code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="路线编码已存在")

    if route_data.scheduled_start and route_data.scheduled_end:
        conflicts = await check_schedule_conflicts(db, company_id, route_data.scheduled_start, route_data.scheduled_end)
        if conflicts:
            pass

    accident_query = select(AccidentReport).where(
        and_(
            AccidentReport.company_id == company_id,
            AccidentReport.accident_time >= datetime.utcnow() - timedelta(days=180)
        )
    )
    accident_result = await db.execute(accident_query)
    accident_count = len(accident_result.scalars().all())

    traffic = route_data.traffic_condition or "moderate"
    weather = route_data.weather_condition or "clear"
    road_level = route_data.road_level or "urban_secondary"

    risk_score = route_data.accident_risk_score or calculate_risk_score(traffic, weather, accident_count, road_level)
    speed_limit = route_data.speed_limit or recommend_speed_limit(road_level, weather, traffic)

    new_route = TestRoute(
        company_id=company_id,
        route_name=route_data.route_name,
        route_code=route_data.route_code or generate_route_code(),
        route_type=route_data.route_type,
        test_area=route_data.test_area,
        start_point=route_data.start_point,
        end_point=route_data.end_point,
        waypoints=route_data.waypoints,
        total_distance=route_data.total_distance,
        estimated_duration=route_data.estimated_duration,
        road_level=road_level,
        traffic_condition=traffic,
        weather_condition=weather,
        speed_limit=speed_limit,
        scheduled_start=route_data.scheduled_start,
        scheduled_end=route_data.scheduled_end,
        accident_risk_score=risk_score,
        approval_status="pending",
        description=route_data.description
    )

    if route_data.vehicle_ids:
        vehicles_result = await db.execute(
            select(TestVehicle).where(
                and_(
                    TestVehicle.id.in_(route_data.vehicle_ids),
                    TestVehicle.company_id == company_id
                )
            )
        )
        vehicles = vehicles_result.scalars().all()
        new_route.vehicles = vehicles

    db.add(new_route)
    await db.commit()
    await db.refresh(new_route)

    return new_route


@router.get("", response_model=List[TestRouteResponse])
async def list_routes(
    company_id: int = Query(..., description="公司ID"),
    status_filter: Optional[str] = Query(None, description="审批状态筛选"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    query = select(TestRoute).where(TestRoute.company_id == company_id).options(selectinload(TestRoute.vehicles))
    if status_filter:
        query = query.where(TestRoute.approval_status == status_filter)
    query = query.order_by(TestRoute.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    routes = result.scalars().all()
    return routes


@router.get("/{route_id}", response_model=TestRouteResponse)
async def get_route(
    route_id: int,
    company_id: int = Query(..., description="公司ID"),
    db: AsyncSession = Depends(get_db)
):
    query = select(TestRoute).options(selectinload(TestRoute.vehicles)).where(
        and_(TestRoute.id == route_id, TestRoute.company_id == company_id)
    )
    result = await db.execute(query)
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="路线不存在")
    return route


@router.put("/{route_id}", response_model=TestRouteResponse)
async def update_route(
    route_id: int,
    route_data: TestRouteUpdate,
    company_id: int = Query(..., description="公司ID"),
    db: AsyncSession = Depends(get_db)
):
    query = select(TestRoute).options(selectinload(TestRoute.vehicles)).where(
        and_(TestRoute.id == route_id, TestRoute.company_id == company_id)
    )
    result = await db.execute(query)
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="路线不存在")

    update_data = route_data.model_dump(exclude_unset=True, exclude={"vehicle_ids"})
    for field, value in update_data.items():
        setattr(route, field, value)

    if route_data.vehicle_ids is not None:
        vehicles_result = await db.execute(
            select(TestVehicle).where(
                and_(
                    TestVehicle.id.in_(route_data.vehicle_ids),
                    TestVehicle.company_id == company_id
                )
            )
        )
        route.vehicles = vehicles_result.scalars().all()

    await db.commit()
    await db.refresh(route)
    return route


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    route_id: int,
    company_id: int = Query(..., description="公司ID"),
    db: AsyncSession = Depends(get_db)
):
    query = select(TestRoute).where(
        and_(TestRoute.id == route_id, TestRoute.company_id == company_id)
    )
    result = await db.execute(query)
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="路线不存在")

    await db.delete(route)
    await db.commit()
    return None


@router.post("/{route_id}/approve", response_model=TestRouteResponse)
async def approve_route(
    route_id: int,
    company_id: int = Query(..., description="公司ID"),
    db: AsyncSession = Depends(get_db)
):
    query = select(TestRoute).where(
        and_(TestRoute.id == route_id, TestRoute.company_id == company_id)
    )
    result = await db.execute(query)
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="路线不存在")

    route.approval_status = "approved"
    route.approved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(route)
    return route


@router.post("/{route_id}/reject", response_model=TestRouteResponse)
async def reject_route(
    route_id: int,
    rejection_reason: str,
    company_id: int = Query(..., description="公司ID"),
    db: AsyncSession = Depends(get_db)
):
    query = select(TestRoute).where(
        and_(TestRoute.id == route_id, TestRoute.company_id == company_id)
    )
    result = await db.execute(query)
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="路线不存在")

    route.approval_status = "rejected"
    route.rejection_reason = rejection_reason
    await db.commit()
    await db.refresh(route)
    return route


@router.post("/check-conflicts", response_model=List[ScheduleConflict])
async def check_route_conflicts(
    scheduled_start: datetime,
    scheduled_end: datetime,
    exclude_route_id: Optional[int] = Query(None, description="排除的路线ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if scheduled_end <= scheduled_start:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")

    company_id = current_user.id
    conflicts = await check_schedule_conflicts(db, company_id, scheduled_start, scheduled_end, exclude_route_id)
    return conflicts
