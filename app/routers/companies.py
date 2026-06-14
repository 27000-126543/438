from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.auth import get_current_user
from app.models import User


router = APIRouter(tags=["企业管理"])


@router.get("", response_model=List[dict], summary="获取企业列表")
async def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "name": u.company_name,
            "company_name": u.company_name,
            "username": u.username,
            "email": u.email,
            "phone": u.phone,
            "company_license": u.company_license,
            "business_scope": u.business_scope,
            "status": u.status,
            "role": u.role,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("", response_model=dict, summary="创建企业")
async def create_company(
    company_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(User).where(User.username == company_data.get("username"))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    new_user = User(
        username=company_data.get("username") or company_data.get("company_code"),
        company_name=company_data.get("name"),
        email=company_data.get("email") or f"{company_data.get('username', 'user')}@example.com",
        phone=company_data.get("contact_phone"),
        company_license=company_data.get("company_code"),
        business_scope=company_data.get("business_scope"),
        status="active",
        role="company",
    )
    new_user.set_password(company_data.get("password", "Test123456"))
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {
        "id": new_user.id,
        "name": new_user.company_name,
        "company_name": new_user.company_name,
        "username": new_user.username,
        "email": new_user.email,
        "phone": new_user.phone,
        "company_license": new_user.company_license,
        "business_scope": new_user.business_scope,
        "status": new_user.status,
        "role": new_user.role,
    }


@router.get("/{company_id}", response_model=dict, summary="获取企业详情")
async def get_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == company_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="企业不存在")
    return {
        "id": user.id,
        "name": user.company_name,
        "company_name": user.company_name,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "company_license": user.company_license,
        "business_scope": user.business_scope,
        "status": user.status,
        "role": user.role,
        "created_at": user.created_at,
    }
