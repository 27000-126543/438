from datetime import datetime, date
from typing import Optional, List, Dict, Any
import json
import re
import io
import csv

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, and_, func, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    DataCatalog,
    VehicleRealtimeData,
    Alarm,
    AccidentReport,
    TestVehicle,
    User,
)
from app.schemas.data import (
    DataCatalogCreate,
    DataCatalogUpdate,
    DataCatalogResponse,
    DesensitizationRule,
    DataDesensitizationConfig,
)

router = APIRouter(tags=["数据管理"])

DEFAULT_DESENSITIZATION_RULES = {
    "phone": {"pattern": r"(\d{3})\d{4}(\d{4})", "replacement": r"\1****\2"},
    "email": {"pattern": r"(\w{1,3})\w*@(\w+\.\w+)", "replacement": r"\1***@\2"},
    "vin": {"pattern": r"([A-Z0-9]{3})[A-Z0-9]{11}([A-Z0-9]{3})", "replacement": r"\1***********\2"},
    "license_plate": {"pattern": r"([\u4e00-\u9fa5][A-Z])[A-Z0-9]{3,4}([A-Z0-9])", "replacement": r"\1***\2"},
    "id_card": {"pattern": r"(\d{4})\d{10}(\d{4})", "replacement": r"\1**********\2"},
    "name": {"pattern": r"([\u4e00-\u9fa5]{1})[\u4e00-\u9fa5]+", "replacement": r"\1*"},
}

AUTHORIZATION_POLICIES = {
    "public": ["timestamp", "speed", "latitude", "longitude", "vehicle_type", "status"],
    "internal": ["timestamp", "speed", "latitude", "longitude", "vehicle_type", "status", "vin", "license_plate"],
    "confidential": ["timestamp", "speed", "latitude", "longitude", "vehicle_type", "status", "vin", "license_plate",
                     "driver_name", "phone", "email", "battery_level", "fuel_level", "sensor_data"],
}

DATA_TYPE_MAPPING = {
    "vehicle_realtime": VehicleRealtimeData,
    "alarm": Alarm,
    "accident": AccidentReport,
}


class DataQueryParams(BaseModel):
    data_type: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    vehicle_id: Optional[int] = None
    access_level: str = "internal"
    desensitize: bool = True


def desensitize_value(value: str, field_type: str) -> str:
    if not value or not isinstance(value, str):
        return value
    rules = DEFAULT_DESENSITIZATION_RULES.get(field_type)
    if not rules:
        return value
    return re.sub(rules["pattern"], rules["replacement"], value)


def apply_desensitization(data: Dict[str, Any], access_level: str, enabled: bool = True) -> Dict[str, Any]:
    if not enabled:
        return data

    allowed_fields = AUTHORIZATION_POLICIES.get(access_level, AUTHORIZATION_POLICIES["internal"])
    result = {}

    for key, value in data.items():
        if key not in allowed_fields:
            continue

        if isinstance(value, dict):
            result[key] = apply_desensitization(value, access_level, enabled)
        elif isinstance(value, list):
            result[key] = [
                apply_desensitization(item, access_level, enabled) if isinstance(item, dict) else item
                for item in value
            ]
        elif key in ["phone", "email", "vin", "license_plate", "id_card", "driver_name", "name"]:
            field_type = "name" if key in ["driver_name", "name"] else key
            result[key] = desensitize_value(str(value) if value else value, field_type)
        else:
            result[key] = value

    return result


def generate_catalog_code(data_type: str) -> str:
    now = datetime.utcnow()
    return f"CAT-{data_type.upper()}-{now.strftime('%Y%m%d%H%M%S')}"


