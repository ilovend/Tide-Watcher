from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.data.dependencies import get_source
from app.data.source_zhitu import ZhituSource
from app.engine.registry import get_all_strategies, get_strategy
from app.engine.runner import run_strategy, run_all_strategies
from app.store.database import async_session
from app.store.models import StrategySignal

router = APIRouter(prefix="/api/strategies", tags=["策略"])


@router.get("/list")
async def strategy_list():
    """获取所有已注册策略。"""
    strategies = get_all_strategies()
    return {
        "count": len(strategies),
        "data": [
            {
                "name": meta.name,
                "schedule": meta.schedule,
                "description": meta.description,
                "enabled": meta.enabled,
                "tags": meta.tags,
            }
            for meta in strategies.values()
        ],
    }


@router.post("/run/{name}")
async def run_one(
    name: str,
    date: str = Query(None, description="运行日期 yyyy-MM-dd，默认今天"),
    source: ZhituSource = Depends(get_source),
):
    """手动执行指定策略。"""
    meta = get_strategy(name)
    if meta is None:
        raise HTTPException(404, f"策略 '{name}' 不存在")

    results = await run_strategy(meta, source, date)
    return {
        "strategy": name,
        "signal_count": len(results),
        "signals": results,
    }


@router.post("/run-all")
async def run_all(
    date: str = Query(None, description="运行日期 yyyy-MM-dd，默认今天"),
    source: ZhituSource = Depends(get_source),
):
    """手动执行所有已启用策略。"""
    all_results = await run_all_strategies(source, date)
    return {
        "strategy_count": len(all_results),
        "results": {
            name: {"signal_count": len(signals), "signals": signals}
            for name, signals in all_results.items()
        },
    }


@router.get("/signals")
async def query_signals(
    strategy_name: str = Query(None, description="按策略名称筛选"),
    date: str = Query(None, description="按信号日期筛选 yyyy-MM-dd"),
    limit: int = Query(50, ge=1, le=500),
):
    """查询历史选股信号。"""
    async with async_session() as session:
        stmt = select(StrategySignal).order_by(StrategySignal.created_at.desc())

        if strategy_name:
            stmt = stmt.where(StrategySignal.strategy_name == strategy_name)
        if date:
            stmt = stmt.where(StrategySignal.signal_date == date)

        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()

    return {
        "count": len(rows),
        "data": [
            {
                "id": r.id,
                "strategy_name": r.strategy_name,
                "stock_code": r.stock_code,
                "stock_name": r.stock_name,
                "signal_date": r.signal_date,
                "score": r.score,
                "reason": r.reason,
                "extra_data": r.extra_data,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
