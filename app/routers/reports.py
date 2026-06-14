from datetime import datetime, date, timedelta
from typing import Optional, List
import json
import io
import csv

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, and_, or_, func, cast, Date as SqlDate
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    DailyReport,
    TestVehicle,
    VehicleRealtimeData,
    AccidentReport,
    RoadsideDevice,
    Alarm,
    MaintenanceWorkOrder,
    User,
    TestRoute,
)
from app.schemas.report import (
    DailyReportCreate,
    DailyReportResponse,
    VehicleStatistics,
    AlarmStatistics,
    SafetyStatistics,
    DeviceStatistics,
    MultiDimensionReport,
    RegionMetrics,
    RegionComparisonResponse,
    DailyRegionMetrics,
    TrendAnalysis,
    RegionTrendResponse,
)

router = APIRouter(tags=["运营报表"])


def generate_report_number(company_id: int, report_date: date) -> str:
    return f"RPT-{company_id}-{report_date.strftime('%Y%m%d')}"


@router.post("/generate-daily", summary="生成每日运营统计报表")
async def generate_daily_report(
    company_id: Optional[int] = None,
    report_date: Optional[str] = Query(None, description="报表日期 YYYY-MM-DD，默认为今天"),
    region: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if report_date:
        try:
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")
    else:
        target_date = date.today()

    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    companies = []
    if company_id:
        company_result = await db.execute(
            select(User).where(User.id == company_id)
        )
        company = company_result.scalar_one_or_none()
        if not company:
            raise HTTPException(status_code=404, detail="企业不存在")
        companies = [company]
    else:
        companies_result = await db.execute(select(User).where(User.role == "enterprise"))
        companies = companies_result.scalars().all()

    if not companies:
        raise HTTPException(status_code=404, detail="没有找到企业")

    generated_reports = []

    for company in companies:
        existing_result = await db.execute(
            select(DailyReport).where(
                and_(
                    DailyReport.company_id == company.id,
                    DailyReport.report_date == target_date,
                    DailyReport.region == region,
                )
            )
        )
        existing_report = existing_result.scalar_one_or_none()

        vehicles_query = select(TestVehicle).where(TestVehicle.company_id == company.id)
        if region:
            vehicles_query = vehicles_query.where(TestVehicle.test_area == region)
        vehicles_result = await db.execute(vehicles_query)
        all_vehicles = vehicles_result.scalars().all()
        total_vehicles = len(all_vehicles)
        vehicle_ids = [v.id for v in all_vehicles]

        active_count = 0
        total_test_distance = 0.0
        total_test_duration = 0.0
        autopilot_distance = 0.0
        manual_distance = 0.0
        max_speed = None
        speeds = []

        if vehicle_ids:
            data_result = await db.execute(
                select(VehicleRealtimeData).where(
                    and_(
                        VehicleRealtimeData.vehicle_id.in_(vehicle_ids),
                        VehicleRealtimeData.timestamp >= day_start,
                        VehicleRealtimeData.timestamp < day_end,
                    )
                )
            )
            realtime_data = data_result.scalars().all()

            active_vehicle_ids = set()
            last_mileage = {}
            prev_points = {}

            for data in realtime_data:
                active_vehicle_ids.add(data.vehicle_id)
                if data.speed is not None:
                    speeds.append(data.speed)
                    if max_speed is None or data.speed > max_speed:
                        max_speed = data.speed

                prev = prev_points.get(data.vehicle_id)
                if prev and prev.latitude and prev.longitude and data.latitude and data.longitude:
                    from math import radians, sin, cos, sqrt, atan2
                    EARTH_RADIUS_KM = 6371.0
                    lat1, lon1 = radians(prev.latitude), radians(prev.longitude)
                    lat2, lon2 = radians(data.latitude), radians(data.longitude)
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
                    c = 2 * atan2(sqrt(a), sqrt(1 - a))
                    dist_km = EARTH_RADIUS_KM * c
                    total_test_distance += dist_km
                    if data.autopilot_enabled:
                        autopilot_distance += dist_km
                    else:
                        manual_distance += dist_km

                prev_points[data.vehicle_id] = data

            active_count = len(active_vehicle_ids)

            if realtime_data:
                timestamps = [d.timestamp for d in realtime_data if d.timestamp]
                if timestamps:
                    duration_hours = (max(timestamps) - min(timestamps)).total_seconds() / 3600.0
                    total_test_duration = max(duration_hours, 0.0)

        average_speed = sum(speeds) / len(speeds) if speeds else 0.0

        alarms_query = select(Alarm).where(
            and_(
                Alarm.company_id == company.id,
                Alarm.created_at >= day_start,
                Alarm.created_at < day_end,
            )
        )
        if region and vehicle_ids:
            alarms_query = alarms_query.where(Alarm.vehicle_id.in_(vehicle_ids))
        elif region:
            alarms_query = alarms_query.join(TestVehicle).where(TestVehicle.test_area == region)
        alarms_result = await db.execute(alarms_query)
        alarms = alarms_result.scalars().all()
        total_alarms = len(alarms)
        critical_alarms = len([a for a in alarms if a.alarm_level == "critical"])
        warning_alarms = len([a for a in alarms if a.alarm_level == "warning"])
        info_alarms = len([a for a in alarms if a.alarm_level == "info"])
        alarms_resolved = len([a for a in alarms if a.status == "resolved"])

        accidents_query = select(AccidentReport).where(
            and_(
                AccidentReport.company_id == company.id,
                AccidentReport.accident_time >= day_start,
                AccidentReport.accident_time < day_end,
            )
        )
        if region and vehicle_ids:
            accidents_query = accidents_query.where(AccidentReport.vehicle_id.in_(vehicle_ids))
        elif region:
            accidents_query = accidents_query.join(TestVehicle).where(TestVehicle.test_area == region)
        accidents_result = await db.execute(accidents_query)
        accidents = accidents_result.scalars().all()
        new_accidents = len(accidents)

        ongoing_accidents_query = select(AccidentReport).where(
            and_(
                AccidentReport.company_id == company.id,
                AccidentReport.status.in_(["under_investigation", "pending"]),
            )
        )
        if region and vehicle_ids:
            ongoing_accidents_query = ongoing_accidents_query.where(AccidentReport.vehicle_id.in_(vehicle_ids))
        elif region:
            ongoing_accidents_query = ongoing_accidents_query.join(TestVehicle).where(TestVehicle.test_area == region)
        ongoing_accidents_result = await db.execute(ongoing_accidents_query)
        ongoing_accidents = len(ongoing_accidents_result.scalars().all())

        if total_test_distance > 0:
            accident_rate = (new_accidents / total_test_distance) * 1000.0
        else:
            accident_rate = 0.0

        devices_query = select(RoadsideDevice).join(
            TestRoute, RoadsideDevice.route_id == TestRoute.id
        ).where(TestRoute.company_id == company.id)
        if region:
            devices_query = devices_query.where(TestRoute.test_area == region)
        all_devices_result = await db.execute(devices_query)
        all_devices = all_devices_result.scalars().all()
        total_devices = len(all_devices)
        online_devices = len([d for d in all_devices if d.status == "online"])
        device_online_rate = (online_devices / total_devices * 100) if total_devices > 0 else 0.0

        maintenance_query = select(MaintenanceWorkOrder).where(
            and_(
                MaintenanceWorkOrder.company_id == company.id,
                MaintenanceWorkOrder.created_at >= day_start,
                MaintenanceWorkOrder.created_at < day_end,
            )
        )
        if region:
            maintenance_query = maintenance_query.join(
                RoadsideDevice, MaintenanceWorkOrder.device_id == RoadsideDevice.id
            ).join(
                TestRoute, RoadsideDevice.route_id == TestRoute.id
            ).where(TestRoute.test_area == region)
        maintenance_result = await db.execute(maintenance_query)
        maintenance_orders = maintenance_result.scalars().all()
        total_maintenance = len(maintenance_orders)
        completed_maintenance = len([m for m in maintenance_orders if m.status == "completed"])
        pending_maintenance = len([m for m in maintenance_orders if m.status in ["pending", "assigned"]])

        if total_vehicles > 0 and total_devices > 0:
            operational_efficiency = (
                (active_count / total_vehicles) * 0.4
                + (device_online_rate / 100) * 0.3
                + ((1 - min(accident_rate / 10, 1)) * 0.3)
            ) * 100
        else:
            operational_efficiency = 0.0

        if total_alarms > 0:
            safety_index = max(0.0, 100.0 - (critical_alarms * 20 + warning_alarms * 5) / total_alarms * 50)
        else:
            safety_index = 100.0

        if existing_report:
            existing_report.total_vehicles = total_vehicles
            existing_report.active_vehicles = active_count
            existing_report.total_test_distance = round(total_test_distance, 2)
            existing_report.total_test_duration = round(total_test_duration, 2)
            existing_report.autopilot_distance = round(autopilot_distance, 2)
            existing_report.manual_distance = round(manual_distance, 2)
            existing_report.max_speed_recorded = round(max_speed, 2) if max_speed else None
            existing_report.average_speed = round(average_speed, 2)
            existing_report.total_alarms = total_alarms
            existing_report.critical_alarms = critical_alarms
            existing_report.warning_alarms = warning_alarms
            existing_report.info_alarms = info_alarms
            existing_report.alarms_resolved = alarms_resolved
            existing_report.accident_rate = round(accident_rate, 4)
            existing_report.new_accidents = new_accidents
            existing_report.ongoing_accidents = ongoing_accidents
            existing_report.total_maintenance_orders = total_maintenance
            existing_report.completed_maintenance = completed_maintenance
            existing_report.pending_maintenance = pending_maintenance
            existing_report.total_devices = total_devices
            existing_report.online_devices = online_devices
            existing_report.device_online_rate = round(device_online_rate, 2)
            existing_report.operational_efficiency = round(operational_efficiency, 2)
            existing_report.safety_index = round(safety_index, 2)
            existing_report.generated_at = datetime.utcnow()
            existing_report.updated_at = datetime.utcnow()
            report = existing_report
        else:
            report = DailyReport(
                company_id=company.id,
                report_date=target_date,
                report_type="daily",
                region=region,
                total_vehicles=total_vehicles,
                active_vehicles=active_count,
                total_test_distance=round(total_test_distance, 2),
                total_test_duration=round(total_test_duration, 2),
                autopilot_distance=round(autopilot_distance, 2),
                manual_distance=round(manual_distance, 2),
                max_speed_recorded=round(max_speed, 2) if max_speed else None,
                average_speed=round(average_speed, 2),
                total_alarms=total_alarms,
                critical_alarms=critical_alarms,
                warning_alarms=warning_alarms,
                info_alarms=info_alarms,
                alarms_resolved=alarms_resolved,
                accident_rate=round(accident_rate, 4),
                new_accidents=new_accidents,
                ongoing_accidents=ongoing_accidents,
                total_maintenance_orders=total_maintenance,
                completed_maintenance=completed_maintenance,
                pending_maintenance=pending_maintenance,
                total_devices=total_devices,
                online_devices=online_devices,
                device_online_rate=round(device_online_rate, 2),
                operational_efficiency=round(operational_efficiency, 2),
                safety_index=round(safety_index, 2),
                generated_by="system",
            )
            db.add(report)

        await db.commit()
        await db.refresh(report)
        generated_reports.append(report)

    return {
        "message": f"成功生成 {len(generated_reports)} 份日报表",
        "report_date": target_date.isoformat(),
        "reports": [r.to_dict() for r in generated_reports],
    }


@router.get("", summary="获取运营报表列表", response_model=List[DailyReportResponse])
async def list_reports(
    company_id: Optional[int] = None,
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    region: Optional[str] = None,
    report_type: Optional[str] = "daily",
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(DailyReport)

    conditions = []
    if company_id:
        conditions.append(DailyReport.company_id == company_id)
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            conditions.append(DailyReport.report_date >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="开始日期格式错误")
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
            conditions.append(DailyReport.report_date <= end_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="结束日期格式错误")
    if region:
        conditions.append(DailyReport.region == region)
    if report_type:
        conditions.append(DailyReport.report_type == report_type)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(DailyReport.report_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    reports = result.scalars().all()

    return reports


@router.get("/summary", summary="获取指定日期范围的汇总统计")
async def get_report_summary(
    company_id: Optional[int] = None,
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    region: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误")

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    query = select(DailyReport).where(
        and_(
            DailyReport.report_date >= start_dt,
            DailyReport.report_date <= end_dt,
        )
    )

    if company_id:
        query = query.where(DailyReport.company_id == company_id)
    if region:
        query = query.where(DailyReport.region == region)

    result = await db.execute(query)
    reports = result.scalars().all()

    if not reports:
        return {
            "start_date": start_date,
            "end_date": end_date,
            "report_count": 0,
            "summary": None,
        }

    summary = {
        "total_active_vehicles_sum": sum(r.active_vehicles for r in reports),
        "avg_active_vehicles": round(sum(r.active_vehicles for r in reports) / len(reports), 2),
        "total_test_distance_sum": round(sum(r.total_test_distance for r in reports), 2),
        "avg_daily_distance": round(sum(r.total_test_distance for r in reports) / len(reports), 2),
        "total_autopilot_distance": round(sum(r.autopilot_distance for r in reports), 2),
        "total_manual_distance": round(sum(r.manual_distance for r in reports), 2),
        "total_alarms_sum": sum(r.total_alarms for r in reports),
        "critical_alarms_sum": sum(r.critical_alarms for r in reports),
        "warning_alarms_sum": sum(r.warning_alarms for r in reports),
        "new_accidents_sum": sum(r.new_accidents for r in reports),
        "avg_accident_rate": round(sum(r.accident_rate for r in reports) / len(reports), 4),
        "avg_device_online_rate": round(sum(r.device_online_rate for r in reports) / len(reports), 2),
        "avg_operational_efficiency": round(sum(r.operational_efficiency for r in reports) / len(reports), 2),
        "avg_safety_index": round(sum(r.safety_index for r in reports) / len(reports), 2),
        "total_maintenance_orders_sum": sum(r.total_maintenance_orders for r in reports),
        "completed_maintenance_sum": sum(r.completed_maintenance for r in reports),
    }

    return {
        "start_date": start_date,
        "end_date": end_date,
        "report_count": len(reports),
        "summary": summary,
    }


@router.get("/export", summary="按区域和日期导出运营报表")
async def export_reports(
    company_id: Optional[int] = None,
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD，默认30天前"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD，默认今天"),
    region: Optional[str] = None,
    regions: Optional[List[str]] = Query(None, description="区域列表，可传多个，与region二选一"),
    format: Optional[str] = Query("csv", description="导出格式: csv, json"),
    db: AsyncSession = Depends(get_db),
):
    try:
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        else:
            start_dt = date.today() - timedelta(days=30)
            start_date = start_dt.isoformat()

        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            end_dt = date.today()
            end_date = end_dt.isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误")

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    if not format:
        format = "csv"

    if format not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail=f"不支持的导出格式: {format}")

    query = select(DailyReport).options(
        selectinload(DailyReport.company)
    ).where(
        and_(
            DailyReport.report_date >= start_dt,
            DailyReport.report_date <= end_dt,
        )
    )

    if company_id:
        query = query.where(DailyReport.company_id == company_id)
    if region:
        query = query.where(DailyReport.region == region)
    if regions:
        query = query.where(DailyReport.region.in_(regions))

    query = query.order_by(DailyReport.report_date)
    result = await db.execute(query)
    reports = result.scalars().all()

    report_dicts = []
    for r in reports:
        d = r.to_dict()
        for k, v in d.items():
            if isinstance(v, (datetime, date)):
                d[k] = v.isoformat()
        report_dicts.append(d)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if format == "json":
        content = json.dumps(report_dicts, ensure_ascii=False, indent=2)
        media_type = "application/json"
        filename = f"daily_reports_{start_date}_{end_date}_{timestamp}.json"
        return StreamingResponse(
            iter([content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        output = io.StringIO()
        if report_dicts:
            fieldnames = list(report_dicts[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for record in report_dicts:
                writer.writerow(record)

        media_type = "text/csv"
        filename = f"daily_reports_{start_date}_{end_date}_{timestamp}.csv"
        content = output.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


@router.get("/statistics/overview", summary="获取实时概览统计")
async def get_overview_statistics(
    company_id: Optional[int] = None,
    region: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    vehicles_query = select(TestVehicle)
    if company_id:
        vehicles_query = vehicles_query.where(TestVehicle.company_id == company_id)
    if region:
        vehicles_query = vehicles_query.where(TestVehicle.test_area == region)
    vehicles_result = await db.execute(vehicles_query)
    all_vehicles = vehicles_result.scalars().all()
    total_vehicles = len(all_vehicles)

    today = date.today()
    day_start = datetime.combine(today, datetime.min.time())
    active_count = 0
    today_distance = 0.0

    vehicle_ids = [v.id for v in all_vehicles]
    if vehicle_ids:
        today_data = await db.execute(
            select(VehicleRealtimeData).where(
                and_(
                    VehicleRealtimeData.vehicle_id.in_(vehicle_ids),
                    VehicleRealtimeData.timestamp >= day_start,
                )
            )
        )
        today_records = today_data.scalars().all()
        active_count = len(set(r.vehicle_id for r in today_records))

    devices_query = select(RoadsideDevice).join(
        TestRoute, RoadsideDevice.route_id == TestRoute.id
    )
    if company_id:
        devices_query = devices_query.where(TestRoute.company_id == company_id)
    if region:
        devices_query = devices_query.where(TestRoute.test_area == region)
    devices_result = await db.execute(devices_query)
    all_devices = devices_result.scalars().all()
    total_devices = len(all_devices)
    online_devices = len([d for d in all_devices if d.status == "online"])
    device_online_rate = (online_devices / total_devices * 100) if total_devices > 0 else 0.0

    accident_query = select(AccidentReport)
    if company_id:
        accident_query = accident_query.where(AccidentReport.company_id == company_id)
    if region and vehicle_ids:
        accident_query = accident_query.where(AccidentReport.vehicle_id.in_(vehicle_ids))
    elif region:
        accident_query = accident_query.join(TestVehicle).where(TestVehicle.test_area == region)
    accidents_result = await db.execute(accident_query)
    total_accidents = len(accidents_result.scalars().all())

    total_distance = 0.0
    mileage_query = select(func.sum(TestVehicle.mileage))
    if company_id:
        mileage_query = mileage_query.where(TestVehicle.company_id == company_id)
    if region:
        mileage_query = mileage_query.where(TestVehicle.test_area == region)
    mileage_result = await db.execute(mileage_query)
    total_distance = mileage_result.scalar() or 0.0

    if total_distance > 0:
        accident_rate = (total_accidents / max(total_distance, 1)) * 1000.0
    else:
        accident_rate = 0.0

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "region": region,
        "statistics": {
            "total_vehicles": total_vehicles,
            "active_vehicles_today": active_count,
            "total_devices": total_devices,
            "online_devices": online_devices,
            "device_online_rate": round(device_online_rate, 2),
            "total_accidents": total_accidents,
            "accident_rate_per_1000km": round(accident_rate, 4),
            "total_test_distance": round(total_distance, 2),
        },
    }


@router.get("/compare-regions", response_model=RegionComparisonResponse, summary="多区域数据对比")
async def compare_regions(
    company_id: Optional[int] = None,
    report_date: Optional[str] = Query(None, description="对比日期 YYYY-MM-DD，默认今天"),
    regions: Optional[List[str]] = Query(None, description="区域列表，可传多个"),
    db: AsyncSession = Depends(get_db),
):
    if report_date:
        try:
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")
    else:
        target_date = date.today()

    if not regions:
        raise HTTPException(status_code=400, detail="请至少指定一个区域")

    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    regions_list = list(regions)
    all_metrics = []

    for region in regions_list:
        vehicles_query = select(TestVehicle)
        if company_id:
            vehicles_query = vehicles_query.where(TestVehicle.company_id == company_id)
        vehicles_query = vehicles_query.where(TestVehicle.test_area == region)
        vehicles_result = await db.execute(vehicles_query)
        all_vehicles = vehicles_result.scalars().all()
        total_vehicles = len(all_vehicles)
        vehicle_ids = [v.id for v in all_vehicles]

        active_count = 0
        total_test_distance = 0.0
        if vehicle_ids:
            data_result = await db.execute(
                select(VehicleRealtimeData).where(
                    and_(
                        VehicleRealtimeData.vehicle_id.in_(vehicle_ids),
                        VehicleRealtimeData.timestamp >= day_start,
                        VehicleRealtimeData.timestamp < day_end,
                    )
                )
            )
            realtime_data = data_result.scalars().all()
            active_count = len(set(d.vehicle_id for d in realtime_data))

            prev_points = {}
            for data in realtime_data:
                prev = prev_points.get(data.vehicle_id)
                if prev and prev.latitude and prev.longitude and data.latitude and data.longitude:
                    from math import radians, sin, cos, sqrt, atan2
                    EARTH_RADIUS_KM = 6371.0
                    lat1, lon1 = radians(prev.latitude), radians(prev.longitude)
                    lat2, lon2 = radians(data.latitude), radians(data.longitude)
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
                    c = 2 * atan2(sqrt(a), sqrt(1 - a))
                    total_test_distance += EARTH_RADIUS_KM * c
                prev_points[data.vehicle_id] = data

        alarms_query = select(Alarm).where(
            and_(
                Alarm.created_at >= day_start,
                Alarm.created_at < day_end,
            )
        )
        if company_id:
            alarms_query = alarms_query.where(Alarm.company_id == company_id)
        if vehicle_ids:
            alarms_query = alarms_query.where(Alarm.vehicle_id.in_(vehicle_ids))
        else:
            alarms_query = alarms_query.join(TestVehicle).where(
                and_(TestVehicle.test_area == region,
                     TestVehicle.company_id == company_id if company_id else True)
            )
        alarms_result = await db.execute(alarms_query)
        alarms = alarms_result.scalars().all()
        total_alarms = len(alarms)
        critical_alarms = len([a for a in alarms if a.alarm_level == "critical"])

        accidents_query = select(AccidentReport).where(
            and_(
                AccidentReport.accident_time >= day_start,
                AccidentReport.accident_time < day_end,
            )
        )
        if company_id:
            accidents_query = accidents_query.where(AccidentReport.company_id == company_id)
        if vehicle_ids:
            accidents_query = accidents_query.where(AccidentReport.vehicle_id.in_(vehicle_ids))
        else:
            accidents_query = accidents_query.join(TestVehicle).where(
                and_(TestVehicle.test_area == region,
                     TestVehicle.company_id == company_id if company_id else True)
            )
        accidents_result = await db.execute(accidents_query)
        new_accidents = len(accidents_result.scalars().all())

        accident_rate = (new_accidents / max(total_test_distance, 1) * 1000.0) if total_test_distance > 0 else 0.0

        devices_query = select(RoadsideDevice).join(
            TestRoute, RoadsideDevice.route_id == TestRoute.id
        )
        if company_id:
            devices_query = devices_query.where(TestRoute.company_id == company_id)
        devices_query = devices_query.where(TestRoute.test_area == region)
        devices_result = await db.execute(devices_query)
        all_devices = devices_result.scalars().all()
        total_devices = len(all_devices)
        online_devices = len([d for d in all_devices if d.status == "online"])
        device_online_rate = (online_devices / total_devices * 100) if total_devices > 0 else 0.0

        all_metrics.append(RegionMetrics(
            region=region,
            total_vehicles=total_vehicles,
            active_vehicles=active_count,
            total_test_distance=round(total_test_distance, 2),
            total_alarms=total_alarms,
            critical_alarms=critical_alarms,
            accident_rate=round(accident_rate, 4),
            total_devices=total_devices,
            online_devices=online_devices,
            device_online_rate=round(device_online_rate, 2),
            new_accidents=new_accidents
        ))

    best_active = max(all_metrics, key=lambda x: x.active_vehicles) if all_metrics else None
    best_distance = max(all_metrics, key=lambda x: x.total_test_distance) if all_metrics else None
    best_device_rate = max(all_metrics, key=lambda x: x.device_online_rate) if all_metrics else None
    lowest_accident = min(all_metrics, key=lambda x: x.accident_rate) if all_metrics else None

    comparison_summary = {
        "total_regions_compared": len(all_metrics),
        "best_active_vehicles": best_active.region if best_active else None,
        "best_test_distance": best_distance.region if best_distance else None,
        "best_device_online_rate": best_device_rate.region if best_device_rate else None,
        "lowest_accident_rate": lowest_accident.region if lowest_accident else None,
        "rankings": {
            "active_vehicles": [{"region": m.region, "value": m.active_vehicles} for m in sorted(all_metrics, key=lambda x: x.active_vehicles, reverse=True)],
            "total_alarms": [{"region": m.region, "value": m.total_alarms} for m in sorted(all_metrics, key=lambda x: x.total_alarms, reverse=True)],
            "accident_rate": [{"region": m.region, "value": m.accident_rate} for m in sorted(all_metrics, key=lambda x: x.accident_rate)],
            "device_online_rate": [{"region": m.region, "value": m.device_online_rate} for m in sorted(all_metrics, key=lambda x: x.device_online_rate, reverse=True)],
        }
    }

    return RegionComparisonResponse(
        report_date=target_date,
        regions=regions_list,
        metrics=all_metrics,
        comparison_summary=comparison_summary
    )


async def calculate_region_metrics_for_date(
    db: AsyncSession,
    target_date: date,
    region: str,
    company_id: Optional[int] = None
) -> DailyRegionMetrics:
    from app.schemas.report import DailyRegionMetrics

    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    vehicles_query = select(TestVehicle)
    if company_id:
        vehicles_query = vehicles_query.where(TestVehicle.company_id == company_id)
    vehicles_query = vehicles_query.where(TestVehicle.test_area == region)
    vehicles_result = await db.execute(vehicles_query)
    all_vehicles = vehicles_result.scalars().all()
    total_vehicles = len(all_vehicles)
    vehicle_ids = [v.id for v in all_vehicles]

    active_count = 0
    total_test_distance = 0.0
    if vehicle_ids:
        data_result = await db.execute(
            select(VehicleRealtimeData).where(
                and_(
                    VehicleRealtimeData.vehicle_id.in_(vehicle_ids),
                    VehicleRealtimeData.timestamp >= day_start,
                    VehicleRealtimeData.timestamp < day_end,
                )
            )
        )
        realtime_data = data_result.scalars().all()
        active_count = len(set(d.vehicle_id for d in realtime_data))

        prev_points = {}
        for data in realtime_data:
            prev = prev_points.get(data.vehicle_id)
            if prev and prev.latitude and prev.longitude and data.latitude and data.longitude:
                from math import radians, sin, cos, sqrt, atan2
                EARTH_RADIUS_KM = 6371.0
                lat1, lon1 = radians(prev.latitude), radians(prev.longitude)
                lat2, lon2 = radians(data.latitude), radians(data.longitude)
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                total_test_distance += EARTH_RADIUS_KM * c
            prev_points[data.vehicle_id] = data

    alarms_query = select(Alarm).where(
        and_(
            Alarm.created_at >= day_start,
            Alarm.created_at < day_end,
        )
    )
    if company_id:
        alarms_query = alarms_query.where(Alarm.company_id == company_id)
    if vehicle_ids:
        alarms_query = alarms_query.where(Alarm.vehicle_id.in_(vehicle_ids))
    else:
        alarms_query = alarms_query.join(TestVehicle).where(
            and_(TestVehicle.test_area == region,
                 TestVehicle.company_id == company_id if company_id else True)
        )
    alarms_result = await db.execute(alarms_query)
    alarms = alarms_result.scalars().all()
    total_alarms = len(alarms)
    critical_alarms = len([a for a in alarms if a.alarm_level == "critical"])

    accidents_query = select(AccidentReport).where(
        and_(
            AccidentReport.accident_time >= day_start,
            AccidentReport.accident_time < day_end,
        )
    )
    if company_id:
        accidents_query = accidents_query.where(AccidentReport.company_id == company_id)
    if vehicle_ids:
        accidents_query = accidents_query.where(AccidentReport.vehicle_id.in_(vehicle_ids))
    else:
        accidents_query = accidents_query.join(TestVehicle).where(
            and_(TestVehicle.test_area == region,
                 TestVehicle.company_id == company_id if company_id else True)
        )
    accidents_result = await db.execute(accidents_query)
    new_accidents = len(accidents_result.scalars().all())

    accident_rate = (new_accidents / max(total_test_distance, 1) * 1000.0) if total_test_distance > 0 else 0.0

    devices_query = select(RoadsideDevice).join(
        TestRoute, RoadsideDevice.route_id == TestRoute.id
    )
    if company_id:
        devices_query = devices_query.where(TestRoute.company_id == company_id)
    devices_query = devices_query.where(TestRoute.test_area == region)
    devices_result = await db.execute(devices_query)
    all_devices = devices_result.scalars().all()
    total_devices = len(all_devices)
    online_devices = len([d for d in all_devices if d.status == "online"])
    device_online_rate = (online_devices / total_devices * 100) if total_devices > 0 else 0.0

    day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    dow = target_date.weekday()

    return DailyRegionMetrics(
        report_date=target_date,
        region=region,
        total_vehicles=total_vehicles,
        active_vehicles=active_count,
        total_test_distance=round(total_test_distance, 2),
        total_alarms=total_alarms,
        critical_alarms=critical_alarms,
        accident_rate=round(accident_rate, 4),
        total_devices=total_devices,
        online_devices=online_devices,
        device_online_rate=round(device_online_rate, 2),
        new_accidents=new_accidents,
        day_of_week=day_names[dow],
        is_weekend=dow >= 5
    )


def calculate_trend_analysis(
    metric_name: str,
    region: str,
    daily_data: List[DailyRegionMetrics]
) -> TrendAnalysis:
    from app.schemas.report import TrendAnalysis

    metric_map = {
        "active_vehicles": lambda x: x.active_vehicles,
        "total_test_distance": lambda x: x.total_test_distance,
        "total_alarms": lambda x: x.total_alarms,
        "accident_rate": lambda x: x.accident_rate,
        "device_online_rate": lambda x: x.device_online_rate,
    }

    getter = metric_map.get(metric_name)
    if not getter:
        return TrendAnalysis(
            metric_name=metric_name,
            region=region,
            values=[],
            trend_direction="unknown"
        )

    values = []
    raw_values = []
    for data in daily_data:
        val = getter(data)
        values.append({
            "date": data.report_date.isoformat(),
            "value": val,
            "day_of_week": data.day_of_week
        })
        raw_values.append(val)

    if not raw_values:
        return TrendAnalysis(
            metric_name=metric_name,
            region=region,
            values=values,
            trend_direction="unknown"
        )

    max_val = max(raw_values)
    min_val = min(raw_values)
    avg_val = sum(raw_values) / len(raw_values)

    max_idx = raw_values.index(max_val)
    min_idx = raw_values.index(min_val)
    max_date = daily_data[max_idx].report_date
    min_date = daily_data[min_idx].report_date

    volatility = 0.0
    if len(raw_values) > 1 and avg_val > 0:
        variance = sum((v - avg_val) ** 2 for v in raw_values) / len(raw_values)
        std_dev = variance ** 0.5
        volatility = round(std_dev / avg_val * 100, 2)

    trend_direction = "stable"
    if len(raw_values) >= 3:
        first_half = sum(raw_values[:len(raw_values)//2]) / (len(raw_values)//2)
        second_half = sum(raw_values[len(raw_values)//2:]) / len(raw_values[len(raw_values)//2:])
        if second_half > first_half * 1.1:
            trend_direction = "rising"
        elif second_half < first_half * 0.9:
            trend_direction = "falling"

    return TrendAnalysis(
        metric_name=metric_name,
        region=region,
        values=values,
        max_value=round(max_val, 4) if isinstance(max_val, float) else max_val,
        min_value=round(min_val, 4) if isinstance(min_val, float) else min_val,
        avg_value=round(avg_val, 4) if isinstance(avg_val, float) else avg_val,
        max_date=max_date,
        min_date=min_date,
        volatility=volatility,
        trend_direction=trend_direction
    )


@router.get("/region-trend", response_model=RegionTrendResponse, summary="连续多天区域趋势视图")
async def get_region_trend(
    company_id: Optional[int] = None,
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    regions: Optional[List[str]] = Query(None, description="区域列表，可传多个"),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.report import RegionTrendResponse

    try:
        s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        e_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")

    if s_date > e_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    if (e_date - s_date).days > 365:
        raise HTTPException(status_code=400, detail="查询范围不能超过365天")

    if not regions:
        raise HTTPException(status_code=400, detail="请至少指定一个区域")

    regions_list = list(regions)
    daily_metrics: List[DailyRegionMetrics] = []

    current_date = s_date
    while current_date <= e_date:
        for region in regions_list:
            metrics = await calculate_region_metrics_for_date(
                db, current_date, region, company_id
            )
            daily_metrics.append(metrics)
        current_date += timedelta(days=1)

    trend_analysis = []
    volatility_summary = {}

    for region in regions_list:
        region_data = [m for m in daily_metrics if m.region == region]
        volatility_summary[region] = {}

        for metric_name in ["active_vehicles", "total_test_distance", "total_alarms", "accident_rate", "device_online_rate"]:
            trend = calculate_trend_analysis(metric_name, region, region_data)
            trend_analysis.append(trend)
            volatility_summary[region][metric_name] = {
                "volatility": trend.volatility,
                "trend": trend.trend_direction,
                "max_value": trend.max_value,
                "max_date": trend.max_date.isoformat() if trend.max_date else None,
                "min_value": trend.min_value,
                "min_date": trend.min_date.isoformat() if trend.min_date else None
            }

    all_metric_volatility = []
    for t in trend_analysis:
        if t.volatility is not None:
            all_metric_volatility.append({
                "region": t.region,
                "metric": t.metric_name,
                "volatility": t.volatility,
                "max_date": t.max_date.isoformat() if t.max_date else None,
                "max_value": t.max_value
            })

    all_metric_volatility.sort(key=lambda x: x["volatility"], reverse=True)

    peak_day = None
    lowest_day = None
    if daily_metrics:
        peak_day_data = max(daily_metrics, key=lambda x: x.total_alarms + x.new_accidents * 10)
        lowest_day_data = min(daily_metrics, key=lambda x: x.device_online_rate)
        peak_day = {
            "date": peak_day_data.report_date.isoformat(),
            "region": peak_day_data.region,
            "alarms": peak_day_data.total_alarms,
            "accidents": peak_day_data.new_accidents,
            "online_rate": peak_day_data.device_online_rate,
            "day_of_week": peak_day_data.day_of_week
        }
        lowest_day = {
            "date": lowest_day_data.report_date.isoformat(),
            "region": lowest_day_data.region,
            "online_rate": lowest_day_data.device_online_rate,
            "day_of_week": lowest_day_data.day_of_week
        }

    return RegionTrendResponse(
        start_date=s_date,
        end_date=e_date,
        regions=regions_list,
        total_days=(e_date - s_date).days + 1,
        daily_metrics=daily_metrics,
        trend_analysis=trend_analysis,
        volatility_summary=volatility_summary,
        peak_day=peak_day,
        lowest_day=lowest_day
    )


@router.get("/{report_id}", summary="获取报表详情", response_model=DailyReportResponse)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DailyReport).where(DailyReport.id == report_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="报表不存在")

    return report
