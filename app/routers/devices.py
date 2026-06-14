from datetime import datetime, timedelta
from typing import Optional, List
from math import radians, sin, cos, sqrt, atan2

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse

from app.database import get_db
from app.models import (
    RoadsideDevice,
    MaintenanceWorkOrder,
    MaintenanceStaff,
    User,
    TestRoute,
)
from app.schemas.device import (
    RoadsideDeviceCreate,
    RoadsideDeviceResponse,
    MaintenanceWorkOrderCreate,
    MaintenanceWorkOrderResponse,
    MaintenanceAssignment,
    DeviceOfflineDetection,
    DeviceHeartbeat,
)

router = APIRouter(tags=["路侧设备管理"])

OFFLINE_THRESHOLD_MINUTES = 30
EARTH_RADIUS_KM = 6371.0


class DeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    status: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    maintenance_skills: Optional[List[str]] = None
    configuration: Optional[dict] = None


class WorkOrderAssign(BaseModel):
    staff_id: int


def generate_order_number() -> str:
    now = datetime.utcnow()
    return f"WO-{now.strftime('%Y%m%d%H%M%S')}-{now.microsecond // 1000:03d}"


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_KM * c


@router.post("/heartbeat", summary="设备心跳上报")
async def device_heartbeat(
    data: DeviceHeartbeat,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RoadsideDevice).where(RoadsideDevice.device_code == data.device_code)
    )
    device = result.scalar_one_or_none()

    now = datetime.utcnow()
    created = False

    if device:
        device.last_heartbeat = now
        device.status = data.status or "online"
        device.offline_since = None

        if data.latitude is not None:
            device.latitude = data.latitude
        if data.longitude is not None:
            device.longitude = data.longitude
        if data.firmware_version is not None:
            device.firmware_version = data.firmware_version
        if data.sensor_data is not None:
            config = device.configuration or {}
            config = config.copy()
            config["last_sensor_data"] = data.sensor_data
            device.configuration = config

        device.updated_at = now
        status_code = status.HTTP_200_OK
        message = "心跳上报成功"
    else:
        device = RoadsideDevice(
            device_code=data.device_code,
            device_name=f"设备-{data.device_code}",
            device_type="unknown",
            latitude=data.latitude or 0.0,
            longitude=data.longitude or 0.0,
            status=data.status or "online",
            last_heartbeat=now,
            firmware_version=data.firmware_version,
            configuration={
                "last_sensor_data": data.sensor_data
            } if data.sensor_data else None,
        )
        db.add(device)
        created = True
        status_code = status.HTTP_201_CREATED
        message = "设备注册并心跳上报成功"

    await db.commit()
    await db.refresh(device)

    return JSONResponse(
        status_code=status_code,
        content={
            "message": message,
            "device_code": device.device_code,
            "received_at": now.isoformat(),
            "created": created,
        }
    )


@router.post("/check-offline", summary="检查离线设备并自动生成维修工单")
async def check_offline_devices(
    db: AsyncSession = Depends(get_db),
):
    threshold_time = datetime.utcnow() - timedelta(minutes=OFFLINE_THRESHOLD_MINUTES)

    result = await db.execute(
        select(RoadsideDevice).where(
            and_(
                or_(
                    RoadsideDevice.last_heartbeat < threshold_time,
                    RoadsideDevice.last_heartbeat.is_(None),
                ),
                RoadsideDevice.status != "offline",
            )
        )
    )
    offline_devices = result.scalars().all()

    generated_orders = []

    for device in offline_devices:
        device.status = "offline"
        if device.offline_since is None:
            device.offline_since = datetime.utcnow()

        existing_result = await db.execute(
            select(MaintenanceWorkOrder).where(
                and_(
                    MaintenanceWorkOrder.device_id == device.id,
                    MaintenanceWorkOrder.status.in_(["pending", "in_progress"]),
                )
            )
        )
        existing_order = existing_result.scalar_one_or_none()

        if not existing_order:
            company_id = 1
            if device.route_id:
                route_result = await db.execute(
                    select(TestRoute).where(TestRoute.id == device.route_id)
                )
                route = route_result.scalar_one_or_none()
                if route:
                    company_id = route.company_id

            order = MaintenanceWorkOrder(
                company_id=company_id,
                device_id=device.id,
                order_number=generate_order_number(),
                title=f"设备离线维修 - {device.device_name}",
                description=(
                    f"设备 {device.device_name} ({device.device_code}) "
                    f"已离线超过{OFFLINE_THRESHOLD_MINUTES}分钟，"
                    f"最后心跳时间: {device.last_heartbeat.isoformat() if device.last_heartbeat else '无'}"
                ),
                maintenance_type="emergency",
                priority="high",
                required_skills=device.maintenance_skills or ["basic_maintenance"],
                status="pending",
                reported_by="system",
            )
            db.add(order)
            generated_orders.append(order)

        device.updated_at = datetime.utcnow()

    await db.commit()

    return {
        "message": f"检查完成，发现 {len(offline_devices)} 台离线设备，生成 {len(generated_orders)} 个维修工单",
        "offline_device_count": len(offline_devices),
        "generated_order_count": len(generated_orders),
        "generated_orders": [
            {
                "order_number": o.order_number,
                "device_id": o.device_id,
                "priority": o.priority,
            }
            for o in generated_orders
        ],
    }


