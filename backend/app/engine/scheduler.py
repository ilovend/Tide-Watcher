import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.data.source_zhitu import ZhituSource
from app.engine.registry import get_scheduled_strategies
from app.engine.runner import run_strategy

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_source: ZhituSource | None = None


async def start_scheduler() -> None:
    """启动策略调度器，根据注册表中的 schedule 自动创建定时任务。"""
    global _scheduler, _source

    _source = ZhituSource()
    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    for meta in get_scheduled_strategies():
        parts = meta.schedule.split(":")
        if len(parts) != 2:
            logger.warning("策略 '%s' 的 schedule 格式无效: %s，应为 HH:MM", meta.name, meta.schedule)
            continue

        hour, minute = parts
        trigger = CronTrigger(
            day_of_week="mon-fri",
            hour=int(hour),
            minute=int(minute),
            timezone="Asia/Shanghai",
        )

        _scheduler.add_job(
            run_strategy,
            trigger=trigger,
            args=[meta, _source],
            id=f"strategy_{meta.name}",
            name=f"策略: {meta.name}",
            replace_existing=True,
        )
        logger.info("定时任务已注册: %s → 每交易日 %s", meta.name, meta.schedule)

    # ----- 数据同步任务 -----
    from app.store.sync import sync_stock_list, sync_all_pools
    from app.data.kline_updater import update_all_stocks
    import datetime

    async def _sync_stock_list():
        await sync_stock_list(_source)

    async def _sync_pools():
        today = datetime.date.today().strftime("%Y-%m-%d")
        await sync_all_pools(_source, today)

    async def _update_kline():
        await update_all_stocks(_source)

    # ----- 择时引擎任务 -----
    from app.engine.bridge import run_timing_pipeline

    async def _run_timing():
        signal = await run_timing_pipeline(_source)
        logger.info("择时信号: %s", signal)

    _scheduler.add_job(
        _run_timing,
        trigger=CronTrigger(day_of_week="mon-fri", hour=14, minute=30, timezone="Asia/Shanghai"),
        id="timing_pipeline",
        name="择时: 14:30 盘前决策",
        replace_existing=True,
    )

    _scheduler.add_job(
        _sync_pools,
        trigger=CronTrigger(day_of_week="mon-fri", hour=15, minute=30, timezone="Asia/Shanghai"),
        id="sync_pools",
        name="同步: 股池快照",
        replace_existing=True,
    )
    _scheduler.add_job(
        _update_kline,
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=0, timezone="Asia/Shanghai"),
        id="update_kline",
        name="增量: 日K线",
        replace_existing=True,
    )
    _scheduler.add_job(
        _sync_stock_list,
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=30, timezone="Asia/Shanghai"),
        id="sync_stock_list",
        name="同步: 股票列表",
        replace_existing=True,
    )
    # ----- 财务排雷任务 -----
    from app.engine.finance_risk import scan_all_stocks

    async def _scan_finance_risk():
        await scan_all_stocks(_source)

    # 每季度首月15日执行（1月/4月/7月/10月，覆盖财报季后）
    _scheduler.add_job(
        _scan_finance_risk,
        trigger=CronTrigger(month="1,4,7,10", day=15, hour=18, minute=0, timezone="Asia/Shanghai"),
        id="scan_finance_risk",
        name="排雷: 季度财务扫描",
        replace_existing=True,
    )

    logger.info("数据同步任务已注册: 择时(14:30) + 股池(15:30) + K线(16:00) + 股票列表(16:30) + 排雷(季度)")

    _scheduler.start()
    logger.info("策略调度器已启动，共 %d 个定时任务", len(_scheduler.get_jobs()))


async def stop_scheduler() -> None:
    """关闭调度器并释放数据源连接。"""
    global _scheduler, _source

    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None

    if _source:
        await _source.close()
        _source = None

    logger.info("策略调度器已关闭")
