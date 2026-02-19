"""
数据桥接模块 — 将 ZhituAPI 实时数据喂送给择时引擎。

职责：
  1. 从 ZhituAPI 采集实时盘面数据（全市场行情 + 股池）
  2. 组装 MarketSnapshot
  3. 执行完整的 择时(timing) → 守卫(guard) 流程
  4. 接口失败时默认最严格拦截

调用时机：
  每个交易日 14:30 由调度器自动触发
"""

import datetime
import logging
from typing import Any

from app.data.source_zhitu import ZhituSource
from app.engine.calendar import is_trading_day, is_before_close
from app.engine.timing import evaluate, TimingSignal, Light, Action
from app.engine.guard import confirm, MarketSnapshot

logger = logging.getLogger(__name__)

# 主要指数代码（用于计算指数跌幅）
INDEX_CODES = {"000001", "399001", "399006"}  # 上证/深证/创业板


async def fetch_market_snapshot(source: ZhituSource) -> MarketSnapshot:
    """从 ZhituAPI 采集实时数据，构建盘面快照。

    数据来源：
      - realtime_all: 全市场行情 → 指数跌幅、涨跌家数
      - pool/ztgc: 涨停股池 → 涨停数
      - pool/dtgc: 跌停股池 → 跌停数
      - pool/zbgc: 炸板股池 → 炸板数 + 炸板率
    """
    today = datetime.date.today().strftime("%Y-%m-%d")

    # 并发采集全市场行情 + 三个股池
    quotes: list[dict[str, Any]] = []
    zt_pool: list[dict[str, Any]] = []
    dt_pool: list[dict[str, Any]] = []
    zb_pool: list[dict[str, Any]] = []

    # 全市场行情（核心数据源）
    quotes = await source.get_realtime_all()

    # 股池数据（可能因为非交易时间返回空）
    zt_pool = await source.get_pool("ztgc", today)
    dt_pool = await source.get_pool("dtgc", today)
    zb_pool = await source.get_pool("zbgc", today)

    # 从全市场行情中提取统计
    up_count = 0
    down_count = 0
    worst_index_pct = 0.0

    for q in quotes:
        dm = str(q.get("dm", ""))
        pct = q.get("pc", 0) or 0

        # 指数跌幅（取最差的）
        pure = dm.split(".")[0] if "." in dm else dm
        if pure in INDEX_CODES:
            if pct < worst_index_pct:
                worst_index_pct = pct

        # 涨跌统计（排除指数，只统计个股）
        if len(pure) == 6 and pure[0] in ("0", "3", "6", "8"):
            if pct > 0:
                up_count += 1
            elif pct < 0:
                down_count += 1

    # 股池统计
    limit_up_count = len(zt_pool) if isinstance(zt_pool, list) else 0
    limit_down_count = len(dt_pool) if isinstance(dt_pool, list) else 0
    broken_board_count = len(zb_pool) if isinstance(zb_pool, list) else 0

    # 炸板率
    total_board = limit_up_count + broken_board_count
    broken_rate = (broken_board_count / total_board * 100) if total_board > 0 else 0.0

    snap = MarketSnapshot(
        index_change_pct=worst_index_pct,
        up_count=up_count,
        down_count=down_count,
        limit_up_count=limit_up_count,
        limit_down_count=limit_down_count,
        broken_board_count=broken_board_count,
        broken_rate=broken_rate,
    )

    logger.info(
        "盘面快照: 指数%.2f%% | 涨%d/跌%d | 涨停%d/跌停%d | 炸板%d(%.1f%%)",
        snap.index_change_pct, snap.up_count, snap.down_count,
        snap.limit_up_count, snap.limit_down_count,
        snap.broken_board_count, snap.broken_rate,
    )

    return snap


def _fail_safe_signal(d: datetime.date, error_msg: str) -> TimingSignal:
    """接口失败时的安全降级信号 — 最严格拦截。"""
    return TimingSignal(
        date=d,
        level=99,
        light=Light.RED,
        action=Action.OBSERVE,
        reason="数据获取失败，为了安全，禁止建仓",
        details=[
            f"错误信息: {error_msg}",
            "无法获取实时盘面数据，执行最严格拦截",
            "待数据恢复后再做决策",
        ],
    )


async def run_timing_pipeline(source: ZhituSource) -> TimingSignal:
    """完整择时流水线：日历择时 → 盘面守卫 → 最终信号。

    调用顺序：
      1. timing.evaluate() — 日历层面判断
      2. 如果是 PROBE_ENTRY → 采集实时数据 → guard.confirm()
      3. 如果采集失败 → fail-safe 最严格拦截

    Returns:
        最终的择时信号
    """
    today = datetime.date.today()

    # Step 1: 日历择时
    signal = evaluate(today)
    logger.info("日历择时: %s", signal)

    # 如果不是建仓信号，无需盘面确认
    if signal.action != Action.PROBE_ENTRY:
        return signal

    # Step 2: 需要盘面确认 — 采集数据
    try:
        snap = await fetch_market_snapshot(source)
    except Exception as e:
        logger.error("盘面数据采集失败: %s", e, exc_info=True)
        return _fail_safe_signal(today, str(e))

    # Step 3: 盘面守卫确认
    final = confirm(signal, snap)
    logger.info("守卫确认: %s", final)

    return final