@router.get("", summary="获取设备列表", response_model=List[RoadsideDeviceResponse])
async def list_devices(
    status: Optional[str] = None,
    device_type: Optional[str] = None,
    route_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(RoadsideDevice)

    conditions = []
    if status:
        conditions.append(RoadsideDevice.status == status)
    if device_type:
        conditions.append(RoadsideDevice.device_type == device_type)
    if route_id:
        conditions.append(RoadsideDevice.route_id == route_id)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(RoadsideDevice.id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    devices = result.scalars().all()

    return devices


@router.post("", summary="创建设备", response_model=RoadsideDeviceResponse)
async def create_device(
    data: RoadsideDeviceCreate,
    db: AsyncSession = Depends(get_db),
):
    existing_result = await db.execute(
        select(RoadsideDevice).where(RoadsideDevice.device_code == data.device_code)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="设备编号已存在")

    device = RoadsideDevice(**data.model_dump(exclude_unset=True))
    db.add(device)
    await db.commit()
    await db.refresh(device)

    return device


@router.get("/work-orders", summary="获取维修工单列表", response_model=List[MaintenanceWorkOrderResponse])
async def list_work_orders(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    device_id: Optional[int] = None,
    assigned_to: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(MaintenanceWorkOrder)

    conditions = []
    if status:
        conditions.append(MaintenanceWorkOrder.status == status)
    if priority:
        conditions.append(MaintenanceWorkOrder.priority == priority)
    if device_id:
        conditions.append(MaintenanceWorkOrder.device_id == device_id)
    if assigned_to:
        conditions.append(MaintenanceWorkOrder.assigned_to == assigned_to)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(MaintenanceWorkOrder.id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    orders = result.scalars().all()

    return orders


@router.post("/work-orders/{order_id}/assign", summary="按技能和位置分配维护人员", response_model=MaintenanceAssignment)
async def assign_maintenance_staff(
    order_id: int,
    assign_data: Optional[WorkOrderAssign] = None,
    db: AsyncSession = Depends(get_db),
):
    order_result = await db.execute(
        select(MaintenanceWorkOrder).where(MaintenanceWorkOrder.id == order_id)
    )
    order = order_result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="维修工单不存在")

    if order.status == "completed":
        raise HTTPException(status_code=400, detail="工单已完成，无法分配")

    device_result = await db.execute(
        select(RoadsideDevice).where(RoadsideDevice.id == order.device_id)
    )
    device = device_result.scalar_one_or_none()

    if assign_data and assign_data.staff_id:
        staff_result = await db.execute(
            select(MaintenanceStaff).where(MaintenanceStaff.id == assign_data.staff_id)
        )
        staff = staff_result.scalar_one_or_none()
        if not staff:
            raise HTTPException(status_code=404, detail="维护人员不存在")
    else:
        required_skills = set(order.required_skills or [])

        staff_result = await db.execute(
            select(MaintenanceStaff).where(
                MaintenanceStaff.status.in_(["available", "on_duty"])
            )
        )
        available_staff = staff_result.scalars().all()

        if not available_staff:
            raise HTTPException(status_code=404, detail="没有可用的维护人员")

        scored_staff = []
        for staff in available_staff:
            score = 0.0
            staff_skills = set(staff.skills or [])

            if required_skills:
                matched = len(required_skills & staff_skills)
                skill_score = matched / len(required_skills) if required_skills else 1.0
                score += skill_score * 60
            else:
                score += 60

            if device and staff.current_latitude and staff.current_longitude:
                distance = calculate_distance(
                    device.latitude,
                    device.longitude,
                    staff.current_latitude,
                    staff.current_longitude,
                )
                distance_score = max(0.0, 1.0 - distance / 50.0)
                score += distance_score * 30
            else:
                score += 15

            workload_score = max(0.0, 1.0 - staff.workload / 10.0)
            score += workload_score * 10

            scored_staff.append((score, staff))

        scored_staff.sort(key=lambda x: x[0], reverse=True)
        staff = scored_staff[0][1]

    order.assigned_to = staff.name
    order.assignee_skills = staff.skills
    order.assigned_at = datetime.utcnow()
    order.status = "assigned"
    staff.workload += 1
    staff.updated_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(order)
    await db.refresh(staff)

    required_skills = set(order.required_skills or [])
    staff_skills = set(staff.skills or [])
    matched_skills = list(required_skills & staff_skills)
    missing_skills = list(required_skills - staff_skills) if required_skills else None

    return MaintenanceAssignment(
        work_order_id=order.id,
        order_number=order.order_number,
        assigned_staff_id=staff.id,
        assigned_staff_name=staff.name,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
    )


@router.get("/work-orders/{order_id}", summary="获取维修工单详情", response_model=MaintenanceWorkOrderResponse)
async def get_work_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MaintenanceWorkOrder).where(MaintenanceWorkOrder.id == order_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="维修工单不存在")

    return order


@router.get("/staff", summary="获取维护人员列表")
async def list_maintenance_staff(
    status: Optional[str] = None,
    skill: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(MaintenanceStaff)

    conditions = []
    if status:
        conditions.append(MaintenanceStaff.status == status)
    if skill:
        conditions.append(MaintenanceStaff.skills.contains([skill]))

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(MaintenanceStaff.id.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    staff_list = result.scalars().all()

    return {
        "total": len(staff_list),
        "staff": [s.to_dict() for s in staff_list],
    }


@router.get("/{device_id}", summary="获取设备详情", response_model=RoadsideDeviceResponse)
async def get_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RoadsideDevice).where(RoadsideDevice.id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    return device


@router.put("/{device_id}", summary="更新设备", response_model=RoadsideDeviceResponse)
async def update_device(
    device_id: int,
    data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RoadsideDevice).where(RoadsideDevice.id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(device, key, value)

    device.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(device)

    return device
