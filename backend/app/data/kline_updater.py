"""日K线增量更新服务。

每日盘后自动从 ZhituAPI 获取全市场当天日K线数据，
增量追加到 SQLite daily_kline 表。

更新策略：
  1. 查询 SQLite 中每只股票的最新日期
  2. 从 ZhituAPI 获取该日期之后的新数据
  3. 追加写入 SQLite
  4. 支持按单只股票或全市场批量更新
"""

import asyncio
import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.config import settings
from app.data.source_zhitu import ZhituSource, normalize_code

logger = logging.getLogger(__name__)

DB_PATH = Path(settings.database_url.replace("sqlite:///", "")).resolve()

INSERT_SQL = (
    "INSERT INTO daily_kline "
    "(code, trade_date, open, high, low, close, pre_close, volume, amount, change_pct, amplitude, turnover) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def _get_latest_date(code: str) -> str | None:
    """查询某只股票在 SQLite 中的最新交易日期。"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute(
            "SELECT MAX(trade_date) FROM daily_kline WHERE code = ?", (code,)
        ).fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def _get_all_codes_latest() -> dict[str, str]:
    """查询所有股票在 SQLite 中的最新交易日期。返回 {code: latest_date}。"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT code, MAX(trade_date) FROM daily_kline GROUP BY code"
        ).fetchall()
        return {row[0]: row[1] for row in rows if row[1]}
    finally:
        conn.close()


def _insert_kline_batch(records: list[tuple]) -> int:
    """批量写入K线数据到 SQLite。返回写入行数。"""
    if not records:
        return 0
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        conn.executemany(INSERT_SQL, records)
        conn.commit()
        return len(records)
    finally:
        conn.close()


def _api_bar_to_tuple(code: str, bar: dict[str, Any]) -> tuple | None:
    """将 ZhituAPI 返回的K线数据转为 SQLite 插入元组。"""
    d = bar.get("d", "")
    o = bar.get("o")
    if o is None:
        return None
    # 日期格式统一为 YYYY-MM-DD
    if len(d) == 8:
        d = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return (
        code,
        d,
        float(o),
        float(bar.get("h", 0)),
        float(bar.get("l", 0)),
        float(bar.get("c", 0)),
        float(bar["yc"]) if bar.get("yc") is not None else None,
        float(bar.get("v", 0)),
        float(bar.get("a", 0)),
        float(bar["zf"]) if bar.get("zf") is not None else None,
        float(bar["zd"]) if bar.get("zd") is not None else None,
        float(bar["hs"]) if bar.get("hs") is not None else None,
    )


async def update_single_stock(source: ZhituSource, code: str) -> int:
    """增量更新单只股票的日K线。返回新增行数。"""
    code = normalize_code(code)
    latest = _get_latest_date(code)

    if latest:
        # 从最新日期的下一天开始
        start_date = latest.replace("-", "")
    else:
        # 无历史数据，取最近一年
        start_date = (date.today() - timedelta(days=365)).strftime("%Y%m%d")

    end_date = date.today().strftime("%Y%m%d")

    if start_date >= end_date:
        return 0

    try:
        bars = await source.get_history_kline(code, "d", "n", start_date, end_date)
    except Exception:
        logger.warning("获取 %s K线失败，跳过", code)
        return 0

    if not bars:
        return 0

    # 过滤已有数据（防止重复）
    records = []
    for bar in bars:
        d = bar.get("d", "")
        if len(d) == 8:
            d = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        if latest and d <= latest:
            continue
        t = _api_bar_to_tuple(code, bar)
        if t:
            records.append(t)

    inserted = _insert_kline_batch(records)
    if inserted > 0:
        logger.info("增量更新 %s: +%d 条 (最新: %s)", code, inserted, records[-1][1])
    return inserted


async def update_all_stocks(source: ZhituSource) -> dict[str, int]:
    """增量更新全市场日K线。

    策略：获取全市场股票列表，逐只更新。
    使用 asyncio.Semaphore 控制并发避免触发频率限制。
    """
    stock_list = await source.get_stock_list()
    if not stock_list:
        logger.error("获取股票列表失败，无法更新")
        return {"total": 0, "updated": 0, "new_bars": 0}

    # 获取本地所有股票的最新日期
    local_latest = _get_all_codes_latest()
    today = date.today().strftime("%Y-%m-%d")

    # 筛选需要更新的股票（本地最新日期 < 今天）
    codes_to_update = []
    for stock in stock_list:
        dm = stock.get("dm", "")
        jys = stock.get("jys", "")
        exchange = "SH" if jys == "sh" else "SZ" if jys == "sz" else "BJ"
        code = f"{dm}.{exchange}"
        latest = local_latest.get(code, "")
        if latest < today:
            codes_to_update.append(code)

    logger.info("需要更新的股票: %d / %d", len(codes_to_update), len(stock_list))

    # 逐只更新（串行，避免频率限制）
    total_new = 0
    updated_count = 0
    sem = asyncio.Semaphore(3)  # 最多3个并发

    async def _update_one(c: str) -> int:
        async with sem:
            return await update_single_stock(source, c)

    # 分批并发
    batch_size = 20
    for i in range(0, len(codes_to_update), batch_size):
        batch = codes_to_update[i:i + batch_size]
        results = await asyncio.gather(
            *[_update_one(c) for c in batch],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, int) and r > 0:
                total_new += r
                updated_count += 1
        logger.info(
            "进度: %d/%d | 已更新: %d 只 | 新增: %d 条",
            min(i + batch_size, len(codes_to_update)),
            len(codes_to_update),
            updated_count,
            total_new,
        )

    logger.info(
        "全市场K线增量更新完成: %d 只股票更新 | 共新增 %d 条K线",
        updated_count, total_new,
    )
    return {
        "total": len(codes_to_update),
        "updated": updated_count,
        "new_bars": total_new,
    }
