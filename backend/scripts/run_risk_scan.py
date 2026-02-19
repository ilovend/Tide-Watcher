import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.source_zhitu import ZhituSource
from app.engine.finance_risk import scan_all_stocks, get_risk_list

async def main():
    source = ZhituSource()
    try:
        stats = await scan_all_stocks(source, batch_size=30)
        print(f"\nScan stats: {stats}")
        
        risks = await get_risk_list()
        print(f"\nFlagged: {len(risks)}")
        for r in risks[:20]:
            print(f"  {r.code} {r.name} | {r.risk_type} | {r.reason}")
        if len(risks) > 20:
            print(f"  ... and {len(risks) - 20} more")
    finally:
        await source.close()

asyncio.run(main())
