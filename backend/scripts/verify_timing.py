"""
验证择时引擎在 2026 年关键日期的输出。

用法：
    cd backend
    ./venv/Scripts/python scripts/verify_timing.py
"""

import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engine.calendar import (
    is_trading_day,
    futures_settlement_day,
    options_settlement_day,
    settlement_week_info,
)
from app.engine.timing import evaluate, evaluate_range


def print_sep():
    print("=" * 72)


def show_monthly_calendar(year: int, month: int):
    """显示某月的结算日信息。"""
    fd = futures_settlement_day(year, month)
    od = options_settlement_day(year, month)
    print(f"  {year}-{month:02d} | 期货交割日: {fd} ({fd.strftime('%A')}) | 期权结算日: {od} ({od.strftime('%A')})")


def verify_date(d: datetime.date, expected_summary: str):
    """验证单个日期并输出详细信息。"""
    print_sep()
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    wd = weekday_names[d.weekday()]
    trading = "✅ 交易日" if is_trading_day(d) else "❌ 非交易日"

    print(f"📅 {d} ({wd}) — {trading}")
    print(f"   预期: {expected_summary}")
    print()

    sig = evaluate(d)
    light_emoji = {"红灯": "🔴", "黄灯": "🟡", "绿灯": "🟢"}
    emoji = light_emoji.get(sig.light.value, "⚪")

    print(f"   结果: {emoji} {sig}")
    if sig.details:
        for detail in sig.details:
            print(f"         → {detail}")

    # 补充结算周信息
    info = settlement_week_info(d)
    parts = []
    if info["is_futures_week"]:
        parts.append(f"期货交割周(交割日={info['futures_day']})")
    if info["is_options_week"]:
        parts.append(f"期权结算周(结算日={info['options_day']})")
    if parts:
        print(f"   结算周: {', '.join(parts)}")
    print()


def main():
    print()
    print_sep()
    print("🌊 Tide-Watcher 择时引擎验证 — 2026 年关键日期")
    print_sep()
    print()

    # 先展示 2026 年各月结算日
    print("📊 2026 年结算日一览:")
    print()
    for m in range(1, 13):
        show_monthly_calendar(2026, m)
    print()

    # 验证 4 个关键日期
    print("🔍 关键日期验证:")

    verify_date(
        datetime.date(2026, 3, 13),
        "年报预警(L2黄灯) + 期货交割周前置撤退(L3) → L2优先，黄灯清仓离场",
    )

    verify_date(
        datetime.date(2026, 4, 21),
        "4月结算周博弈点 → 但处于绝对禁区(3/15~4/30)，L1强制红灯拦截",
    )

    verify_date(
        datetime.date(2026, 5, 19),
        "常规时段，期货交割周的周二 → L3绿灯，试探建仓",
    )

    verify_date(
        datetime.date(2026, 5, 26),
        "常规时段，期权结算周的周二 → L3绿灯，试探建仓",
    )

    # 补充：展示 2026-03 和 2026-05 的完整择时信号
    print_sep()
    print("📋 2026 年 3 月完整择时信号:")
    print_sep()
    for sig in evaluate_range(datetime.date(2026, 3, 1), datetime.date(2026, 3, 31)):
        light_emoji = {"红灯": "🔴", "黄灯": "🟡", "绿灯": "🟢"}
        emoji = light_emoji.get(sig.light.value, "⚪")
        print(f"  {emoji} {sig}")

    print()
    print_sep()
    print("📋 2026 年 5 月完整择时信号:")
    print_sep()
    for sig in evaluate_range(datetime.date(2026, 5, 1), datetime.date(2026, 5, 31)):
        light_emoji = {"红灯": "🔴", "黄灯": "🟡", "绿灯": "🟢"}
        emoji = light_emoji.get(sig.light.value, "⚪")
        print(f"  {emoji} {sig}")

    print()
    print_sep()
    print("✅ 验证完成")
    print_sep()


if __name__ == "__main__":
    main()
