"""K线数据服务层。

优先从本地 SQLite（daily_kline 表，1578万行历史数据）读取，
仅在本地无数据时回退到 ZhituAPI，节省 API 配额。

查询策略：
  1. 日K线 → 先查 SQLite，不足则补充 ZhituAPI
  2. 分钟/周/月K线 → 直接走 ZhituAPI（本地仅存日线）
"""

import logging
from typing import Any

import sqlite3
from pathlib import Path

from app.config import settings
from app.data.source_zhitu import ZhituSource, normalize_code

logger = logging.getLogger(__name__)

DB_PATH = Path(settings.database_url.replace("sqlite:///", "")).resolve()


def _query_sqlite_kline(
    code: str,
    start: str = "",
    end: str = "",
    limit: int = 0,
) -> list[dict[str, Any]]:
    """从 SQLite daily_kline 表查询日K线。"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT trade_date, open, high, low, close, pre_close, volume, amount, change_pct, amplitude, turnover FROM daily_kline WHERE code = ?"
        params: list[Any] = [code]

        if start:
            # 支持 YYYYMMDD 和 YYYY-MM-DD 两种格式
            fmt_start = f"{start[:4]}-{start[4:6]}-{start[6:]}" if len(start) == 8 else start
            sql += " AND trade_date >= ?"
            params.append(fmt_start)
        if end:
            fmt_end = f"{end[:4]}-{end[4:6]}-{end[6:]}" if len(end) == 8 else end
            sql += " AND trade_date <= ?"
            params.append(fmt_end)

        if limit > 0:
            sql += " ORDER BY trade_date DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            rows = list(reversed(rows))
        else:
            sql += " ORDER BY trade_date ASC"
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                "d": row["trade_date"],
                "o": row["open"],
                "h": row["high"],
                "l": row["low"],
                "c": row["close"],
                "yc": row["pre_close"],
                "v": row["volume"],
                "a": row["amount"],
                "zf": row["change_pct"],
                "zd": row["amplitude"],
                "hs": row["turnover"],
            }
            for row in rows
        ]
    finally:
        conn.close()


async def get_kline(
    source: ZhituSource,
    code: str,
    level: str = "d",
    adjust: str = "n",
    start: str = "",
    end: str = "",
) -> list[dict[str, Any]]:
    """获取历史K线数据。日线优先走本地 SQLite。"""
    code = normalize_code(code)

    # 非日线直接走 API
    if level != "d":
        return await source.get_history_kline(code, level, adjust, start, end)

    # 日线：先查本地
    local = _query_sqlite_kline(code, start, end)
    if local:
        logger.debug("本地K线命中: %s, %d 条", code, len(local))
        return local

    # 本地无数据，回退 API
    logger.debug("本地K线未命中: %s, 回退API", code)
    return await source.get_history_kline(code, level, adjust, start, end)


async def get_latest_kline(
    source: ZhituSource,
    code: str,
    level: str = "d",
    adjust: str = "n",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """获取最新 N 条K线。日线优先走本地 SQLite。"""
    code = normalize_code(code)

    if level != "d":
        return await source.get_latest_kline(code, level, adjust, limit)

    local = _query_sqlite_kline(code, limit=limit)
    if local:
        logger.debug("本地最新K线命中: %s, %d 条", code, len(local))
        return local

    logger.debug("本地最新K线未命中: %s, 回退API", code)
    return await source.get_latest_kline(code, level, adjust, limit)
