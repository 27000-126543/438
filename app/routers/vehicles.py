from datetime import date, datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import TestVehicle, User
from app.schemas.vehicle import VehicleRegisterCreate, TestVehicleResponse

router = APIRouter()

VALID_AUTOMATION_LEVELS = {"L1", "L2", "L3", "L4", "L5"}

REQUIRED_CONFIG_FIELDS = {
    "sensor_config": ["lidar", "camera", "radar", "ultrasonic"],
    "compute_platform": ["processor", "memory_gb", "storage_gb"],
    "communication_module": ["type", "protocol"],
    "safety_system": ["emergency_brake", "driver_monitoring"]
}


class ValidationErrorDetail(BaseModel):
    field: str
    message: str


class VehicleRegistrationResponse(BaseModel):
    success: bool
    message: str
    vehicle_id: Optional[int] = None
    vehicle: Optional[Dict[str, Any]] = None
    errors: Optional[List[ValidationErrorDetail]] = None
    correction_notice: Optional[Dict[str, Any]] = None


def validate_vehicle_config(config: Dict[str, Any]) -> List[ValidationErrorDetail]:
    errors = []

    for section, required_fields in REQUIRED_CONFIG_FIELDS.items():
        config_section = config.get(section) if config else None
        if config_section is None:
            errors.append(ValidationErrorDetail(
                field=f"vehicle_config.{section}",
                message=f"缺少必填配置节: {section}"
            ))
            continue

        for field in required_fields:
            if field not in config_section:
                errors.append(ValidationErrorDetail(
                    field=f"vehicle_config.{section}.{field}",
                    message=f"缺少必填字段: {section}.{field}"
                ))

    if config and config.get("sensor_config"):
        sensor_config = config.get("sensor_config")
        lidar = sensor_config.get("lidar")
        camera = sensor_config.get("camera")
        radar = sensor_config.get("radar")
        if not lidar and not camera and not radar:
            errors.append(ValidationErrorDetail(
                field="vehicle_config.sensor_config",
                message="至少需要一种传感器配置(lidar/camera/radar)"
            ))

    if config and config.get("compute_platform"):
        compute_platform = config.get("compute_platform")
        memory = compute_platform.get("memory_gb")
        if memory is not None and isinstance(memory, (int, float)) and memory < 8:
            errors.append(ValidationErrorDetail(
                field="vehicle_config.compute_platform.memory_gb",
                message="内存至少需要 8GB"
            ))

    if config and config.get("communication_module"):
        communication_module = config.get("communication_module")
        comm_type = communication_module.get("type")
        if comm_type and comm_type.upper() not in {"4G", "5G", "V2X", "WIFI", "BLUETOOTH"}:
            errors.append(ValidationErrorDetail(
                field="vehicle_config.communication_module.type",
                message=f"不支持的通信类型: {comm_type}"
            ))

    if config and config.get("safety_system"):
        safety_system = config.get("safety_system")
        emergency_brake = safety_system.get("emergency_brake")
        if emergency_brake is None:
            errors.append(ValidationErrorDetail(
                field="vehicle_config.safety_system.emergency_brake",
                message="必须配置紧急制动系统"
            ))

    return errors


def validate_insurance_expiry(insurance_expiry_date: date) -> Optional[ValidationErrorDetail]:
    today = date.today()
    if insurance_expiry_date <= today:
        return ValidationErrorDetail(
            field="insurance_expiry_date",
            message=f"保险已过期或即将过期，有效期截止日期 {insurance_expiry_date} 必须晚于今天 {today}"
        )

    min_valid_days = 30
    days_until_expiry = (insurance_expiry_date - today).days
    if days_until_expiry < min_valid_days:
        return ValidationErrorDetail(
            field="insurance_expiry_date",
            message=f"保险有效期不足，剩余 {days_until_expiry} 天，至少需要 {min_valid_days} 天"
        )

    return None


def validate_vin_unique(vin: str) -> Optional[ValidationErrorDetail]:
    if len(vin) < 17:
        return ValidationErrorDetail(
            field="vin",
            message="VIN码长度不足17位"
        )
    return None


def validate_automation_level_value(level: Optional[str]) -> Optional[ValidationErrorDetail]:
    if level is None:
        return ValidationErrorDetail(
            field="automation_level",
            message="自动化等级不能为空"
        )
    if not isinstance(level, str):
        return ValidationErrorDetail(
            field="automation_level",
            message=f"自动化等级必须是字符串类型，当前类型: {type(level).__name__}"
        )
    level_upper = level.strip().upper()
    if level_upper not in VALID_AUTOMATION_LEVELS:
        return ValidationErrorDetail(
            field="automation_level",
            message=f"自动化等级必须是 L1-L5 中的一个，当前值: {level}，有效值: {', '.join(sorted(VALID_AUTOMATION_LEVELS))}"
        )
    return None


def generate_correction_notice(errors: List[ValidationErrorDetail], company_name: str) -> Dict[str, Any]:
    return {
        "notice_title": "测试车辆注册资料补正通知",
        "recipient_company": company_name,
        "issue_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_issues": len(errors),
        "issues": [
            {
                "field": err.field,
                "description": err.message,
                "suggestion": f"请核对并修正 {err.field} 的信息"
            }
            for err in errors
        ],
        "deadline": "请在收到通知后3个工作日内完成补正并重新提交",
        "contact_info": {
            "department": "智能网联汽车测试管理中心",
            "phone": "400-XXX-XXXX",
            "email": "support@example.com"
        }
    }


