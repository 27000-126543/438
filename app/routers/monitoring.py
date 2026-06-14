import math
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_db
from app.models import VehicleRealtimeData, TestVehicle, TestRoute, Alarm, SafetyOfficer
from app.schemas.monitoring import (
    VehicleRealtimeDataCreate, VehicleRealtimeDataResponse,
    AlarmCreate, AlarmResponse
)

router = APIRouter(tags=["车辆实时监控"])


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 1000


def point_to_route_distance(lat: float, lng: float, waypoints: List[Dict[str, Any]]) -> float:
    if not waypoints:
        return float("inf")
    min_dist = float("inf")
    for i in range(len(waypoints) - 1):
        p1 = waypoints[i]
        p2 = waypoints[i + 1]
        p1_lat, p1_lng = p1.get("lat", p1.get("latitude", 0)), p1.get("lng", p1.get("longitude", 0))
        p2_lat, p2_lng = p2.get("lat", p2.get("latitude", 0)), p2.get("lng", p2.get("longitude", 0))

        d1 = haversine_distance(lat, lng, p1_lat, p1_lng)
        d2 = haversine_distance(lat, lng, p2_lat, p2_lng)
        seg_len = haversine_distance(p1_lat, p1_lng, p2_lat, p2_lng)

        if seg_len == 0:
            dist = d1
        else:
            t = max(0, min(1, ((lat - p1_lat) * (p2_lat - p1_lat) + (lng - p1_lng) * (p2_lng - p1_lng)) / (seg_len ** 2)))
            proj_lat = p1_lat + t * (p2_lat - p1_lat)
            proj_lng = p1_lng + t * (p2_lng - p1_lng)
            dist = haversine_distance(lat, lng, proj_lat, proj_lng)

        min_dist = min(min_dist, d1, d2, dist)
    return min_dist


async def assign_safety_officer(db: AsyncSession, company_id: int) -> Optional[SafetyOfficer]:
    query = select(SafetyOfficer).where(
        SafetyOfficer.status == "on_duty"
    ).order_by(SafetyOfficer.workload.asc()).limit(1)
    result = await db.execute(query)
    officer = result.scalar_one_or_none()
    return officer


async def create_alarm(
    db: AsyncSession,
    company_id: int,
    vehicle_id: int,
    alarm_type: str,
    alarm_level: str,
    title: str,
    description: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    related_data: Optional[Dict[str, Any]] = None
) -> Alarm:
    officer = await assign_safety_officer(db, company_id)

    alarm = Alarm(
        company_id=company_id,
        vehicle_id=vehicle_id,
        alarm_type=alarm_type,
        alarm_level=alarm_level,
        alarm_code=f"{alarm_type.upper()}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        title=title,
        description=description,
        latitude=latitude,
        longitude=longitude,
        status="pending",
        assigned_to=officer.name if officer else None,
        related_data=related_data
    )

    if officer:
        officer.workload += 1

    db.add(alarm)
    return alarm


async def detect_deviation(
    db: AsyncSession,
    vehicle: TestVehicle,
    data: VehicleRealtimeData
) -> Optional[Alarm]:
    if not vehicle.routes:
        return None

    active_route = None
    for route in vehicle.routes:
        if route.approval_status == "approved" and route.scheduled_start and route.scheduled_end:
            now = datetime.utcnow()
            if route.scheduled_start - timedelta(minutes=10) <= now <= route.scheduled_end + timedelta(minutes=10):
                active_route = route
                break

    if not active_route or not active_route.waypoints:
        return None

    deviation_threshold = 500.0
    distance = point_to_route_distance(data.latitude, data.longitude, active_route.waypoints)

    if distance > deviation_threshold:
        return await create_alarm(
            db,
            company_id=vehicle.company_id,
            vehicle_id=vehicle.id,
            alarm_type="route_deviation",
            alarm_level="critical" if distance > 1000 else "warning",
            title="车辆偏离路线",
            description=f"车辆偏离规划路线{round(distance, 1)}米，规划路线：{active_route.route_name}",
            latitude=data.latitude,
            longitude=data.longitude,
            related_data={
                "route_id": active_route.id,
                "route_name": active_route.route_name,
                "deviation_distance_meters": round(distance, 1),
                "threshold_meters": deviation_threshold
            }
        )
    return None


