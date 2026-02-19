"""
验证盘面守卫在不同市场场景下的二次确认行为。

用法：
    cd backend
    ./venv/Scripts/python scripts/verify_guard.py
"""

import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.timing import evaluate, Action
from app.engine.guard import confirm, MarketSnapshot


def print_sep():
    print("=" * 72)


def test_scenario(name: str, date: datetime.date, snap: MarketSnapshot):
    """测试一个场景。"""
    print_sep()
    print(f"📋 场景: {name}")
    print(f"   日期: {date}")
    print(f"   盘面: 指数{snap.index_change_pct:+.2f}% | "
          f"涨{snap.up_count}/跌{snap.down_count} | "
          f"涨停{snap.limit_up_count}/跌停{snap.limit_down_count} | "
          f"炸板率{snap.broken_rate:.0f}%")
    print()

    # 日历信号
    raw = evaluate(date)
    light_map = {"红灯": "🔴", "黄灯": "🟡", "绿灯": "🟢"}
    print(f"   日历信号: {light_map.get(raw.light.value, '⚪')} {raw}")

    # 守卫确认
    final = confirm(raw, snap)
    print(f"   最终信号: {light_map.get(final.light.value, '⚪')} {final}")
    if final.details:
        for d in final.details:
            print(f"             → {d}")
    print()


def main():
    print()
    print_sep()
    print("🛡️ Tide-Watcher 盘面守卫验证")
    print_sep()
    print()

    # 使用 2026-05-26（期权结算周周二）作为测试日期
    d = datetime.date(2026, 5, 26)

    # 场景1: 正常博弈性回落
    test_scenario(
        "正常博弈性回落 → 放行建仓",
        d,
        MarketSnapshot(
            index_change_pct=-0.8,
            up_count=1800,
            down_count=2500,
            limit_up_count=30,
            limit_down_count=5,
            broken_rate=15.0,
        ),
    )

    # 场景2: 单边暴跌（指数跌3%+）
    test_scenario(
        "单边暴跌（指数-3.5%）→ 拦截",
        d,
        MarketSnapshot(
            index_change_pct=-3.5,
            up_count=300,
            down_count=4200,
            limit_up_count=5,
            limit_down_count=150,
            broken_rate=80.0,
        ),
    )

    # 场景3: 千股跌停
    test_scenario(
        "千股跌停（跌停280只）→ 拦截",
        d,
        MarketSnapshot(
            index_change_pct=-2.1,
            up_count=500,
            down_count=3800,
            limit_up_count=10,
            limit_down_count=280,
            broken_rate=60.0,
        ),
    )

    # 场景4: 情绪偏弱（炸板率高）
    test_scenario(
        "情绪偏弱（炸板率55%）→ 降级",
        d,
        MarketSnapshot(
            index_change_pct=-1.2,
            up_count=1500,
            down_count=2800,
            limit_up_count=25,
            limit_down_count=15,
            broken_rate=55.0,
        ),
    )

    # 场景5: 跌停偏多但未到暴跌
    test_scenario(
        "跌停偏多（80只）→ 降级",
        d,
        MarketSnapshot(
            index_change_pct=-1.5,
            up_count=1200,
            down_count=3000,
            limit_up_count=15,
            limit_down_count=80,
            broken_rate=35.0,
        ),
    )

    # 场景6: L1 禁区日（守卫不干预）
    test_scenario(
        "L1 禁区日（4/21）→ 守卫不干预，L1直接拦截",
        datetime.date(2026, 4, 21),
        MarketSnapshot(
            index_change_pct=1.5,
            up_count=3500,
            down_count=800,
            limit_up_count=60,
            limit_down_count=2,
            broken_rate=10.0,
        ),
    )

    print_sep()
    print("✅ 守卫验证完成")
    print_sep()


if __name__ == "__main__":
    main()
