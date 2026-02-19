import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.store.database import engine

async def create():
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: c.execute(text(
            "CREATE TABLE IF NOT EXISTS financial_risk ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "code VARCHAR(12) NOT NULL,"
            "name VARCHAR(20) DEFAULT '',"
            "risk_type VARCHAR(30) NOT NULL,"
            "risk_level VARCHAR(10) DEFAULT 'high',"
            "reason TEXT DEFAULT '',"
            "cumulative_loss FLOAT,"
            "latest_revenue FLOAT,"
            "latest_net_profit FLOAT,"
            "loss_years INTEGER DEFAULT 0,"
            "scan_date VARCHAR(10) NOT NULL,"
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )))
        await conn.run_sync(lambda c: c.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_fr_code ON financial_risk (code)"
        )))
        await conn.run_sync(lambda c: c.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_fr_scan ON financial_risk (scan_date)"
        )))
        await conn.run_sync(lambda c: c.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_fr_code_scan ON financial_risk (code, scan_date)"
        )))
    print("financial_risk table created")

asyncio.run(create())