async def detect_speeding(
    db: AsyncSession,
    vehicle: TestVehicle,
    data: VehicleRealtimeData
) -> Optional[Alarm]:
    if data.speed is None:
        return None

    speed_limit = 60.0
    for route in vehicle.routes:
        if route.speed_limit:
            speed_limit = route.speed_limit
            break

    if data.speed > speed_limit:
        over_percentage = (data.speed - speed_limit) / speed_limit * 100
        alarm_level = "info"
        if over_percentage >= 50:
            alarm_level = "critical"
        elif over_percentage >= 20:
            alarm_level = "warning"

        return await create_alarm(
            db,
            company_id=vehicle.company_id,
            vehicle_id=vehicle.id,
            alarm_type="speeding",
            alarm_level=alarm_level,
            title="车辆超速告警",
            description=f"车辆速度{data.speed}km/h，超过限速{speed_limit}km/h，超速{round(over_percentage, 1)}%",
            latitude=data.latitude,
            longitude=data.longitude,
            related_data={
                "current_speed": data.speed,
                "speed_limit": speed_limit,
                "over_percentage": round(over_percentage, 1)
            }
        )
    return None


async def detect_lane_departure(
    db: AsyncSession,
    vehicle: TestVehicle,
    data: VehicleRealtimeData
) -> Optional[Alarm]:
    if data.lane_departure:
        return await create_alarm(
            db,
            company_id=vehicle.company_id,
            vehicle_id=vehicle.id,
            alarm_type="lane_departure",
            alarm_level="warning",
            title="车道偏离告警",
            description="车辆检测到非预期车道偏离，请确认驾驶员状态",
            latitude=data.latitude,
            longitude=data.longitude,
            related_data={
                "heading": data.heading,
                "steering_angle": data.steering_angle
            }
        )
    return None


async def detect_obstacle(
    db: AsyncSession,
    vehicle: TestVehicle,
    data: VehicleRealtimeData
) -> Optional[Alarm]:
    if data.obstacle_detected and data.obstacle_distance is not None and data.obstacle_distance < 5.0:
        alarm_level = "critical" if data.obstacle_distance < 2.0 else "warning"
        return await create_alarm(
            db,
            company_id=vehicle.company_id,
            vehicle_id=vehicle.id,
            alarm_type="obstacle_critical",
            alarm_level=alarm_level,
            title="障碍物接近告警",
            description=f"检测到前方障碍物距离仅{round(data.obstacle_distance, 1)}米，请立即减速或刹车",
            latitude=data.latitude,
            longitude=data.longitude,
            related_data={
                "obstacle_distance": data.obstacle_distance,
                "speed": data.speed,
                "brake_status": data.brake_status
            }
        )
    return None