@router.post("/register", response_model=VehicleRegistrationResponse, status_code=status.HTTP_200_OK)
async def register_test_vehicle(
    data: VehicleRegisterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    errors: List[ValidationErrorDetail] = []

    if not data.vin or not str(data.vin).strip():
        errors.append(ValidationErrorDetail(
            field="vin",
            message="VIN码不能为空"
        ))
    normalized_vin = str(data.vin).strip() if data.vin else data.vin

    if not data.license_plate or not str(data.license_plate).strip():
        errors.append(ValidationErrorDetail(
            field="license_plate",
            message="车牌号不能为空"
        ))
    normalized_license_plate = str(data.license_plate).strip() if data.license_plate else data.license_plate

    if not data.vehicle_model or not str(data.vehicle_model).strip():
        errors.append(ValidationErrorDetail(
            field="vehicle_model",
            message="车辆型号不能为空"
        ))
    normalized_vehicle_model = str(data.vehicle_model).strip() if data.vehicle_model else data.vehicle_model

    if not data.vehicle_type or not str(data.vehicle_type).strip():
        errors.append(ValidationErrorDetail(
            field="vehicle_type",
            message="车辆类型不能为空"
        ))

    if not data.test_type or not str(data.test_type).strip():
        errors.append(ValidationErrorDetail(
            field="test_type",
            message="测试类型不能为空"
        ))

    if not data.test_area or not str(data.test_area).strip():
        errors.append(ValidationErrorDetail(
            field="test_area",
            message="测试区域不能为空"
        ))

    if not data.manufacture_date:
        errors.append(ValidationErrorDetail(
            field="manufacture_date",
            message="生产日期不能为空"
        ))

    if not data.registration_date:
        errors.append(ValidationErrorDetail(
            field="registration_date",
            message="注册日期不能为空"
        ))

    if not data.test_expiry_date:
        errors.append(ValidationErrorDetail(
            field="test_expiry_date",
            message="测试有效期截止日期不能为空"
        ))

    if not data.insurance_expiry_date:
        errors.append(ValidationErrorDetail(
            field="insurance_expiry_date",
            message="保险有效期截止日期不能为空"
        ))

    if normalized_vin:
        vin_error = validate_vin_unique(normalized_vin)
        if vin_error:
            errors.append(vin_error)

    automation_level_error = validate_automation_level_value(data.automation_level)
    if automation_level_error:
        errors.append(automation_level_error)

    normalized_automation_level = (
        data.automation_level.strip().upper()
        if data.automation_level and isinstance(data.automation_level, str)
        else data.automation_level
    )

    if normalized_vin:
        result = await db.execute(select(TestVehicle).where(TestVehicle.vin == normalized_vin))
        if result.scalar_one_or_none():
            errors.append(ValidationErrorDetail(
                field="vin",
                message=f"VIN码 {normalized_vin} 已存在，该车辆已注册"
            ))

    if normalized_license_plate:
        result = await db.execute(select(TestVehicle).where(TestVehicle.license_plate == normalized_license_plate))
        if result.scalar_one_or_none():
            errors.append(ValidationErrorDetail(
                field="license_plate",
                message=f"车牌号 {normalized_license_plate} 已存在"
            ))

    if data.insurance_expiry_date:
        insurance_error = validate_insurance_expiry(data.insurance_expiry_date)
        if insurance_error:
            errors.append(insurance_error)

    if data.test_expiry_date and data.test_expiry_date <= date.today():
        errors.append(ValidationErrorDetail(
            field="test_expiry_date",
            message="测试有效期截止日期必须晚于今天"
        ))

    config_errors = validate_vehicle_config(data.vehicle_config)
    errors.extend(config_errors)

    if data.manufacture_date and data.manufacture_date > date.today():
        errors.append(ValidationErrorDetail(
            field="manufacture_date",
            message="生产日期不能晚于今天"
        ))

    if data.registration_date and data.manufacture_date:
        if data.registration_date < data.manufacture_date:
            errors.append(ValidationErrorDetail(
                field="registration_date",
                message="注册日期不能早于生产日期"
            ))

    if errors:
        correction_notice = generate_correction_notice(errors, current_user.company_name)
        return VehicleRegistrationResponse(
            success=False,
            message="车辆注册资料校验未通过，请根据补正通知修正后重新提交",
            errors=errors,
            correction_notice=correction_notice
        )

    vehicle = TestVehicle(
        company_id=current_user.id,
        vin=normalized_vin,
        license_plate=normalized_license_plate,
        vehicle_model=normalized_vehicle_model,
        vehicle_type=data.vehicle_type,
        automation_level=normalized_automation_level,
        test_type=data.test_type,
        test_area=data.test_area,
        manufacture_date=data.manufacture_date,
        registration_date=data.registration_date,
        test_expiry_date=data.test_expiry_date,
        insurance_expiry_date=data.insurance_expiry_date,
        vehicle_config=data.vehicle_config,
        status="pending_review"
    )

    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)

    return VehicleRegistrationResponse(
        success=True,
        message="测试车辆注册提交成功，等待审核",
        vehicle_id=vehicle.id,
        vehicle=vehicle.to_dict()
    )


@router.get("/", response_model=List[Dict[str, Any]])
async def list_vehicles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(TestVehicle).where(TestVehicle.company_id == current_user.id)
    )
    vehicles = result.scalars().all()
    return [v.to_dict() for v in vehicles]


@router.get("/{vehicle_id}", response_model=Dict[str, Any])
async def get_vehicle(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(TestVehicle).where(
            TestVehicle.id == vehicle_id,
            TestVehicle.company_id == current_user.id
        )
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="车辆不存在或无权访问"
        )
    return vehicle.to_dict()
