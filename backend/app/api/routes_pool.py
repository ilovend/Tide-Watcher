from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func

from app.data.dependencies import get_source
from app.data.source_zhitu import ZhituSource
from app.store.database import async_session
from app.store.models import (
    LimitUpPool, BrokenBoardPool, StrongPool,
    EmotionSnapshot, Sector, StockSector, Watchlist,
)
from app.store.sync import (
    sync_limit_up_pool, sync_broken_board_pool, sync_strong_pool,
    compute_emotion_snapshot,
)

router = APIRouter(prefix="/api/pools", tags=["股池"])

_POOL_NAMES = {
    "ztgc": "涨停股池",
    "dtgc": "跌停股池",
    "qsgc": "强势股池",
    "cxgc": "次新股池",
    "zbgc": "炸板股池",
}


@router.get("/types")
async def pool_types():
    """获取所有可用股池类型。"""
    return {
        "data": [
            {"code": code, "name": name}
            for code, name in _POOL_NAMES.items()
        ]
    }


def _model_to_dict(row) -> dict:
    """将 ORM 对象转为字典。"""
    d = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        d[col.name] = val
    return d


@router.get("/history/ztgc")
async def limit_up_history(
    date: str = Query(None),
    code: str = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """查询本地涨停股池历史数据。"""
    async with async_session() as session:
        stmt = select(LimitUpPool).order_by(LimitUpPool.trade_date.desc())
        if date:
            stmt = stmt.where(LimitUpPool.trade_date == date)
        if code:
            stmt = stmt.where(LimitUpPool.code == code)
        rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return {"count": len(rows), "data": [_model_to_dict(r) for r in rows]}


@router.get("/history/zbgc")
async def broken_board_history(
    date: str = Query(None),
    code: str = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """查询本地炸板股池历史数据。"""
    async with async_session() as session:
        stmt = select(BrokenBoardPool).order_by(BrokenBoardPool.trade_date.desc())
        if date:
            stmt = stmt.where(BrokenBoardPool.trade_date == date)
        if code:
            stmt = stmt.where(BrokenBoardPool.code == code)
        rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return {"count": len(rows), "data": [_model_to_dict(r) for r in rows]}


@router.get("/history/qsgc")
async def strong_pool_history(
    date: str = Query(None),
    code: str = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """查询本地强势股池历史数据。"""
    async with async_session() as session:
        stmt = select(StrongPool).order_by(StrongPool.trade_date.desc())
        if date:
            stmt = stmt.where(StrongPool.trade_date == date)
        if code:
            stmt = stmt.where(StrongPool.code == code)
        rows = (await session.execute(stmt.limit(limit))).scalars().all()
    return {"count": len(rows), "data": [_model_to_dict(r) for r in rows]}


# ==========================================================================
# 情绪数据
# ==========================================================================

@router.get("/emotion/latest")
async def emotion_latest(limit: int = Query(30, ge=1, le=365)):
    """获取最新市场情绪快照列表。"""
    async with async_session() as session:
        rows = (await session.execute(
            select(EmotionSnapshot).order_by(EmotionSnapshot.trade_date.desc()).limit(limit)
        )).scalars().all()
    return {"count": len(rows), "data": [_model_to_dict(r) for r in rows]}


@router.get("/emotion/{trade_date}")
async def emotion_by_date(trade_date: str):
    """获取某日市场情绪快照。"""
    async with async_session() as session:
        row = (await session.execute(
            select(EmotionSnapshot).where(EmotionSnapshot.trade_date == trade_date)
        )).scalar_one_or_none()
    if row is None:
        return {"data": None, "message": f"{trade_date} 无情绪数据"}
    return {"data": _model_to_dict(row)}


# ==========================================================================
# 板块数据
# ==========================================================================

@router.get("/sectors")
async def sector_list(
    sector_type: str = Query("", description="concept/industry/空=全部"),
    limit: int = Query(500, ge=1, le=5000),
):
    """获取板块列表。"""
    async with async_session() as session:
        stmt = select(Sector).where(Sector.is_active == True)
        if sector_type:
            stmt = stmt.where(Sector.sector_type == sector_type)
        stmt = stmt.order_by(Sector.sector_name).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
    return {"count": len(rows), "data": [_model_to_dict(r) for r in rows]}


@router.get("/sectors/{sector_code}/stocks")
async def sector_stocks(sector_code: str):
    """获取某板块的成分股列表。"""
    async with async_session() as session:
        rows = (await session.execute(
            select(StockSector).where(StockSector.sector_code == sector_code)
        )).scalars().all()
    return {
        "sector_code": sector_code,
        "count": len(rows),
        "data": [{"stock_code": r.stock_code, "sector_name": r.sector_name} for r in rows],
    }


@router.get("/sectors/stock/{code}")
async def stock_sectors(code: str):
    """获取个股所属板块列表。"""
    pure = code.split(".")[0] if "." in code else code
    async with async_session() as session:
        rows = (await session.execute(
            select(StockSector).where(StockSector.stock_code == pure)
        )).scalars().all()
    return {
        "code": code,
        "count": len(rows),
        "data": [{"sector_code": r.sector_code, "sector_name": r.sector_name} for r in rows],
    }


# ==========================================================================
# 自选股
# ==========================================================================

@router.get("/watchlist")
async def get_watchlist():
    """获取自选股列表。"""
    async with async_session() as session:
        rows = (await session.execute(
            select(Watchlist).order_by(Watchlist.added_at.desc())
        )).scalars().all()
    return {"count": len(rows), "data": [_model_to_dict(r) for r in rows]}


@router.post("/watchlist")
async def add_to_watchlist(code: str, name: str = "", note: str = "", tags: str = ""):
    """添加自选股。"""
    async with async_session() as session:
        existing = (await session.execute(
            select(Watchlist).where(Watchlist.code == code)
        )).scalar_one_or_none()
        if existing:
            return {"message": f"{code} 已在自选中", "data": _model_to_dict(existing)}
        record = Watchlist(code=code, name=name, note=note, tags=tags)
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return {"message": "已添加", "data": _model_to_dict(record)}


@router.delete("/watchlist/{code}")
async def remove_from_watchlist(code: str):
    """移除自选股。"""
    from sqlalchemy import delete
    async with async_session() as session:
        result = await session.execute(
            delete(Watchlist).where(Watchlist.code == code)
        )
        await session.commit()
    if result.rowcount > 0:
        return {"message": f"已移除 {code}"}
    return {"message": f"{code} 不在自选中"}


# ==================== 财务风控 ====================

@router.get("/risk/list")
async def get_risk_list_api():
    """获取全部财务风险股票名单（从缓存读取）。"""
    from app.engine.finance_risk import get_risk_list
    risks = await get_risk_list()
    return {
        "count": len(risks),
        "data": [
            {
                "code": r.code,
                "name": r.name,
                "risk_type": r.risk_type,
                "risk_level": r.risk_level,
                "reason": r.reason,
                "loss_years": r.loss_years,
                "cumulative_loss": r.cumulative_loss,
                "latest_revenue": r.latest_revenue,
                "scan_date": r.scan_date,
            }
            for r in risks
        ],
    }


@router.get("/risk/check/{code}")
async def check_risk_api(code: str):
    """查询单只股票的财务风险（从缓存读取）。"""
    from app.engine.finance_risk import get_risk_by_code
    risk = await get_risk_by_code(code)
    if risk is None:
        return {"code": code, "has_risk": False}
    return {
        "code": risk.code,
        "has_risk": True,
        "risk_type": risk.risk_type,
        "risk_level": risk.risk_level,
        "reason": risk.reason,
        "loss_years": risk.loss_years,
        "cumulative_loss": risk.cumulative_loss,
        "latest_revenue": risk.latest_revenue,
        "scan_date": risk.scan_date,
    }


@router.post("/risk/scan")
async def trigger_risk_scan(source: ZhituSource = Depends(get_source)):
    """手动触发全市场财务排雷扫描（耗时约2-3分钟）。"""
    from app.engine.finance_risk import scan_all_stocks
    stats = await scan_all_stocks(source)
    return stats


# ==================== 全局状态 ====================

@router.get("/global-status")
async def get_global_status():
    """全局市场状态：当前日期、假期信息、风险股统计，供前端全页面同步。"""
    import datetime
    from app.engine.timing import evaluate
    from app.engine.calendar import is_trading_day, next_trading_day
    from app.engine.finance_risk import get_risk_list

    today = datetime.date.today()
    signal = evaluate(today)
    risk_stocks = await get_risk_list()
    extreme_count = sum(1 for r in risk_stocks if r.is_extreme_risk)

    return {
        "date": str(today),
        "is_trading_day": is_trading_day(today),
        "is_holiday": signal.is_holiday,
        "holiday_name": signal.holiday_name,
        "next_open_date": signal.next_open_date,
        "timing_light": signal.light.value,
        "timing_action": signal.action.value,
        "timing_reason": signal.reason,
        "risk_stock_total": len(risk_stocks),
        "risk_stock_extreme": extreme_count,
        "risk_codes": [r.code for r in risk_stocks],
    }


# ==================== 择时信号 ====================

@router.get("/timing/today")
async def get_timing_today(source: ZhituSource = Depends(get_source)):
    """获取今日择时信号（日历择时 + 盘面守卫）。"""
    import datetime
    from app.engine.timing import evaluate, Action
    from app.engine.bridge import fetch_market_snapshot, _fail_safe_signal
    from app.engine.guard import confirm

    today = datetime.date.today()
    signal = evaluate(today)

    if signal.action == Action.PROBE_ENTRY:
        try:
            snap = await fetch_market_snapshot(source)
            signal = confirm(signal, snap)
        except Exception as e:
            signal = _fail_safe_signal(today, str(e))

    return {
        "date": str(signal.date),
        "level": signal.level,
        "light": signal.light.value,
        "action": signal.action.value,
        "reason": signal.reason,
        "details": signal.details,
        "is_trading_day": signal.is_trading_day,
        "is_holiday": signal.is_holiday,
        "holiday_name": signal.holiday_name,
        "next_open_date": signal.next_open_date,
    }


@router.get("/timing/calendar")
async def get_timing_calendar():
    """获取结算日历信息：本月期货/期权结算日 + 倒计时。"""
    import datetime
    from app.engine.calendar import (
        futures_settlement_day,
        options_settlement_day,
        is_futures_settlement_week,
        is_options_settlement_week,
    )

    today = datetime.date.today()
    y, m = today.year, today.month

    fd = futures_settlement_day(y, m)
    od = options_settlement_day(y, m)

    # 如果本月结算日已过，计算下月
    next_m = m + 1 if m < 12 else 1
    next_y = y if m < 12 else y + 1
    next_fd = futures_settlement_day(next_y, next_m) if fd < today else fd
    next_od = options_settlement_day(next_y, next_m) if od < today else od

    return {
        "today": str(today),
        "futures_day": str(fd),
        "options_day": str(od),
        "next_futures_day": str(next_fd),
        "next_options_day": str(next_od),
        "days_to_futures": (next_fd - today).days,
        "days_to_options": (next_od - today).days,
        "is_futures_week": is_futures_settlement_week(today),
        "is_options_week": is_options_settlement_week(today),
    }


@router.get("/timing/{date}")
async def get_timing_by_date(date: str):
    """获取指定日期的日历择时信号（仅日历层，无盘面数据）。"""
    import datetime
    from app.engine.timing import evaluate

    try:
        d = datetime.date.fromisoformat(date)
    except ValueError:
        return {"error": f"日期格式错误: {date}，应为 YYYY-MM-DD"}

    signal = evaluate(d)
    return {
        "date": str(signal.date),
        "level": signal.level,
        "light": signal.light.value,
        "action": signal.action.value,
        "reason": signal.reason,
        "details": signal.details,
        "is_trading_day": signal.is_trading_day,
        "is_holiday": signal.is_holiday,
        "holiday_name": signal.holiday_name,
        "next_open_date": signal.next_open_date,
    }


# ==========================================================================
# 通配股池查询（必须放在最后，避免拦截具体路径）
# ==========================================================================

@router.get("/{pool_type}/{date}")
async def get_pool(
    pool_type: str,
    date: str,
    save: bool = Query(False, description="是否同时保存到结构化表"),
    source: ZhituSource = Depends(get_source),
):
    """获取指定日期的股池数据（实时从 ZhituAPI 获取）。"""
    data = await source.get_pool(pool_type, date)

    if save and data:
        if pool_type == "ztgc":
            await sync_limit_up_pool(source, date)
        elif pool_type == "zbgc":
            await sync_broken_board_pool(source, date)
        elif pool_type == "qsgc":
            await sync_strong_pool(source, date)

    return {
        "pool_type": pool_type,
        "pool_name": _POOL_NAMES.get(pool_type, pool_type),
        "date": date,
        "count": len(data),
        "data": data,
    }
