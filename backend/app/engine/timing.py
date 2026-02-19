"""
三级优先级择时漏斗。

信号优先级：Level 1 > Level 2 > Level 3
高级别触发后强制屏蔽低级别信号。

Level 1 - 绝对禁区（3/15 ~ 4/30 财报暴雷季）→ 强制红灯
Level 2 - 风险预警区（3/5~3/15 跑路期 + 12月资金枯竭期）→ 黄/红灯
Level 3 - 常规结算周博弈 → 战术信号
"""

import datetime
from dataclasses import dataclass, field
from enum import Enum

from app.engine.calendar import (
    is_trading_day,
    next_trading_day,
    futures_settlement_day,
    options_settlement_day,
    settlement_week_info,
    trading_day_or_prev,
    _week_range,
)
from chinese_calendar import is_holiday as _is_cn_holiday


# ==================== 信号定义 ====================

class Light(Enum):
    """交通灯状态"""
    RED = "红灯"
    YELLOW = "黄灯"
    GREEN = "绿灯"
    GREY = "休市"


class Action(Enum):
    """操作建议"""
    FORCE_EMPTY = "绝对空仓"
    CLEAR_EXIT = "清仓离场"
    REST = "建议休息"
    PRE_RETREAT = "前置撤退"
    PROBE_ENTRY = "试探建仓"
    OBSERVE = "结算观察"
    NORMAL = "正常交易"
    INACTIVE = "休市"


@dataclass
class TimingSignal:
    """择时信号"""
    date: datetime.date
    level: int                    # 1/2/3，0=无特殊信号
    light: Light
    action: Action
    reason: str
    details: list[str] = field(default_factory=list)
    is_trading_day: bool = True
    is_holiday: bool = False
    holiday_name: str = ""
    next_open_date: str = ""

    def __str__(self) -> str:
        level_tag = f"L{self.level}" if self.level > 0 else "L0"
        return (
            f"[{self.date}] {level_tag} {self.light.value} | "
            f"{self.action.value} — {self.reason}"
        )


# ==================== Level 1: 绝对禁区 ====================

def _check_level1(d: datetime.date) -> TimingSignal | None:
    """财报暴雷季：3月15日 ~ 4月30日，强制红灯。"""
    md = (d.month, d.day)
    if (3, 15) <= md <= (4, 30):
        return TimingSignal(
            date=d,
            level=1,
            light=Light.RED,
            action=Action.FORCE_EMPTY,
            reason="财报暴雷季（3/15~4/30），强制空仓",
            details=[
                f"当前处于年报/一季报密集披露期",
                f"严禁任何建仓操作",
            ],
        )
    return None


# ==================== Level 2: 风险预警区 ====================

def _check_level2(d: datetime.date) -> TimingSignal | None:
    """
    2A: 3月5日 ~ 3月14日 → 黄灯：清仓离场（为雷区前撤离）
    2B: 12月全月 → 红灯：建议休息（资金面枯竭期）
    """
    md = (d.month, d.day)

    # 2A: 风险前置跑路期
    if (3, 5) <= md <= (3, 14):
        days_to_zone = (datetime.date(d.year, 3, 15) - d).days
        return TimingSignal(
            date=d,
            level=2,
            light=Light.YELLOW,
            action=Action.CLEAR_EXIT,
            reason=f"风险前置跑路期（3/5~3/14），距绝对禁区还有 {days_to_zone} 天",
            details=[
                "即将进入财报暴雷季",
                "仅允许离场操作，严禁建仓",
            ],
        )

    # 2B: 资金面枯竭期
    if d.month == 12:
        return TimingSignal(
            date=d,
            level=2,
            light=Light.RED,
            action=Action.REST,
            reason="12月资金面枯竭期，建议休息",
            details=[
                "年末资金回笼压力大",
                "机构调仓换股密集",
                "仅允许离场预警，严禁建仓",
            ],
        )

    return None


# ==================== Level 3: 常规结算周博弈 ====================

