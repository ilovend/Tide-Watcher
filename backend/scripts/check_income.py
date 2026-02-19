import asyncio, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.data.source_zhitu import ZhituSource

async def main():
    source = ZhituSource()
    try:
        # Test with a known stock, get 3 years of income data
        data = await source.get_finance_report("000010.SZ", "income")
        if isinstance(data, list):
            print(f"Type: list, Length: {len(data)}")
            if data:
                print("Keys:", list(data[0].keys()) if isinstance(data[0], dict) else type(data[0]))
                for item in data:
                    d = item.get("reportDate", item.get("date", item.get("rq", "?")))
                    jlr = item.get("jlr", item.get("netProfit", "?"))
                    yysr = item.get("yysr", item.get("totalRevenue", item.get("zyyw", "?")))
                    kflr = item.get("kflr", "?")
                    print(f"  {d} | jlr={jlr} | yysr={yysr} | kflr={kflr}")
        elif isinstance(data, dict):
            print(f"Type: dict")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
        else:
            print(f"Type: {type(data)}")
    finally:
        await source.close()

asyncio.run(main())
