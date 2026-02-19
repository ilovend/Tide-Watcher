import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy import text
from app.store.database import engine

COLUMNS_TO_ADD = [
    ("list_date", "VARCHAR(10)"),
    ("total_shares", "FLOAT"),
    ("float_shares", "FLOAT"),
    ("is_active", "BOOLEAN DEFAULT 1"),
]

async def fix():
    async with engine.begin() as conn:
        rows = await conn.run_sync(lambda c: c.execute(text("PRAGMA table_info(stocks)")).fetchall())
        existing = {r[1] for r in rows}
        for col_name, col_type in COLUMNS_TO_ADD:
            if col_name not in existing:
                sql = f"ALTER TABLE stocks ADD COLUMN {col_name} {col_type}"
                await conn.run_sync(lambda c, s=sql: c.execute(text(s)))
                print(f"Added {col_name}")
            else:
                print(f"{col_name} already exists")

asyncio.run(fix())