@router.get("/catalogs", summary="获取数据目录列表", response_model=List[DataCatalogResponse])
async def list_catalogs(
    data_type: Optional[str] = None,
    access_level: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    try:
        query = select(DataCatalog)

        conditions = []
        if data_type:
            conditions.append(DataCatalog.data_type == data_type)
        if access_level:
            conditions.append(DataCatalog.access_level == access_level)
        if status:
            conditions.append(DataCatalog.status == status)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(DataCatalog.id.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        catalogs = result.scalars().all()

        return list(catalogs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据目录列表失败: {str(e)}")


@router.get("/catalogs/{catalog_id}", summary="获取数据目录详情", response_model=DataCatalogResponse)
async def get_catalog(
    catalog_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(DataCatalog).where(DataCatalog.id == catalog_id)
        )
        catalog = result.scalar_one_or_none()

        if not catalog:
            raise HTTPException(status_code=404, detail="数据目录不存在")

        return catalog
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据目录详情失败: {str(e)}")


@router.post("/catalogs", summary="创建数据目录", response_model=DataCatalogResponse)
async def create_catalog(
    data: DataCatalogCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        create_data = data.model_dump(exclude_unset=True)

        if not create_data.get("catalog_code"):
            create_data["catalog_code"] = generate_catalog_code(create_data.get("data_type", "custom"))

        existing_result = await db.execute(
            select(DataCatalog).where(DataCatalog.catalog_code == create_data["catalog_code"])
        )
        if existing_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="目录编码已存在")

        if not create_data.get("catalog_name"):
            data_type = create_data.get("data_type", "custom")
            data_type_names = {
                "vehicle_realtime": "车辆实时数据",
                "alarm": "告警数据",
                "accident": "事故数据",
                "custom": "自定义数据",
            }
            create_data["catalog_name"] = f"{data_type_names.get(data_type, data_type)}数据目录"

        if not create_data.get("desensitization_rules"):
            create_data["desensitization_rules"] = DEFAULT_DESENSITIZATION_RULES

        if "last_updated" not in create_data:
            create_data["last_updated"] = datetime.utcnow()

        catalog = DataCatalog(**create_data)
        db.add(catalog)
        await db.commit()
        await db.refresh(catalog)

        return catalog
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"创建数据目录失败: {str(e)}")


@router.put("/catalogs/{catalog_id}", summary="更新或创建数据目录", response_model=DataCatalogResponse)
async def update_catalog(
    catalog_id: int,
    data: DataCatalogUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(DataCatalog).where(DataCatalog.id == catalog_id)
        )
        catalog = result.scalar_one_or_none()

        update_data = data.model_dump(exclude_unset=True)

        if not catalog:
            create_data = update_data.copy()

            if "catalog_code" not in create_data or not create_data["catalog_code"]:
                create_data["catalog_code"] = generate_catalog_code(create_data.get("data_type", "custom"))

            if "catalog_name" not in create_data or not create_data["catalog_name"]:
                dt = create_data.get("data_type", "custom")
                data_type_names = {
                    "vehicle_realtime": "车辆实时数据",
                    "alarm": "告警数据",
                    "accident": "事故数据",
                    "custom": "自定义数据",
                }
                create_data["catalog_name"] = f"{data_type_names.get(dt, dt)}数据目录"

            if "desensitization_rules" not in create_data or not create_data["desensitization_rules"]:
                create_data["desensitization_rules"] = DEFAULT_DESENSITIZATION_RULES

            if "last_updated" not in create_data:
                create_data["last_updated"] = datetime.utcnow()

            existing_result = await db.execute(
                select(DataCatalog).where(DataCatalog.catalog_code == create_data["catalog_code"])
            )
            if existing_result.scalar_one_or_none():
                create_data["catalog_code"] = f"{create_data['catalog_code']}_{catalog_id}"

            create_data["id"] = catalog_id
            catalog = DataCatalog(**create_data)
            db.add(catalog)
        else:
            for key, value in update_data.items():
                setattr(catalog, key, value)

            catalog.updated_at = datetime.utcnow()
            if "last_updated" not in update_data:
                catalog.last_updated = datetime.utcnow()

        await db.commit()
        await db.refresh(catalog)

        return catalog
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"更新数据目录失败: {str(e)}")


@router.post("/catalogs/generate", summary="自动生成数据目录")
async def generate_data_catalog(
    data_type: Optional[str] = Query("vehicle_realtime", description="数据类型: vehicle_realtime, alarm, accident"),
    db: AsyncSession = Depends(get_db),
):
    model = DATA_TYPE_MAPPING.get(data_type)
    if not model:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}")

    count_result = await db.execute(select(func.count()).select_from(model))
    record_count = count_result.scalar() or 0

    time_range = {"start": None, "end": None}
    if hasattr(model, "timestamp"):
        min_result = await db.execute(select(func.min(model.timestamp)))
        max_result = await db.execute(select(func.max(model.timestamp)))
        time_range["start"] = min_result.scalar_one_or_none()
        time_range["end"] = max_result.scalar_one_or_none()
    elif hasattr(model, "created_at"):
        min_result = await db.execute(select(func.min(model.created_at)))
        max_result = await db.execute(select(func.max(model.created_at)))
        time_range["start"] = min_result.scalar_one_or_none()
        time_range["end"] = max_result.scalar_one_or_none()

    schema = {}
    for column in model.__table__.columns:
        schema[column.name] = {
            "type": str(column.type),
            "nullable": column.nullable,
            "primary_key": column.primary_key,
        }

    catalog_code = generate_catalog_code(data_type)
    data_type_names = {
        "vehicle_realtime": "车辆实时数据",
        "alarm": "告警数据",
        "accident": "事故数据",
    }

    catalog = DataCatalog(
        catalog_code=catalog_code,
        catalog_name=f"{data_type_names.get(data_type, data_type)}数据目录",
        data_type=data_type,
        data_source="system_automatic",
        description=f"自动生成的{data_type_names.get(data_type, data_type)}数据目录",
        storage_format="database",
        record_count=record_count,
        time_range_start=time_range["start"],
        time_range_end=time_range["end"],
        data_owner="system",
        access_level="internal",
        desensitization_enabled=True,
        desensitization_rules=DEFAULT_DESENSITIZATION_RULES,
        data_schema=schema,
        update_frequency="realtime",
        last_updated=datetime.utcnow(),
        status="active",
        tags=[data_type, "auto_generated"],
    )
    db.add(catalog)
    await db.commit()
    await db.refresh(catalog)

    return {
        "message": "数据目录生成成功",
        "catalog": catalog.to_dict(),
        "stats": {
            "record_count": record_count,
            "time_range_start": time_range["start"].isoformat() if time_range["start"] else None,
            "time_range_end": time_range["end"].isoformat() if time_range["end"] else None,
        },
    }


