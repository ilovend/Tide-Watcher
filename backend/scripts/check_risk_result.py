import asyncio, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.engine.finance_risk import get_risk_list

async def main():
    risks = await get_risk_list()
    print(f"Total flagged: {len(risks)}")
    for r in risks[:10]:
        print(f"  {r.code} {r.name} | {r.risk_type} | {r.reason}")
    if len(risks) > 10:
        print(f"  ... and {len(risks) - 10} more")

asyncio.run(main())
