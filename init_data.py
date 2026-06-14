import asyncio
from app.database import AsyncSessionLocal as async_session
from app.models import SafetyOfficer, MaintenanceStaff
from sqlalchemy import select


async def init_test_data():
    async with async_session() as db:
        print("初始化系统测试数据...")

        # 创建安全员
        officers = [
            {"officer_code": "SA001", "name": "张安全", "phone": "13900139001",
             "email": "zhang.anquan@example.com", "license_number": "LIC-SA-001",
             "certification_level": "高级", "status": "on_duty", "workload": 0},
            {"officer_code": "SA002", "name": "李监控", "phone": "13900139002",
             "email": "li.jiankong@example.com", "license_number": "LIC-SA-002",
             "certification_level": "中级", "status": "on_duty", "workload": 0},
            {"officer_code": "SA003", "name": "王监管", "phone": "13900139003",
             "email": "wang.jianguan@example.com", "license_number": "LIC-SA-003",
             "certification_level": "高级", "status": "on_duty", "workload": 0},
        ]
        for o in officers:
            existing = await db.execute(
                select(SafetyOfficer).where(SafetyOfficer.officer_code == o["officer_code"])
            )
            if not existing.scalar_one_or_none():
                db.add(SafetyOfficer(**o))
                print(f"  ✅ 创建安全员: {o['name']}")

        # 创建维护人员
        staff = [
            {"staff_code": "MS001", "name": "赵维修", "phone": "13700137001",
             "email": "zhao.weixiu@example.com", "skills": ["5G", "RSU", "optical_fiber"],
             "status": "available", "workload": 0,
             "current_latitude": 39.98, "current_longitude": 116.30},
            {"staff_code": "MS002", "name": "钱技术", "phone": "13700137002",
             "email": "qian.jishu@example.com", "skills": ["RSU", "radar", "software"],
             "status": "available", "workload": 0,
             "current_latitude": 39.95, "current_longitude": 116.35},
            {"staff_code": "MS003", "name": "孙工程师", "phone": "13700137003",
             "email": "sun.gongcheng@example.com", "skills": ["5G", "camera", "radar"],
             "status": "on_duty", "workload": 0,
             "current_latitude": 40.00, "current_longitude": 116.25},
        ]
        for s in staff:
            existing = await db.execute(
                select(MaintenanceStaff).where(MaintenanceStaff.staff_code == s["staff_code"])
            )
            if not existing.scalar_one_or_none():
                db.add(MaintenanceStaff(**s))
                print(f"  ✅ 创建维护人员: {s['name']}")

        await db.commit()
        print("\n✅ 测试数据初始化完成！")


if __name__ == "__main__":
    asyncio.run(init_test_data())
