import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.source_zhitu import ZhituSource
from app.store.sync import sync_stock_list

async def main():
    source = ZhituSource()
    try:
        await sync_stock_list(source)
    finally:
        await source.close()

asyncio.run(main())
