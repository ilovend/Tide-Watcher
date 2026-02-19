"""数据库定时同步任务。

自动将 ZhituAPI 数据同步到本地数据库：
  - 股票列表 → stocks 表
  - 涨停/炸板/强势股池 → 结构化表
  - 情绪快照 → 基于股池数据自动计算

由 scheduler 在盘后自动调度执行。
"""

import logging
from typing import Any

from sqlalchemy import select, delete

from app.data.source_zhitu import ZhituSource
from app.store.database import async_session
from app.store.models import (
    Stock, LimitUpPool, BrokenBoardPool, StrongPool, EmotionSnapshot,
)

logger = logging.getLogger(__name__)


# ==========================================================================
# 股票列表同步
# ==========================================================================

async def sync_stock_list(source: ZhituSource) -> int:
    """同步全市场股票列表到 stocks 表。"""
    data = await source.get_stock_list()
    if not data:
        logger.warning("股票列表为空，跳过同步")
        return 0

    async with async_session() as session:
        count = 0
        for item in data:
            dm = item.get("dm", "")
            mc = item.get("mc", "")
            jys = item.get("jys", "")
            exchange = "SH" if jys == "sh" else "SZ" if jys == "sz" else "BJ"
            code = f"{dm}.{exchange}"

            existing = await session.get(Stock, code)
            if existing:
                existing.name = mc
                existing.exchange = exchange
            else:
                session.add(Stock(code=code, name=mc, exchange=exchange))
            count += 1

        await session.commit()

    logger.info("股票列表同步完成: %d 只", count)
    return count


# ==========================================================================
# 结构化股池同步
# ==========================================================================

def _parse_pool_stock(raw: dict[str, Any], trade_date: str) -> dict[str, Any]:
    """从 ZhituAPI 原始数据中提取通用股池字段。"""
    return {
        "trade_date": trade_date,
        "code": raw.get("dm", ""),
        "name": raw.get("mc", ""),
        "price": raw.get("p"),
        "change_pct": raw.get("zf"),
        "amount": raw.get("cje"),
        "float_mv": raw.get("lt"),
        "turnover": raw.get("hs"),
    }


async def sync_limit_up_pool(source: ZhituSource, date: str) -> int:
    """同步涨停股池到 limit_up_pool 表。"""
    data = await source.get_pool("ztgc", date)
    if not data:
        logger.info("涨停股池 %s 无数据", date)
        return 0

    async with async_session() as session:
        # 清除当日旧数据（幂等）
        await session.execute(
            delete(LimitUpPool).where(LimitUpPool.trade_date == date)
        )
        for raw in data:
            base = _parse_pool_stock(raw, date)
            record = LimitUpPool(
                **base,
                total_mv=raw.get("zsz"),
                limit_count=raw.get("lbc", 1),
                first_limit_time=raw.get("fbt"),
                last_limit_time=raw.get("lbt"),
                limit_amount=raw.get("zj"),
                break_count=raw.get("zbc", 0),
                limit_stat=raw.get("tj"),
            )
            session.add(record)
        await session.commit()

    logger.info("涨停股池同步: %s → %d 只", date, len(data))
    return len(data)


async def sync_broken_board_pool(source: ZhituSource, date: str) -> int:
    """同步炸板股池到 broken_board_pool 表。"""
    data = await source.get_pool("zbgc", date)
    if not data:
        logger.info("炸板股池 %s 无数据", date)
        return 0

    async with async_session() as session:
        await session.execute(
            delete(BrokenBoardPool).where(BrokenBoardPool.trade_date == date)
        )
        for raw in data:
            base = _parse_pool_stock(raw, date)
            record = BrokenBoardPool(
                **base,
                break_count=raw.get("zbc", 0),
                first_limit_time=raw.get("fbt"),
            )
            session.add(record)
        await session.commit()

    logger.info("炸板股池同步: %s → %d 只", date, len(data))
    return len(data)


async def sync_strong_pool(source: ZhituSource, date: str) -> int:
    """同步强势股池到 strong_pool 表。"""
    data = await source.get_pool("qsgc", date)
    if not data:
        logger.info("强势股池 %s 无数据", date)
        return 0

    async with async_session() as session:
        await session.execute(
            delete(StrongPool).where(StrongPool.trade_date == date)
        )
        for raw in data:
            base = _parse_pool_stock(raw, date)
            record = StrongPool(
                **base,
                streak_days=raw.get("lbc", 0),
            )
            session.add(record)
        await session.commit()

    logger.info("强势股池同步: %s → %d 只", date, len(data))
    return len(data)


