from fastapi import APIRouter, Depends, Query

from app.data.dependencies import get_source
from app.data.source_zhitu import ZhituSource
from app.data import kline_service

router = APIRouter(prefix="/api/stocks", tags=["股票"])


@router.get("/list")
async def stock_list(source: ZhituSource = Depends(get_source)):
    """获取全市场股票列表。"""
    data = await source.get_stock_list()
    return {"count": len(data), "data": data}


@router.get("/realtime/{code}")
async def realtime_quote(code: str, source: ZhituSource = Depends(get_source)):
    """获取单只股票实时行情。"""
    data = await source.get_realtime_quote(code)
    return {"data": data}


@router.get("/realtime")
async def realtime_all(source: ZhituSource = Depends(get_source)):
    """获取全市场实时行情快照（每分钟最多调用1次）。"""
    data = await source.get_realtime_all()
    return {"count": len(data), "data": data}


@router.get("/kline/{code}")
async def kline(
    code: str,
    level: str = Query("d", description="K线级别: 5/15/30/60/d/w/m/y"),
    adjust: str = Query("n", description="复权: n/f/b/fr/br"),
    start: str = Query("", description="开始日期 YYYYMMDD"),
    end: str = Query("", description="结束日期 YYYYMMDD"),
    source: ZhituSource = Depends(get_source),
):
    """获取历史K线数据。日线优先从本地 SQLite 读取。"""
    data = await kline_service.get_kline(source, code, level, adjust, start, end)
    return {"count": len(data), "data": data}


@router.get("/kline/{code}/latest")
async def kline_latest(
    code: str,
    level: str = Query("d"),
    adjust: str = Query("n"),
    limit: int = Query(20, ge=1, le=500),
    source: ZhituSource = Depends(get_source),
):
    """获取最新N条K线。日线优先从本地 SQLite 读取。"""
    data = await kline_service.get_latest_kline(source, code, level, adjust, limit)
    return {"count": len(data), "data": data}


@router.get("/company/{code}/{info_type}")
async def company_info(
    code: str,
    info_type: str,
    source: ZhituSource = Depends(get_source),
):
    """获取公司信息。

    info_type: gsjj/sszs/ljgg/cwzb/sdgd/ltgd/ssbk/jyfw 等
    """
    data = await source.get_company_info(code, info_type)
    return {"data": data}


@router.get("/finance/{code}/{report_type}")
async def finance_report(
    code: str,
    report_type: str,
    start: str = Query("", description="开始日期 YYYYMMDD"),
    end: str = Query("", description="结束日期 YYYYMMDD"),
    source: ZhituSource = Depends(get_source),
):
    """获取财务报表。

    report_type: balance/income/cashflow/ratios/capital/topholder/flowholder/hm
    """
    data = await source.get_finance_report(code, report_type, start, end)
    return {"count": len(data), "data": data}


@router.get("/indicator/{code}/{indicator}")
async def technical_indicator(
    code: str,
    indicator: str,
    level: str = Query("d"),
    adjust: str = Query("n"),
    start: str = Query(None),
    end: str = Query(None),
    source: ZhituSource = Depends(get_source),
):
    """获取技术指标（macd/ma/boll/kdj）。"""
    data = await source.get_technical_indicator(code, indicator, level, adjust, start, end)
    return {"count": len(data), "data": data}


@router.get("/fund-flow/{code}")
async def fund_flow(
    code: str,
    start: str = Query(None),
    end: str = Query(None),
    limit: int = Query(None, ge=1),
    source: ZhituSource = Depends(get_source),
):
    """获取资金流向数据。"""
    data = await source.get_fund_flow(code, start, end, limit)
    return {"count": len(data), "data": data}


@router.get("/instrument/{code}")
async def instrument(code: str, source: ZhituSource = Depends(get_source)):
    """获取股票基础信息（涨跌停价、市值、停牌状态）。"""
    data = await source.get_instrument(code)
    return {"data": data}


@router.get("/order-book/{code}")
async def order_book(code: str, source: ZhituSource = Depends(get_source)):
    """获取买卖五档盘口。"""
    data = await source.get_order_book(code)
    return {"data": data}


@router.post("/kline/update/{code}")
async def update_kline_single(code: str, source: ZhituSource = Depends(get_source)):
    """手动触发单只股票的日K线增量更新。"""
    from app.data.kline_updater import update_single_stock
    count = await update_single_stock(source, code)
    return {"code": code, "new_bars": count}


@router.post("/kline/update-all")
async def update_kline_all(source: ZhituSource = Depends(get_source)):
    """手动触发全市场日K线增量更新。耗时较长，建议通过定时任务执行。"""
    from app.data.kline_updater import update_all_stocks
    result = await update_all_stocks(source)
    return result
