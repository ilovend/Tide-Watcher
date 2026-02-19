"""
盘面守卫模块 — L3 建仓信号的二次确认。

职责：
  在日历择时（timing.py）发出 L3 PROBE_ENTRY 信号后，
  通过实时盘面数据进行二次确认，防止在单边暴跌中建仓。

检查维度：
  1. 指数跌幅（上证综指/深证成指/创业板指）
  2. 千股跌停（跌停数 > 阈值）
  3. 涨跌比（下跌家数 / 上涨家数）
  4. 炸板率（情绪快照）

使用方式：
  signal = timing.evaluate(date)
  if signal.action == Action.PROBE_ENTRY:
      final = guard.confirm(signal, market_snapshot)
"""

import datetime
from dataclasses import dataclass
from enum import Enum

from app.engine.timing import TimingSignal, Light, Action


class GuardVerdict(Enum):
    """守卫裁定结果"""
    PASS = "放行"           # 盘面正常，允许建仓
    DOWNGRADE = "降级"      # 有风险但不严重，降低仓位
    BLOCK = "拦截"          # 盘面恶劣，禁止建仓


@dataclass
class MarketSnapshot:
    """盘面快照 — 传入守卫的实时数据。

    可从全市场行情 API (realtime_all) 或情绪快照中提取。
    """
    index_change_pct: float = 0.0     # 主要指数涨跌幅（取最差的）
    up_count: int = 0                  # 上涨家数
    down_count: int = 0                # 下跌家数
    limit_up_count: int = 0            # 涨停数
    limit_down_count: int = 0          # 跌停数
    broken_board_count: int = 0        # 炸板数
    broken_rate: float = 0.0           # 炸板率（%）


# ==================== 阈值配置 ====================

INDEX_CRASH_PCT = -3.0         # 指数跌幅超过此值 → 暴跌
LIMIT_DOWN_CRASH = 200         # 跌停数超过此值 → 千股跌停
DOWN_UP_RATIO_CRASH = 3.0      # 跌/涨比超过此值 → 普跌
BROKEN_RATE_WARN = 50.0        # 炸板率超过此值 → 情绪恶化
LIMIT_DOWN_WARN = 50           # 跌停数超过此值 → 警告


# ==================== 守卫逻辑 ====================

def _check_crash(snap: MarketSnapshot) -> tuple[GuardVerdict, list[str]]:
    """检查是否处于暴跌状态。返回 (裁定, 原因列表)。"""
    reasons: list[str] = []
    verdict = GuardVerdict.PASS

    # 指数暴跌
    if snap.index_change_pct <= INDEX_CRASH_PCT:
        reasons.append(f"指数暴跌 {snap.index_change_pct:.2f}%（阈值 {INDEX_CRASH_PCT}%）")
        verdict = GuardVerdict.BLOCK

    # 千股跌停
    if snap.limit_down_count >= LIMIT_DOWN_CRASH:
        reasons.append(f"跌停 {snap.limit_down_count} 只（阈值 {LIMIT_DOWN_CRASH}）")
        verdict = GuardVerdict.BLOCK

    # 涨跌比极端
    if snap.up_count > 0:
        ratio = snap.down_count / snap.up_count
        if ratio >= DOWN_UP_RATIO_CRASH:
            reasons.append(f"涨跌比 1:{ratio:.1f}（阈值 1:{DOWN_UP_RATIO_CRASH}）")
            verdict = GuardVerdict.BLOCK

    return verdict, reasons


def _check_warning(snap: MarketSnapshot) -> tuple[GuardVerdict, list[str]]:
    """检查是否处于警告状态（不至于暴跌但情绪恶化）。"""
    reasons: list[str] = []
    verdict = GuardVerdict.PASS

    # 炸板率过高
    if snap.broken_rate >= BROKEN_RATE_WARN:
        reasons.append(f"炸板率 {snap.broken_rate:.1f}%（阈值 {BROKEN_RATE_WARN}%）")
        verdict = GuardVerdict.DOWNGRADE

    # 跌停数偏多
    if LIMIT_DOWN_WARN <= snap.limit_down_count < LIMIT_DOWN_CRASH:
        reasons.append(f"跌停 {snap.limit_down_count} 只（警告阈值 {LIMIT_DOWN_WARN}）")
        verdict = GuardVerdict.DOWNGRADE

    return verdict, reasons


def confirm(signal: TimingSignal, snap: MarketSnapshot) -> TimingSignal:
    """对 L3 PROBE_ENTRY 信号进行盘面二次确认。

    Args:
        signal: timing.evaluate() 输出的原始信号
        snap:   当前盘面快照

    Returns:
        确认后的信号（可能被降级或拦截）
    """
    # 只对 L3 建仓信号做二次确认
    if signal.action != Action.PROBE_ENTRY:
        return signal

    # 第一关：暴跌检查
    crash_verdict, crash_reasons = _check_crash(snap)
    if crash_verdict == GuardVerdict.BLOCK:
        return TimingSignal(
            date=signal.date,
            level=signal.level,
            light=Light.RED,
            action=Action.OBSERVE,
            reason=f"盘面守卫拦截：单边暴跌，禁止建仓",
            details=[
                f"原始信号: {signal.reason}",
                *crash_reasons,
                "建议观望，等待企稳信号",
            ],
        )

    # 第二关：警告检查
    warn_verdict, warn_reasons = _check_warning(snap)
    if warn_verdict == GuardVerdict.DOWNGRADE:
        return TimingSignal(
            date=signal.date,
            level=signal.level,
            light=Light.YELLOW,
            action=Action.PROBE_ENTRY,
            reason=f"盘面守卫降级：情绪偏弱，仅允许极轻仓试探",
            details=[
                f"原始信号: {signal.reason}",
                *warn_reasons,
                "仓位建议不超过 1 成",
            ],
        )

    # 通过：盘面正常
    signal.details.insert(0, "✅ 盘面守卫确认：盘面状态正常")
    return signal


# ==================== 从全市场行情构建快照 ====================

def build_snapshot_from_realtime(quotes: list[dict]) -> MarketSnapshot:
    """从全市场实时行情数据构建 MarketSnapshot。

    Args:
        quotes: stockApi.realtimeAll() 返回的行情列表，
                每项包含 dm/pc/ud 等字段

    Returns:
        MarketSnapshot
    """
    up = 0
    down = 0
    limit_up = 0
    limit_down = 0
    worst_index_pct = 0.0

    # 主要指数代码前缀
    index_codes = {"000001.SH", "399001.SZ", "399006.SZ"}

    for q in quotes:
        code = q.get("dm", "")
        pct = q.get("pc", 0) or 0

        # 指数跌幅
        if code in index_codes:
            if pct < worst_index_pct:
                worst_index_pct = pct

        # 涨跌统计
        if pct > 0:
            up += 1
        elif pct < 0:
            down += 1

        # 涨停/跌停判断（简化：涨跌幅 >= 9.8% 或 <= -9.8%）
        if pct >= 9.8:
            limit_up += 1
        elif pct <= -9.8:
            limit_down += 1

    broken_rate = 0.0  # 炸板率需从情绪快照获取

    return MarketSnapshot(
        index_change_pct=worst_index_pct,
        up_count=up,
        down_count=down,
        limit_up_count=limit_up,
        limit_down_count=limit_down,
        broken_rate=broken_rate,
    )