async def sync_all_pools(source: ZhituSource, date: str) -> dict[str, int]:
    """同步所有股池 + 计算情绪快照。"""
    results: dict[str, int] = {}

    for name, fn in [
        ("ztgc", sync_limit_up_pool),
        ("zbgc", sync_broken_board_pool),
        ("qsgc", sync_strong_pool),
    ]:
        try:
            results[name] = await fn(source, date)
        except Exception:
            logger.exception("同步股池 %s 失败", name)
            results[name] = 0

    # 同步完成后计算情绪快照
    try:
        await compute_emotion_snapshot(date)
    except Exception:
        logger.exception("计算情绪快照失败: %s", date)

    return results


# ==========================================================================
# 情绪快照计算
# ==========================================================================

def _calculate_phase(score: float) -> str:
    """根据情绪评分判断市场阶段。"""
    if score >= 75:
        return "frenzy"
    if score >= 55:
        return "boom"
    if score >= 35:
        return "ferment"
    if score >= 20:
        return "retreat"
    return "ice"


def _calculate_score(
    limit_up_count: int,
    broken_rate: float,
    max_streak: int,
    promotion_rate: float,
) -> float:
    """计算情绪评分（0-100）。

    加权公式：
      涨停数量得分 (30%) + 连板高度得分 (25%) + 晋级率得分 (25%) + 炸板率反向得分 (20%)
    """
    # 涨停数量得分：0-80家映射到0-30分
    limit_score = min(limit_up_count / 80, 1.0) * 30

    # 连板高度得分：1-10板映射到0-25分
    streak_score = min(max_streak / 10, 1.0) * 25

    # 晋级率得分：0-50%映射到0-25分
    promo_score = min(promotion_rate / 50, 1.0) * 25

    # 炸板率反向得分：炸板率越低越好，0-50%映射到20-0分
    broken_score = max(1.0 - broken_rate / 50, 0.0) * 20

    return round(limit_score + streak_score + promo_score + broken_score, 1)


async def compute_emotion_snapshot(date: str) -> None:
    """基于当日涨停/炸板数据计算市场情绪快照。"""
    async with async_session() as session:
        # 查询涨停数据
        limit_ups = (await session.execute(
            select(LimitUpPool).where(LimitUpPool.trade_date == date)
        )).scalars().all()

        # 查询炸板数据
        brokens = (await session.execute(
            select(BrokenBoardPool).where(BrokenBoardPool.trade_date == date)
        )).scalars().all()

        limit_up_count = len(limit_ups)
        broken_board_count = len(brokens)

        if limit_up_count == 0:
            broken_rate = 0.0
            max_streak = 0
            first_board_count = 0
            promotion_rate = 0.0
            total_amount = 0.0
        else:
            broken_rate = round(broken_board_count / (limit_up_count + broken_board_count) * 100, 2)
            max_streak = max((r.limit_count for r in limit_ups), default=0)
            first_board_count = sum(1 for r in limit_ups if r.limit_count == 1)
            multi_board = limit_up_count - first_board_count
            promotion_rate = round(multi_board / limit_up_count * 100, 2) if limit_up_count > 0 else 0.0
            total_amount = sum(r.amount or 0 for r in limit_ups)

        score = _calculate_score(limit_up_count, broken_rate, max_streak, promotion_rate)
        phase = _calculate_phase(score)

        # 写入（upsert）
        existing = (await session.execute(
            select(EmotionSnapshot).where(EmotionSnapshot.trade_date == date)
        )).scalar_one_or_none()

        if existing:
            existing.limit_up_count = limit_up_count
            existing.broken_board_count = broken_board_count
            existing.broken_rate = broken_rate
            existing.max_streak = max_streak
            existing.first_board_count = first_board_count
            existing.promotion_rate = promotion_rate
            existing.total_limit_amount = total_amount
            existing.phase = phase
            existing.phase_score = score
        else:
            session.add(EmotionSnapshot(
                trade_date=date,
                limit_up_count=limit_up_count,
                broken_board_count=broken_board_count,
                broken_rate=broken_rate,
                max_streak=max_streak,
                first_board_count=first_board_count,
                promotion_rate=promotion_rate,
                total_limit_amount=total_amount,
                phase=phase,
                phase_score=score,
            ))

        await session.commit()

    logger.info(
        "情绪快照: %s → 涨停%d 炸板%d 连板%d 评分%.1f(%s)",
        date, limit_up_count, broken_board_count, max_streak, score, phase,
    )
