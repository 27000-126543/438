import asyncio
import uuid
from app.database import AsyncSessionLocal
from app.models import MaintenanceStaff


async def init_staff():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(MaintenanceStaff))
        existing = result.scalars().all()
        if existing:
            print(f"已有 {len(existing)} 名维护人员，跳过初始化")
            return

        staff_list = [
            {
                "name": "张工",
                "phone": "13800138001",
                "skills": ["camera_repair", "basic_maintenance", "network_config"],
                "latitude": 39.9842,
                "longitude": 116.3074,
                "status": "available",
            },
            {
                "name": "李工",
                "phone": "13800138002",
                "skills": ["sensor_calibration", "lidar_repair", "basic_maintenance"],
                "latitude": 39.9850,
                "longitude": 116.3080,
                "status": "available",
            },
            {
                "name": "王工",
                "phone": "13800138003",
                "skills": ["radar_repair", "power_system", "basic_maintenance"],
                "latitude": 39.9830,
                "longitude": 116.3060,
                "status": "available",
            },
        ]

        for data in staff_list:
            staff_code = f"MS{uuid.uuid4().hex[:8].upper()}"
            staff = MaintenanceStaff(
                staff_code=staff_code,
                name=data["name"],
                phone=data["phone"],
                skills=data["skills"],
                current_latitude=data["latitude"],
                current_longitude=data["longitude"],
                status=data["status"],
                workload=0,
            )
            db.add(staff)

        await db.commit()
        print(f"✅ 成功初始化 {len(staff_list)} 名维护人员")

if __name__ == "__main__":
    from sqlalchemy import select
    asyncio.run(init_staff())
