"""
动态交易日历模块。

职责：
  1. 判断任意日期是否为 A 股交易日（基于 chinesecalendar）
  2. 计算每月期货交割日（第三个周五）和期权结算日（第四个周三）
  3. 若结算日遇到非交易日，自动回退到前一个交易日
  4. 提供"结算周"判断和操作窗口时间
"""

import datetime
from calendar import monthrange
from functools import lru_cache

from chinese_calendar import is_workday, is_holiday


# ==================== 交易日判断 ====================

def is_trading_day(d: datetime.date) -> bool:
    """判断是否为 A 股交易日（非周末 + 非法定假日）。"""
    if d.weekday() >= 5:
        return False
    return is_workday(d)


def prev_trading_day(d: datetime.date) -> datetime.date:
    """获取 d 之前最近的交易日（不含 d 本身）。"""
    cur = d - datetime.timedelta(days=1)
    while not is_trading_day(cur):
        cur -= datetime.timedelta(days=1)
    return cur


def next_trading_day(d: datetime.date) -> datetime.date:
    """获取 d 之后最近的交易日（不含 d 本身）。"""
    cur = d + datetime.timedelta(days=1)
    while not is_trading_day(cur):
        cur += datetime.timedelta(days=1)
    return cur


def trading_day_or_prev(d: datetime.date) -> datetime.date:
    """若 d 是交易日则返回 d，否则回退到前一个交易日。"""
    while not is_trading_day(d):
        d -= datetime.timedelta(days=1)
    return d


# ==================== 结算日计算 ====================

def _nth_weekday_of_month(year: int, month: int, weekday: int, nth: int) -> datetime.date:
    """计算某月第 N 个星期 X 的日期。

    Args:
        weekday: 0=周一, 4=周五
        nth: 1-based，第几个
    """
    first_day = datetime.date(year, month, 1)
    first_weekday = first_day.weekday()

    # 第一个目标星期X出现在几号
    diff = (weekday - first_weekday) % 7
    first_target = first_day + datetime.timedelta(days=diff)

    # 第 N 个
    result = first_target + datetime.timedelta(weeks=nth - 1)
    if result.month != month:
        raise ValueError(f"{year}-{month:02d} 不存在第 {nth} 个星期{weekday}")
    return result


@lru_cache(maxsize=128)
def futures_settlement_day(year: int, month: int) -> datetime.date:
    """股指期货交割日：每月第三个周五，遇非交易日则前移。"""
    raw = _nth_weekday_of_month(year, month, weekday=4, nth=3)  # 4=Friday
    return trading_day_or_prev(raw)


@lru_cache(maxsize=128)
def options_settlement_day(year: int, month: int) -> datetime.date:
    """ETF 期权结算日：每月第四个周三，遇非交易日则前移。"""
    raw = _nth_weekday_of_month(year, month, weekday=2, nth=4)  # 2=Wednesday
    return trading_day_or_prev(raw)


# ==================== 结算周判断 ====================

def _week_range(d: datetime.date) -> tuple[datetime.date, datetime.date]:
    """返回 d 所在周的周一和周五。"""
    monday = d - datetime.timedelta(days=d.weekday())
    friday = monday + datetime.timedelta(days=4)
    return monday, friday


def is_futures_settlement_week(d: datetime.date) -> bool:
    """判断 d 是否在期货交割周内（交割日所在的周一到周五）。"""
    sd = futures_settlement_day(d.year, d.month)
    mon, fri = _week_range(sd)
    return mon <= d <= fri


def is_options_settlement_week(d: datetime.date) -> bool:
    """判断 d 是否在期权结算周内（结算日所在的周一到周五）。"""
    sd = options_settlement_day(d.year, d.month)
    mon, fri = _week_range(sd)
    return mon <= d <= fri


def settlement_week_info(d: datetime.date) -> dict:
    """返回 d 在结算周中的角色信息。

    Returns:
        {
            "is_futures_week": bool,
            "is_options_week": bool,
            "futures_day": date or None,    # 本月期货交割日
            "options_day": date or None,    # 本月期权结算日
            "pre_retreat_day": date or None,  # 结算周前的那个周五（撤退日）
        }
    """
    fd = futures_settlement_day(d.year, d.month)
    od = options_settlement_day(d.year, d.month)

    in_fw = is_futures_settlement_week(d)
    in_ow = is_options_settlement_week(d)

    # 前置撤退日 = 结算周之前的那个周五
    pre_retreat = None
    if in_fw:
        fw_mon, _ = _week_range(fd)
        prev_fri = fw_mon - datetime.timedelta(days=3)  # 上周五
        pre_retreat = trading_day_or_prev(prev_fri)
    elif in_ow:
        ow_mon, _ = _week_range(od)
        prev_fri = ow_mon - datetime.timedelta(days=3)
        pre_retreat = trading_day_or_prev(prev_fri)

    return {
        "is_futures_week": in_fw,
        "is_options_week": in_ow,
        "futures_day": fd,
        "options_day": od,
        "pre_retreat_day": pre_retreat,
    }


# ==================== 操作窗口 ====================

BEFORE_CLOSE_START = datetime.time(14, 30)
BEFORE_CLOSE_END = datetime.time(15, 0)
POST_CLOSE = datetime.time(15, 0)


def is_before_close(t: datetime.time | None = None) -> bool:
    """判断是否处于"收盘前"窗口（14:30 - 15:00）。"""
    if t is None:
        t = datetime.datetime.now().time()
    return BEFORE_CLOSE_START <= t <= BEFORE_CLOSE_END


def is_post_close(t: datetime.time | None = None) -> bool:
    """判断是否已过收盘时间（15:00 之后）。"""
    if t is None:
        t = datetime.datetime.now().time()
    return t >= POST_CLOSE
