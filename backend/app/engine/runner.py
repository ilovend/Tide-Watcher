import json
import logging
import traceback
from typing import Any

from app.data.source_base import DataSource
from app.engine.context import StrategyContext
from app.engine.registry import StrategyMeta, get_all_strategies, get_strategy
from app.store.database import async_session
from app.store.models import StrategySignal

logger = logging.getLogger(__name__)


async def run_strategy(
    meta: StrategyMeta,
    source: DataSource,
    run_date: str | None = None,
) -> list[dict[str, Any]]:
    """执行单个策略并持久化信号。

    Args:
        meta:     策略元信息（从注册表获取）
        source:   数据源实例
        run_date: 运行日期，默认今天

    Returns:
        策略产生的信号列表
    """
    ctx = StrategyContext(source, run_date)
    logger.info("开始执行策略: %s", meta.name)

    try:
        results = await meta.func(ctx)

        # 策略可能通过 ctx.add_signal() 或直接 return 返回结果
        if not results and ctx.results:
            results = ctx.results

        # 持久化信号到数据库
        if results:
            await _save_signals(meta.name, results, ctx.run_date)
            logger.info("策略 '%s' 完成，产生 %d 条信号", meta.name, len(results))
        else:
            logger.info("策略 '%s' 完成，无信号产生", meta.name)

        return results or []

    except Exception:
        logger.error("策略 '%s' 执行失败:\n%s", meta.name, traceback.format_exc())
        return []


async def run_strategy_by_name(
    name: str,
    source: DataSource,
    run_date: str | None = None,
) -> list[dict[str, Any]]:
    """按名称执行策略。"""
    meta = get_strategy(name)
    if meta is None:
        raise ValueError(f"策略 '{name}' 不存在，已注册策略: {list(get_all_strategies().keys())}")
    return await run_strategy(meta, source, run_date)


async def run_all_strategies(
    source: DataSource,
    run_date: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """执行所有已启用策略。"""
    from app.engine.registry import get_enabled_strategies

    all_results: dict[str, list[dict[str, Any]]] = {}
    for meta in get_enabled_strategies():
        all_results[meta.name] = await run_strategy(meta, source, run_date)
    return all_results


async def _save_signals(
    strategy_name: str,
    signals: list[dict[str, Any]],
    run_date: str,
) -> None:
    """将策略信号批量写入数据库。"""
    async with async_session() as session:
        for sig in signals:
            extra = sig.get("extra", {})
            record = StrategySignal(
                strategy_name=strategy_name,
                stock_code=sig.get("stock_code", ""),
                stock_name=sig.get("stock_name", ""),
                signal_date=run_date,
                score=sig.get("score", 0.0),
                reason=sig.get("reason", ""),
                extra_data=json.dumps(extra, ensure_ascii=False) if extra else "{}",
            )
            session.add(record)
        await session.commit()