@router.post("/data", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def report_vehicle_data(
    record: VehicleRealtimeDataCreate,
    db: AsyncSession = Depends(get_db)
):
    vehicle_query = select(TestVehicle).options(
        selectinload(TestVehicle.routes)
    ).where(TestVehicle.id == record.vehicle_id)
    vehicle_result = await db.execute(vehicle_query)
    vehicle = vehicle_result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")

    sensor_data = record.sensor_data or {}
    new_data = VehicleRealtimeData(
        vehicle_id=record.vehicle_id,
        route_id=record.route_id,
        timestamp=record.timestamp or datetime.utcnow(),
        latitude=record.latitude,
        longitude=record.longitude,
        altitude=record.altitude,
        speed=record.speed,
        heading=record.heading,
        acceleration=record.acceleration,
        brake_status=record.brake_status,
        throttle_position=record.throttle_position,
        steering_angle=record.steering_angle,
        gear=record.gear,
        engine_rpm=record.engine_rpm,
        fuel_level=record.fuel_level,
        battery_level=record.battery_level,
        autopilot_enabled=record.autopilot_enabled,
        autopilot_mode=record.autopilot_mode,
        obstacle_detected=record.obstacle_detected,
        obstacle_distance=record.obstacle_distance,
        lane_departure=record.lane_departure,
        signal_light=record.signal_light,
        sensor_data=sensor_data,
        error_codes=record.error_codes
    )

    db.add(new_data)

    if record.latitude and record.longitude:
        vehicle.current_latitude = record.latitude
        vehicle.current_longitude = record.longitude
    if record.speed is not None:
        vehicle.current_speed = record.speed
    if sensor_data.get("mileage") is not None:
        vehicle.mileage = sensor_data.get("mileage")

    vehicle.status = "testing"

    generated_alarms = []

    deviation_alarm = await detect_deviation(db, vehicle, new_data)
    if deviation_alarm:
        generated_alarms.append(deviation_alarm)

    speeding_alarm = await detect_speeding(db, vehicle, new_data)
    if speeding_alarm:
        generated_alarms.append(speeding_alarm)

    lane_alarm = await detect_lane_departure(db, vehicle, new_data)
    if lane_alarm:
        generated_alarms.append(lane_alarm)

    obstacle_alarm = await detect_obstacle(db, vehicle, new_data)
    if obstacle_alarm:
        generated_alarms.append(obstacle_alarm)

    await db.commit()
    await db.refresh(new_data)

    for alarm in generated_alarms:
        await db.refresh(alarm)

    return {
        "record_id": new_data.id,
        "received_at": new_data.received_at.isoformat(),
        "vehicle_status": vehicle.status,
        "alarms_generated": len(generated_alarms),
        "alarms": [
            {
                "id": a.id,
                "alarm_type": a.alarm_type,
                "alarm_level": a.alarm_level,
                "title": a.title,
                "assigned_to": a.assigned_to
            }
            for a in generated_alarms
        ]
    }


@router.post("/batch", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def report_vehicle_data_batch(
    records: List[VehicleRealtimeDataCreate],
    db: AsyncSession = Depends(get_db)
):
    success_count = 0
    failed_count = 0
    total_alarms = 0
    errors = []

    for idx, record in enumerate(records):
        try:
            vehicle_query = select(TestVehicle).options(
                selectinload(TestVehicle.routes)
            ).where(TestVehicle.id == record.vehicle_id)
            vehicle_result = await db.execute(vehicle_query)
            vehicle = vehicle_result.scalar_one_or_none()
            if not vehicle:
                failed_count += 1
                errors.append({"index": idx, "error": f"车辆ID {record.vehicle_id} 不存在"})
                continue

            sensor_data = record.sensor_data or {}
            new_data = VehicleRealtimeData(
                vehicle_id=record.vehicle_id,
                route_id=record.route_id,
                timestamp=record.timestamp or datetime.utcnow(),
                latitude=record.latitude,
                longitude=record.longitude,
                altitude=record.altitude,
                speed=record.speed,
                heading=record.heading,
                acceleration=record.acceleration,
                brake_status=record.brake_status,
                throttle_position=record.throttle_position,
                steering_angle=record.steering_angle,
                gear=record.gear,
                engine_rpm=record.engine_rpm,
                fuel_level=record.fuel_level,
                battery_level=record.battery_level,
                autopilot_enabled=record.autopilot_enabled,
                autopilot_mode=record.autopilot_mode,
                obstacle_detected=record.obstacle_detected,
                obstacle_distance=record.obstacle_distance,
                lane_departure=record.lane_departure,
                signal_light=record.signal_light,
                sensor_data=sensor_data,
                error_codes=record.error_codes
            )
            db.add(new_data)

            if record.latitude and record.longitude:
                vehicle.current_latitude = record.latitude
                vehicle.current_longitude = record.longitude
            if record.speed is not None:
                vehicle.current_speed = record.speed
            if sensor_data.get("mileage") is not None:
                vehicle.mileage = sensor_data.get("mileage")

            vehicle.status = "testing"

            generated_alarms = []

            deviation_alarm = await detect_deviation(db, vehicle, new_data)
            if deviation_alarm:
                generated_alarms.append(deviation_alarm)

            speeding_alarm = await detect_speeding(db, vehicle, new_data)
            if speeding_alarm:
                generated_alarms.append(speeding_alarm)

            lane_alarm = await detect_lane_departure(db, vehicle, new_data)
            if lane_alarm:
                generated_alarms.append(lane_alarm)

            obstacle_alarm = await detect_obstacle(db, vehicle, new_data)
            if obstacle_alarm:
                generated_alarms.append(obstacle_alarm)

            total_alarms += len(generated_alarms)

            success_count += 1
        except Exception as e:
            failed_count += 1
            errors.append({"index": idx, "error": str(e)})

    await db.commit()

    return {
        "total_received": len(records),
        "success_count": success_count,
        "failed_count": failed_count,
        "alarms_generated": total_alarms,
        "errors": errors
    }


@router.get("/vehicles/{vehicle_id}/data", response_model=List[Dict[str, Any]])
async def get_vehicle_realtime_data(
    vehicle_id: int,
    company_id: int = Query(..., description="公司ID"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    vehicle_query = select(TestVehicle).where(TestVehicle.id == vehicle_id)
    vehicle_result = await db.execute(vehicle_query)
    vehicle = vehicle_result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")
    if vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="无权访问该车辆数据")

    query = select(VehicleRealtimeData).where(VehicleRealtimeData.vehicle_id == vehicle_id)
    if start_time:
        query = query.where(VehicleRealtimeData.timestamp >= start_time)
    if end_time:
        query = query.where(VehicleRealtimeData.timestamp <= end_time)
    query = query.order_by(VehicleRealtimeData.timestamp.desc()).limit(limit)

    result = await db.execute(query)
    records = result.scalars().all()
    return [r.to_dict() for r in records]


@router.get("/vehicles/{vehicle_id}/latest", response_model=Optional[Dict[str, Any]])
async def get_vehicle_latest_data(
    vehicle_id: int,
    company_id: int = Query(..., description="公司ID"),
    db: AsyncSession = Depends(get_db)
):
    vehicle_query = select(TestVehicle).where(TestVehicle.id == vehicle_id)
    vehicle_result = await db.execute(vehicle_query)
    vehicle = vehicle_result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")
    if vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="无权访问该车辆数据")

    query = select(VehicleRealtimeData).where(
        VehicleRealtimeData.vehicle_id == vehicle_id
    ).order_by(VehicleRealtimeData.timestamp.desc()).limit(1)

    result = await db.execute(query)
    record = result.scalar_one_or_none()
    return record.to_dict() if record else None


@router.get("/alarms", response_model=List[Dict[str, Any]])
async def list_alarms(
    company_id: int = Query(..., description="公司ID"),
    vehicle_id: Optional[int] = Query(None, description="车辆ID"),
    status_filter: Optional[str] = Query(None, description="告警状态筛选"),
    alarm_type: Optional[str] = Query(None, description="告警类型筛选"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    query = select(Alarm).options(
        selectinload(Alarm.vehicle)
    ).where(Alarm.company_id == company_id)
    if vehicle_id:
        query = query.where(Alarm.vehicle_id == vehicle_id)
    if status_filter:
        query = query.where(Alarm.status == status_filter)
    if alarm_type:
        query = query.where(Alarm.alarm_type == alarm_type)
    if start_time:
        query = query.where(Alarm.timestamp >= start_time)
    if end_time:
        query = query.where(Alarm.timestamp <= end_time)
    query = query.order_by(Alarm.timestamp.desc()).limit(limit)

    result = await db.execute(query)
    alarms = result.scalars().all()
    return [a.to_dict() for a in alarms]


@router.post("/alarms/{alarm_id}/acknowledge", response_model=Dict[str, Any])
async def acknowledge_alarm(
    alarm_id: int,
    acknowledged_by: str,
    company_id: int = Query(..., description="公司ID"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Alarm).options(
        selectinload(Alarm.vehicle)
    ).where(and_(Alarm.id == alarm_id, Alarm.company_id == company_id))
    result = await db.execute(query)
    alarm = result.scalar_one_or_none()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    alarm.status = "acknowledged"
    alarm.acknowledged_by = acknowledged_by
    alarm.acknowledged_at = datetime.utcnow()

    await db.commit()
    await db.refresh(alarm)
    return alarm.to_dict()


@router.post("/alarms/{alarm_id}/resolve", response_model=Dict[str, Any])
async def resolve_alarm(
    alarm_id: int,
    resolved_by: str,
    resolution_notes: Optional[str] = None,
    company_id: int = Query(..., description="公司ID"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Alarm).options(
        selectinload(Alarm.vehicle)
    ).where(and_(Alarm.id == alarm_id, Alarm.company_id == company_id))
    result = await db.execute(query)
    alarm = result.scalar_one_or_none()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    alarm.status = "resolved"
    alarm.resolved_by = resolved_by
    alarm.resolved_at = datetime.utcnow()
    alarm.resolution_notes = resolution_notes

    if alarm.assigned_to:
        officer_query = select(SafetyOfficer).where(SafetyOfficer.name == alarm.assigned_to)
        officer_result = await db.execute(officer_query)
        officer = officer_result.scalar_one_or_none()
        if officer and officer.workload > 0:
            officer.workload -= 1

    await db.commit()
    await db.refresh(alarm)
    return alarm.to_dict()


@router.get("/safety-officers", response_model=List[Dict[str, Any]])
async def list_safety_officers(
    status_filter: Optional[str] = Query(None, description="状态筛选"),
    db: AsyncSession = Depends(get_db)
):
    query = select(SafetyOfficer)
    if status_filter:
        query = query.where(SafetyOfficer.status == status_filter)
    query = query.order_by(SafetyOfficer.workload.asc())

    result = await db.execute(query)
    officers = result.scalars().all()
    return [o.to_dict() for o in officers]
