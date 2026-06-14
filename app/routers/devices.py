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
MIN_SKILL_MATCH_RATIO = 0.3
MAX_DISTANCE_KM = 30
MAX_WORKLOAD = 8
AVERAGE_TRAVEL_SPEED_KMH = 30
ESTIMATED_REPAIR_MINUTES = 60


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


def generate_escalation_rules(priority: str) -> List[dict]:
    if priority in ["critical", "urgent"]:
        return [
            {
                "level": 1,
                "condition": "15分钟未接单",
                "action": "通知区域主管",
                "notify_roles": ["区域主管", "运维经理"],
                "timeout_minutes": 15
            },
            {
                "level": 2,
                "condition": "30分钟未到场",
                "action": "升级至运维总监",
                "notify_roles": ["运维总监", "运营经理"],
                "timeout_minutes": 30
            },
            {
                "level": 3,
                "condition": "60分钟未修复",
                "action": "启动备用人员池",
                "notify_roles": ["运维总监", "客户服务"],
                "timeout_minutes": 60
            }
        ]
    elif priority == "high":
        return [
            {
                "level": 1,
                "condition": "30分钟未接单",
                "action": "通知区域主管",
                "notify_roles": ["区域主管"],
                "timeout_minutes": 30
            },
            {
                "level": 2,
                "condition": "60分钟未到场",
                "action": "升级至运维经理",
                "notify_roles": ["运维经理"],
                "timeout_minutes": 60
            }
        ]
    else:
        return [
            {
                "level": 1,
                "condition": "60分钟未接单",
                "action": "通知区域主管",
                "notify_roles": ["区域主管"],
                "timeout_minutes": 60
            }
        ]


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


