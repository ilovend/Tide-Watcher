import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy import text
from app.store.database import engine

async def fix():
    async with engine.begin() as conn:
        rows = await conn.run_sync(lambda c: c.execute(text("PRAGMA table_info(financial_risk)")).fetchall())
        existing = {r[1] for r in rows}
        if "is_extreme_risk" not in existing:
            await conn.run_sync(lambda c: c.execute(text(
                "ALTER TABLE financial_risk ADD COLUMN is_extreme_risk BOOLEAN DEFAULT 0"
            )))
            print("Added is_extreme_risk column")
        else:
            print("is_extreme_risk already exists")

asyncio.run(fix())
