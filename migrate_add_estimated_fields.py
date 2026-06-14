import asyncio
from app.database import AsyncSessionLocal, engine
from sqlalchemy import text


async def migrate():
    print("开始数据库迁移...")

    async with engine.begin() as conn:
        print("检查并添加 maintenance_work_orders.estimated_arrival 字段...")
        try:
            await conn.execute(text("ALTER TABLE maintenance_work_orders ADD COLUMN estimated_arrival DATETIME"))
            print("✅ estimated_arrival 字段添加成功")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️  estimated_arrival 字段已存在，跳过")
            else:
                print(f"⚠️  添加 estimated_arrival 字段出错: {e}")

        print("检查并添加 maintenance_work_orders.estimated_completion 字段...")
        try:
            await conn.execute(text("ALTER TABLE maintenance_work_orders ADD COLUMN estimated_completion DATETIME"))
            print("✅ estimated_completion 字段添加成功")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️  estimated_completion 字段已存在，跳过")
            else:
                print(f"⚠️  添加 estimated_completion 字段出错: {e}")

        print("检查并添加 test_routes.test_area 字段...")
        try:
            await conn.execute(text("ALTER TABLE test_routes ADD COLUMN test_area VARCHAR(200)"))
            print("✅ test_area 字段添加成功")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️  test_area 字段已存在，跳过")
            else:
                print(f"⚠️  添加 test_area 字段出错: {e}")

    print("\n数据库迁移完成！")


if __name__ == "__main__":
    asyncio.run(migrate())
