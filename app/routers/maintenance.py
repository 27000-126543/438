from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.auth import get_current_user
from app.models import MaintenanceStaff, MaintenanceWorkOrder, User


router = APIRouter(tags=["维护人员管理"])


@router.get("", response_model=List[dict], summary="获取维护人员列表")
async def list_maintenance_staff(
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(MaintenanceStaff)
    if status:
        query = query.where(MaintenanceStaff.status == status)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    staff_list = result.scalars().all()

    staff_dicts = []
    for staff in staff_list:
        workload_result = await db.execute(
            select(func.count(MaintenanceWorkOrder.id)).where(
                and_(
                    MaintenanceWorkOrder.assignee_id == staff.id,
                    MaintenanceWorkOrder.status.in_(["pending", "assigned", "in_progress"])
                )
            )
        )
        actual_workload = workload_result.scalar() or 0

        if staff.workload != actual_workload:
            staff.workload = actual_workload
            staff.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(staff)

        staff_dict = staff.to_dict()
        staff_dict["current_workload"] = actual_workload
        staff_dict["available"] = staff.status in ["available", "on_duty"] and actual_workload < 8
        staff_dicts.append(staff_dict)

    return staff_dicts


@router.get("/{staff_id}", response_model=dict, summary="获取维护人员详情")
async def get_maintenance_staff(
    staff_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MaintenanceStaff).where(MaintenanceStaff.id == staff_id)
    )
    staff = result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="维护人员不存在")

    workload_result = await db.execute(
        select(func.count(MaintenanceWorkOrder.id)).where(
            and_(
                MaintenanceWorkOrder.assignee_id == staff_id,
                MaintenanceWorkOrder.status.in_(["pending", "assigned", "in_progress"])
            )
        )
    )
    actual_workload = workload_result.scalar() or 0

    if staff.workload != actual_workload:
        staff.workload = actual_workload
        staff.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(staff)

    staff_dict = staff.to_dict()
    staff_dict["current_workload"] = actual_workload
    staff_dict["available"] = staff.status in ["available", "on_duty"] and actual_workload < 8
    return staff_dict


@router.post("", response_model=dict, summary="创建维护人员")
async def create_maintenance_staff(
    staff_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import uuid
    staff_code = staff_data.get("staff_code") or f"MS{uuid.uuid4().hex[:8].upper()}"
    new_staff = MaintenanceStaff(
        staff_code=staff_code,
        name=staff_data.get("name"),
        phone=staff_data.get("phone"),
        email=staff_data.get("email"),
        skills=staff_data.get("skills", []),
        current_latitude=staff_data.get("latitude", 39.9042),
        current_longitude=staff_data.get("longitude", 116.4074),
        status=staff_data.get("status", "available"),
        workload=staff_data.get("workload", 0),
    )
    db.add(new_staff)
    await db.commit()
    await db.refresh(new_staff)
    return new_staff.to_dict()