def _check_level3(d: datetime.date) -> TimingSignal | None:
    """
    结算周战术：
    - 结算周前的周五 → 前置撤退
    - 结算周的周二 → 试探建仓
    - 结算日（周三/周五）→ 结算观察
    """
    info = settlement_week_info(d)
    weekday = d.weekday()  # 0=Mon ... 4=Fri

    fd = info["futures_day"]
    od = info["options_day"]

    # ---- 前置撤退：结算周之前的周五 ----
    if weekday == 4:  # 周五
        # 检查下周是否为某个结算周
        next_monday = d + datetime.timedelta(days=3)

        # 检查下周是否包含期货交割日
        fd_next = futures_settlement_day(next_monday.year, next_monday.month)
        fd_mon, fd_fri = _week_range(fd_next)
        if fd_mon == next_monday:
            return TimingSignal(
                date=d,
                level=3,
                light=Light.YELLOW,
                action=Action.PRE_RETREAT,
                reason=f"期货交割周前置撤退（交割日 {fd_next}）",
                details=[
                    "下周为期货交割周",
                    "14:30 收盘前完成减仓/离场",
                ],
            )

        # 检查下周是否包含期权结算日
        od_next = options_settlement_day(next_monday.year, next_monday.month)
        od_mon, od_fri = _week_range(od_next)
        if od_mon == next_monday:
            return TimingSignal(
                date=d,
                level=3,
                light=Light.YELLOW,
                action=Action.PRE_RETREAT,
                reason=f"期权结算周前置撤退（结算日 {od_next}）",
                details=[
                    "下周为期权结算周",
                    "14:30 收盘前完成减仓/离场",
                ],
            )

    # ---- 战术执行日：结算周的周二 ----
    if weekday == 1:  # 周二
        targets = []
        if info["is_futures_week"]:
            targets.append(f"期货交割日 {fd}")
        if info["is_options_week"]:
            targets.append(f"期权结算日 {od}")

        if targets:
            return TimingSignal(
                date=d,
                level=3,
                light=Light.GREEN,
                action=Action.PROBE_ENTRY,
                reason=f"结算周战术执行日（{' + '.join(targets)}）",
                details=[
                    "14:30 观察市场是否出现博弈性回落",
                    "若非单边暴跌，可收盘前试探性建仓",
                    "严格控制仓位，不宜重仓",
                ],
            )

    # ---- 结算日观察 ----
    if d == fd and info["is_futures_week"]:
        return TimingSignal(
            date=d,
            level=3,
            light=Light.YELLOW,
            action=Action.OBSERVE,
            reason=f"期货交割日，15:00 后观察情绪切换",
            details=[
                "股指期货本月合约交割完成",
                "关注盘后资金流向和情绪变化",
            ],
        )

    if d == od and info["is_options_week"]:
        return TimingSignal(
            date=d,
            level=3,
            light=Light.YELLOW,
            action=Action.OBSERVE,
            reason=f"期权结算日，15:00 后观察情绪切换",
            details=[
                "ETF 期权本月合约结算完成",
                "关注盘后资金流向和情绪变化",
            ],
        )

    return None


# ==================== 漏斗主入口 ====================

def evaluate(d: datetime.date) -> TimingSignal:
    """三级择时漏斗主入口。

    按优先级依次检查：L1 → L2 → L3 → 正常交易。
    高级别信号触发后，低级别被屏蔽。

    Args:
        d: 要评估的日期

    Returns:
        TimingSignal: 当日的择时信号
    """
    # Level 1: 绝对禁区
    sig = _check_level1(d)
    if sig:
        return sig

    # Level 2: 风险预警区
    sig = _check_level2(d)
    if sig:
        return sig

    # Level 3: 结算周博弈（仅在交易日生效）
    if is_trading_day(d):
        sig = _check_level3(d)
        if sig:
            return sig

    # 非交易日 → 灰色休市态
    if not is_trading_day(d):
        return _build_inactive_signal(d)

    # 无特殊信号
    return TimingSignal(
        date=d,
        level=0,
        light=Light.GREEN,
        action=Action.NORMAL,
        reason="正常交易时段",
    )


# ==================== 休市信号构建 ====================

_HOLIDAY_NAMES: dict[tuple[int, int], str] = {
    (1, 1): "元旦", (1, 2): "元旦",
    (2, 14): "春节", (2, 15): "春节", (2, 16): "春节", (2, 17): "春节",
    (2, 18): "春节", (2, 19): "春节", (2, 20): "春节", (2, 21): "春节", (2, 22): "春节",
    (5, 1): "劳动节", (5, 2): "劳动节", (5, 3): "劳动节",
    (10, 1): "国庆节", (10, 2): "国庆节", (10, 3): "国庆节", (10, 4): "国庆节",
    (10, 5): "国庆节", (10, 6): "国庆节", (10, 7): "国庆节",
}


def _get_holiday_name(d: datetime.date) -> str:
    """获取节假日名称。优先走静态表，兜底检测 chinese_calendar。"""
    name = _HOLIDAY_NAMES.get((d.month, d.day), "")
    if name:
        return name
    if d.weekday() >= 5:
        return "周末"
    try:
        if _is_cn_holiday(d):
            return "法定假日"
    except Exception:
        pass
    return "非交易日"


def _build_inactive_signal(d: datetime.date) -> TimingSignal:
    """构建休市信号，包含假日信息和下一开盘日。"""
    holiday_name = _get_holiday_name(d)
    next_open = next_trading_day(d)
    next_open_str = next_open.strftime("%Y-%m-%d")

    if holiday_name == "周末":
        reason = f"周末休市 | {next_open.month}月{next_open.day}日开盘"
    else:
        reason = f"{holiday_name}休市 | {next_open.month}月{next_open.day}日开盘"

    return TimingSignal(
        date=d,
        level=0,
        light=Light.GREY,
        action=Action.INACTIVE,
        reason=reason,
        details=[f"下一交易日: {next_open_str}"],
        is_trading_day=False,
        is_holiday=holiday_name not in ("周末", "非交易日"),
        holiday_name=holiday_name,
        next_open_date=next_open_str,
    )


def evaluate_range(start: datetime.date, end: datetime.date) -> list[TimingSignal]:
    """批量评估日期范围内每个交易日的择时信号。"""
    results = []
    d = start
    while d <= end:
        if is_trading_day(d):
            results.append(evaluate(d))
        d += datetime.timedelta(days=1)
    return results
