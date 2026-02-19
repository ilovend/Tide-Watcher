import asyncio, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.data.source_zhitu import ZhituSource

async def main():
    source = ZhituSource()
    try:
        # Check a non-bank stock
        data = await source.get_company_info("000021", "cwzb")
        if isinstance(data, list):
            print(f"Type: list, Length: {len(data)}")
            if data:
                print("First item keys:", list(data[0].keys()) if isinstance(data[0], dict) else type(data[0]))
                print("First item:", json.dumps(data[0], ensure_ascii=False, indent=2))
                if len(data) > 1:
                    print("Second item:", json.dumps(data[1], ensure_ascii=False, indent=2))
        elif isinstance(data, dict):
            print(f"Type: dict, Keys: {list(data.keys())}")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
        else:
            print(f"Type: {type(data)}, Value: {str(data)[:500]}")
    finally:
        await source.close()

asyncio.run(main())