async def auto_assign_work_order(
    order: MaintenanceWorkOrder,
    device: RoadsideDevice,
    db: AsyncSession
):
    from app.schemas.device import CandidateRanking

    required_skills = set(order.required_skills or [])
    priority = order.priority or "normal"

    staff_result = await db.execute(
        select(MaintenanceStaff).where(
            MaintenanceStaff.status.in_(["available", "on_duty"])
        )
    )
    all_staff = staff_result.scalars().all()

    if not all_staff:
        return {
            "success": False,
            "reason": "no_available_staff",
            "message": "当前没有可用的维护人员",
            "pending_reason_detail": {
                "no_staff": True,
                "insufficient_skills": 0,
                "too_far": 0,
                "workload_full": 0,
                "available_count": 0,
                "skill_match_count": 0,
                "distance_ok_count": 0,
                "workload_ok_count": 0,
                "qualification_note": f"资格筛选：技能匹配率>={int(MIN_SKILL_MATCH_RATIO*100)}%, 距离<={MAX_DISTANCE_KM}km, 负载<={MAX_WORKLOAD}单"
            },
            "candidate_rankings": [],
            "total_candidates": 0,
            "eligible_count": 0
        }

    no_skill_count = 0
    too_far_count = 0
    overloaded_count = 0
    all_scored = []

    for staff in all_staff:
        staff_skills = set(staff.skills or [])
        elimination_reasons = []
        elimination_details = {}
        is_eligible = True

        skill_match_ratio = 1.0
        if required_skills:
            matched = len(required_skills & staff_skills)
            skill_match_ratio = matched / len(required_skills) if required_skills else 1.0
            if skill_match_ratio < MIN_SKILL_MATCH_RATIO:
                no_skill_count += 1
                is_eligible = False
                elimination_reasons.append("技能不匹配")
                elimination_details["insufficient_skills"] = {
                    "required": list(required_skills),
                    "matched": list(required_skills & staff_skills),
                    "match_ratio": round(skill_match_ratio, 2),
                    "min_required": MIN_SKILL_MATCH_RATIO
                }

        distance = None
        if device and staff.current_latitude and staff.current_longitude and device.latitude and device.longitude:
            distance = calculate_distance(
                device.latitude,
                device.longitude,
                staff.current_latitude,
                staff.current_longitude,
            )
            if distance > MAX_DISTANCE_KM:
                too_far_count += 1
                is_eligible = False
                elimination_reasons.append("距离太远")
                elimination_details["too_far"] = {
                    "distance_km": round(distance, 2),
                    "max_allowed": MAX_DISTANCE_KM
                }

        if staff.workload >= MAX_WORKLOAD:
            overloaded_count += 1
            is_eligible = False
            elimination_reasons.append("工单满载")
            elimination_details["overloaded"] = {
                "current_workload": staff.workload,
                "max_allowed": MAX_WORKLOAD
            }

        score = 0.0
        skill_score = 0.0
        distance_score = 0.0
        workload_score = 0.0

        if required_skills:
            skill_score = skill_match_ratio * 60
        else:
            skill_score = 60
        score += skill_score

        if distance is not None:
            distance_score = max(0.0, 1.0 - distance / MAX_DISTANCE_KM) * 30
        else:
            distance_score = 15
        score += distance_score

        workload_score = max(0.0, 1.0 - staff.workload / MAX_WORKLOAD) * 10
        score += workload_score

        all_scored.append({
            "staff": staff,
            "score": score,
            "skill_score": skill_score,
            "distance_score": distance_score,
            "workload_score": workload_score,
            "skill_match_ratio": skill_match_ratio,
            "distance_km": distance,
            "current_workload": staff.workload,
            "eligible": is_eligible,
            "elimination_reason": "、".join(elimination_reasons) if elimination_reasons else None,
            "elimination_details": elimination_details if elimination_details else None
        })

    all_scored.sort(key=lambda x: (x["eligible"], x["score"]), reverse=True)

    candidate_rankings = []
    for i, s in enumerate(all_scored):
        candidate_rankings.append(CandidateRanking(
            staff_id=s["staff"].id,
            staff_name=s["staff"].name,
            rank=i + 1,
            total_score=round(s["score"], 2),
            skill_score=round(s["skill_score"], 2),
            distance_score=round(s["distance_score"], 2),
            workload_score=round(s["workload_score"], 2),
            skill_match_ratio=round(s["skill_match_ratio"], 2),
            distance_km=round(s["distance_km"], 2) if s["distance_km"] else None,
            current_workload=s["current_workload"],
            eligible=s["eligible"],
            elimination_reason=s["elimination_reason"],
            elimination_details=s["elimination_details"]
        ))

    eligible_staff = [s for s in all_scored if s["eligible"]]

    if not eligible_staff:
        all_overloaded = overloaded_count == len(all_staff)
        reason_code = "all_overloaded" if all_overloaded else "mixed"

        pending_detail = {
            "no_staff": len(all_staff) == 0,
            "insufficient_skills": no_skill_count,
            "too_far": too_far_count,
            "workload_full": overloaded_count,
            "available_count": len(all_staff),
            "skill_match_count": len(all_staff) - no_skill_count,
            "distance_ok_count": len(all_staff) - too_far_count,
            "workload_ok_count": len(all_staff) - overloaded_count,
            "qualification_note": f"资格筛选：技能匹配率>={int(MIN_SKILL_MATCH_RATIO*100)}%, 距离<={MAX_DISTANCE_KM}km, 负载<={MAX_WORKLOAD}单",
            "all_overloaded": all_overloaded
        }

        reasons = []
        if no_skill_count > 0:
            reasons.append(f"{no_skill_count} 人技能不匹配（最低要求匹配 {int(MIN_SKILL_MATCH_RATIO*100)}% 技能）")
        if too_far_count > 0:
            reasons.append(f"{too_far_count} 人距离超过 {MAX_DISTANCE_KM} 公里")
        if overloaded_count > 0:
            reasons.append(f"{overloaded_count} 人工单已达 {MAX_WORKLOAD} 单上限")

        if all_overloaded:
            message = f"所有 {len(all_staff)} 名维护人员工单已满，当前最大负载 {MAX_WORKLOAD} 单，工单已留待分配"
            reason_code = "all_overloaded"
        else:
            message = "没有符合条件的维护人员：" + "；".join(reasons)
            if pending_detail["insufficient_skills"] > 0 and pending_detail["too_far"] == 0 and pending_detail["workload_full"] == 0:
                reason_code = "insufficient_skills"
            elif pending_detail["too_far"] > 0 and pending_detail["insufficient_skills"] == 0 and pending_detail["workload_full"] == 0:
                reason_code = "too_far"
            elif pending_detail["workload_full"] > 0 and pending_detail["insufficient_skills"] == 0 and pending_detail["too_far"] == 0:
                reason_code = "overloaded"

        return {
            "success": False,
            "reason": reason_code,
            "message": message,
            "pending_reason_detail": pending_detail,
            "candidate_rankings": candidate_rankings,
            "total_candidates": len(all_staff),
            "eligible_count": 0
        }

    best = eligible_staff[0]
    staff = best["staff"]
    distance = best["distance_km"]

    travel_time_hours = (distance or 5.0) / AVERAGE_TRAVEL_SPEED_KMH
    estimated_arrival = datetime.utcnow() + timedelta(hours=travel_time_hours)
    estimated_completion = estimated_arrival + timedelta(minutes=ESTIMATED_REPAIR_MINUTES)

    order.assigned_to = staff.name
    order.assignee_id = staff.id
    order.assignee_skills = staff.skills
    order.assigned_at = datetime.utcnow()
    order.status = "assigned"
    order.estimated_arrival = estimated_arrival
    order.estimated_completion = estimated_completion
    staff.workload += 1
    staff.updated_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(order)
    await db.refresh(staff)

    matched_skills = list(required_skills & set(staff.skills or []))
    missing_skills = list(required_skills - set(staff.skills or [])) if required_skills else None

    assignment_basis = {
        "skill_score": round(best["skill_score"], 2),
        "skill_weight": 60,
        "distance_score": round(best["distance_score"], 2),
        "distance_weight": 30,
        "workload_score": round(best["workload_score"], 2),
        "workload_weight": 10,
        "total_score": round(best["score"], 2),
        "skill_match_ratio": round(best["skill_match_ratio"], 2),
        "distance_km": round(best["distance_km"] or 0, 2),
        "current_workload": best["current_workload"]
    }

    return {
        "success": True,
        "staff_id": staff.id,
        "staff_name": staff.name,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "score": round(best["score"], 2),
        "message": f"已自动分配给 {staff.name}，预计 {travel_time_hours*60:.0f} 分钟后到场",
        "estimated_arrival_time": estimated_arrival.isoformat(),
        "estimated_completion_time": estimated_completion.isoformat(),
        "assignment_basis": assignment_basis,
        "escalation_rules": generate_escalation_rules(priority),
        "pending_reason_detail": None,
        "candidate_rankings": candidate_rankings,
        "total_candidates": len(all_staff),
        "eligible_count": len(eligible_staff)
    }


@router.post("/check-offline", summary="检查离线设备并自动生成维修工单和派单")
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

        order_info = None
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
            await db.flush()
            await db.refresh(order)

            assign_result = await auto_assign_work_order(order, device, db)

            order_info = {
                "order_number": order.order_number,
                "device_id": order.device_id,
                "priority": order.priority,
                "status": order.status,
                "assignment": assign_result
            }
            generated_orders.append(order_info)

        device.updated_at = datetime.utcnow()

    await db.commit()

    return {
        "message": f"检查完成，发现 {len(offline_devices)} 台离线设备，生成 {len(generated_orders)} 个维修工单",
        "offline_device_count": len(offline_devices),
        "generated_order_count": len(generated_orders),
        "assigned_count": len([o for o in generated_orders if o["status"] == "assigned"]),
        "pending_count": len([o for o in generated_orders if o["status"] == "pending"]),
        "generated_orders": generated_orders,
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


@router.post("", summary="创建设备", response_model=RoadsideDeviceResponse, status_code=status.HTTP_201_CREATED)
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
