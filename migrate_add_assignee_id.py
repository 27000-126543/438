import asyncio
import aiosqlite
from app.config import DATABASE_URL

async def migrate():
    db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///./", "./")

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("PRAGMA table_info(maintenance_work_orders)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "assignee_id" not in column_names:
            print("Adding assignee_id column to maintenance_work_orders...")
            await db.execute(
                "ALTER TABLE maintenance_work_orders ADD COLUMN assignee_id INTEGER"
            )
            await db.commit()
            print("✅ assignee_id column added successfully")
        else:
            print("ℹ️  assignee_id column already exists")

        await db.close()

if __name__ == "__main__":
    asyncio.run(migrate())
