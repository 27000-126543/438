import asyncio
import aiosqlite
from app.config import DATABASE_URL

async def migrate():
    db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///./", "./")

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("PRAGMA table_info(accident_reports)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "blocked_at_step" not in column_names:
            print("Adding blocked_at_step column to accident_reports...")
            await db.execute(
                "ALTER TABLE accident_reports ADD COLUMN blocked_at_step VARCHAR(50)"
            )
            await db.commit()
            print("✅ blocked_at_step column added successfully")
        else:
            print("ℹ️  blocked_at_step column already exists")

        await db.close()

if __name__ == "__main__":
    asyncio.run(migrate())
