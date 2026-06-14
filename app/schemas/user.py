from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class UserBase(BaseModel):
    company_name: str
    username: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_license: Optional[str] = None
    business_scope: Optional[str] = None
    status: Optional[str] = "active"
    role: Optional[str] = "enterprise"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = ["enterprise", "admin", "operator", "auditor", "viewer"]
        if v.lower() not in valid_roles:
            raise ValueError(f"角色必须是: {', '.join(valid_roles)}")
        return v.lower()

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = ["active", "inactive", "pending", "suspended"]
        if v.lower() not in valid_statuses:
            raise ValueError(f"状态必须是: {', '.join(valid_statuses)}")
        return v.lower()


class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码长度至少为 6 位")
        return v


class UserUpdate(BaseModel):
    company_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_license: Optional[str] = None
    business_scope: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserRegister(BaseModel):
    company_name: str
    username: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    company_license: Optional[str] = None
    business_scope: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码长度至少为 6 位")
        return v


class UserChangePassword(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("新密码长度至少为 6 位")
        return v


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserInDB(UserBase):
    id: int
    password_hash: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
