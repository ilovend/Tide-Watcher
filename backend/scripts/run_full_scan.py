import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.source_zhitu import ZhituSource
from app.engine.finance_risk import scan_all_stocks, deep_scan_flagged, get_risk_list

async def main():
    source = ZhituSource()
    try:
        # Step 1: 基础扫描（浮动阈值）
        print("=" * 60)
        print("Step 1: 基础扫描（cwzb 财务指标）")
        print("=" * 60)
        stats1 = await scan_all_stocks(source, batch_size=30)
        print(f"基础扫描: {stats1}")

        # Step 2: 深度扫描（income 利润表）
        print()
        print("=" * 60)
        print("Step 2: 深度扫描（income 利润表，补齐3年亏损）")
        print("=" * 60)
        stats2 = await deep_scan_flagged(source)
        print(f"深度扫描: {stats2}")

        # Step 3: 输出结果
        print()
        print("=" * 60)
        print("最终结果")
        print("=" * 60)
        risks = await get_risk_list()
        extreme = [r for r in risks if r.is_extreme_risk]
        normal = [r for r in risks if not r.is_extreme_risk]

        print(f"\n总标记: {len(risks)} 只")
        print(f"极端风险 (is_extreme_risk): {len(extreme)} 只")
        print(f"普通风险: {len(normal)} 只")

        if extreme:
            print(f"\n--- 极端风险股（连续3年亏损）---")
            for r in extreme[:30]:
                print(f"  {r.code} {r.name} | {r.risk_type} | {r.reason}")
            if len(extreme) > 30:
                print(f"  ... and {len(extreme) - 30} more")

        print(f"\n--- 普通风险股（低营收）前10只 ---")
        for r in normal[:10]:
            print(f"  {r.code} {r.name} | {r.risk_type} | {r.reason}")

    finally:
        await source.close()

asyncio.run(main())