@router.get("/query", summary="按时间和类型查询数据（自动脱敏）")
async def query_data(
    data_type: str = Query(..., description="数据类型: vehicle_realtime, alarm, accident"),
    start_time: Optional[str] = Query(None, description="开始时间 ISO 格式"),
    end_time: Optional[str] = Query(None, description="结束时间 ISO 格式"),
    vehicle_id: Optional[int] = None,
    access_level: str = Query("internal", description="授权级别: public, internal, confidential"),
    desensitize: bool = Query(True, description="是否启用脱敏"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    model = DATA_TYPE_MAPPING.get(data_type)
    if not model:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}")

    if access_level not in AUTHORIZATION_POLICIES:
        raise HTTPException(status_code=400, detail=f"不支持的授权级别: {access_level}")

    query = select(model)

    conditions = []
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            if hasattr(model, "timestamp"):
                conditions.append(model.timestamp >= start_dt)
            elif hasattr(model, "created_at"):
                conditions.append(model.created_at >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="开始时间格式错误")

    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
            if hasattr(model, "timestamp"):
                conditions.append(model.timestamp <= end_dt)
            elif hasattr(model, "created_at"):
                conditions.append(model.created_at <= end_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="结束时间格式错误")

    if vehicle_id and hasattr(model, "vehicle_id"):
        conditions.append(model.vehicle_id == vehicle_id)

    if conditions:
        query = query.where(and_(*conditions))

    time_column = model.timestamp if hasattr(model, "timestamp") else model.created_at
    query = query.order_by(time_column.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    records = result.scalars().all()

    processed_records = []
    for record in records:
        record_dict = record.to_dict() if hasattr(record, "to_dict") else {
            c.name: getattr(record, c.name) for c in record.__table__.columns
        }
        for k, v in record_dict.items():
            if isinstance(v, datetime):
                record_dict[k] = v.isoformat()
            elif isinstance(v, date):
                record_dict[k] = v.isoformat()
        processed = apply_desensitization(record_dict, access_level, desensitize)
        processed_records.append(processed)

    count_query = select(func.count()).select_from(model)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    return {
        "total": total,
        "returned": len(processed_records),
        "data_type": data_type,
        "access_level": access_level,
        "desensitized": desensitize,
        "records": processed_records,
    }


@router.get("/export", summary="按时间和类型导出数据（自动脱敏）")
async def export_data(
    data_type: str = Query(..., description="数据类型: vehicle_realtime, alarm, accident"),
    start_time: Optional[str] = Query(None, description="开始时间 ISO 格式"),
    end_time: Optional[str] = Query(None, description="结束时间 ISO 格式"),
    vehicle_id: Optional[int] = None,
    access_level: str = Query("internal", description="授权级别: public, internal, confidential"),
    desensitize: bool = Query(True, description="是否启用脱敏"),
    format: str = Query("csv", description="导出格式: csv, json"),
    db: AsyncSession = Depends(get_db),
):
    model = DATA_TYPE_MAPPING.get(data_type)
    if not model:
        raise HTTPException(status_code=400, detail=f"不支持的数据类型: {data_type}")

    if access_level not in AUTHORIZATION_POLICIES:
        raise HTTPException(status_code=400, detail=f"不支持的授权级别: {access_level}")

    if format not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail=f"不支持的导出格式: {format}")

    query = select(model)

    conditions = []
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            if hasattr(model, "timestamp"):
                conditions.append(model.timestamp >= start_dt)
            elif hasattr(model, "created_at"):
                conditions.append(model.created_at >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="开始时间格式错误")

    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
            if hasattr(model, "timestamp"):
                conditions.append(model.timestamp <= end_dt)
            elif hasattr(model, "created_at"):
                conditions.append(model.created_at <= end_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="结束时间格式错误")

    if vehicle_id and hasattr(model, "vehicle_id"):
        conditions.append(model.vehicle_id == vehicle_id)

    if conditions:
        query = query.where(and_(*conditions))

    time_column = model.timestamp if hasattr(model, "timestamp") else model.created_at
    query = query.order_by(time_column.desc()).limit(50000)
    result = await db.execute(query)
    records = result.scalars().all()

    processed_records = []
    allowed_fields = AUTHORIZATION_POLICIES.get(access_level, AUTHORIZATION_POLICIES["internal"])

    for record in records:
        record_dict = record.to_dict() if hasattr(record, "to_dict") else {
            c.name: getattr(record, c.name) for c in record.__table__.columns
        }
        for k, v in record_dict.items():
            if isinstance(v, (datetime, date)):
                record_dict[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                record_dict[k] = json.dumps(v, ensure_ascii=False)
        processed = apply_desensitization(record_dict, access_level, desensitize)
        processed_records.append(processed)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if format == "json":
        content = json.dumps(processed_records, ensure_ascii=False, indent=2)
        media_type = "application/json"
        filename = f"{data_type}_data_{timestamp}.json"
        return StreamingResponse(
            iter([content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        output = io.StringIO()
        if processed_records:
            fieldnames = [k for k in processed_records[0].keys() if k in allowed_fields]
            if not fieldnames:
                fieldnames = list(processed_records[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for record in processed_records:
                filtered = {k: v for k, v in record.items() if k in fieldnames}
                writer.writerow(filtered)

        media_type = "text/csv"
        filename = f"{data_type}_data_{timestamp}.csv"
        content = output.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


@router.post("/desensitize", summary="测试数据脱敏")
async def test_desensitization(
    data: Dict[str, Any],
    access_level: str = Query("internal", description="授权级别: public, internal, confidential"),
):
    if access_level not in AUTHORIZATION_POLICIES:
        raise HTTPException(status_code=400, detail=f"不支持的授权级别: {access_level}")

    result = apply_desensitization(data, access_level, True)

    return {
        "original": data,
        "desensitized": result,
        "access_level": access_level,
        "allowed_fields": AUTHORIZATION_POLICIES[access_level],
    }
