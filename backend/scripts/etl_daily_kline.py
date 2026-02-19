"""ETL 脚本：将 MySQL stock_daily 日K线数据迁移到 SQLite daily_kline 表。

使用原生 sqlite3 + executemany + WAL 模式，
分批处理（每批 50000 行），预计 5~10 分钟完成 1646 万行迁移。

用法：
    cd backend
    venv/Scripts/python scripts/etl_daily_kline.py
"""

import sqlite3
import sys
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymysql
from app.config import settings

BATCH_SIZE = 50000
DB_PATH = Path(settings.database_url.replace("sqlite:///", "")).resolve()


def normalize_code(code: str) -> str:
    code = code.strip()
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return code


def to_float(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


def main():
    print("=" * 60)
    print("ETL: MySQL stock_daily → SQLite daily_kline")
    print("=" * 60)

    # 1. 准备 SQLite（原生连接，性能最大化）
    lite = sqlite3.connect(str(DB_PATH))
    lite.execute("PRAGMA journal_mode=WAL")
    lite.execute("PRAGMA synchronous=OFF")
    lite.execute("PRAGMA cache_size=-200000")  # 200MB 缓存
    lite.execute("PRAGMA temp_store=MEMORY")

    # 确保表存在
    lite.execute("""
        CREATE TABLE IF NOT EXISTS daily_kline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(12),
            trade_date VARCHAR(10),
            open FLOAT, high FLOAT, low FLOAT, close FLOAT,
            pre_close FLOAT, volume FLOAT, amount FLOAT,
            change_pct FLOAT, amplitude FLOAT, turnover FLOAT
        )
    """)
    lite.commit()

    existing = lite.execute("SELECT COUNT(*) FROM daily_kline").fetchone()[0]
    print(f"SQLite: {DB_PATH}")
    print(f"已有 daily_kline: {existing:,} 行")

    if existing > 0:
        print(f"已有 {existing:,} 行，自动清空重导...")
        lite.execute("DELETE FROM daily_kline")
        lite.execute("DROP INDEX IF EXISTS ix_daily_kline_code_date")
        lite.execute("DROP INDEX IF EXISTS ix_daily_kline_code")
        lite.execute("DROP INDEX IF EXISTS ix_daily_kline_trade_date")
        lite.commit()
        print("已清空")

    # 2. 连接 MySQL
    mysql_conn = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.SSCursor,  # 服务端游标，减少内存
    )

    cur = mysql_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM stock_daily")
    total = cur.fetchone()[0]
    print(f"MySQL stock_daily: {total:,} 行")
    print(f"批次大小: {BATCH_SIZE:,}")
    print()

    # 3. 流式读取 + 批量写入
    cur.execute(
        "SELECT code, trade_date, `open`, high, low, `close`, pre_close, "
        "volume, amount, change_pct, amplitude, turnover "
        "FROM stock_daily ORDER BY code, trade_date"
    )

    insert_sql = (
        "INSERT INTO daily_kline "
        "(code, trade_date, open, high, low, close, pre_close, volume, amount, change_pct, amplitude, turnover) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    start = time.time()
    inserted = 0
    skipped = 0
    batch = []

    while True:
        row = cur.fetchone()
        if row is None:
            break

        code_raw, td, o, h, l, c, pc, v, a, cp, amp, tn = row
        o_f = to_float(o)

        # 跳过无效数据（负价格）
        if o_f is not None and o_f < 0:
            skipped += 1
            continue

        batch.append((
            normalize_code(str(code_raw)),
            td.strftime("%Y-%m-%d") if td else "",
            o_f or 0.0,
            to_float(h) or 0.0,
            to_float(l) or 0.0,
            to_float(c) or 0.0,
            to_float(pc),
            to_float(v) or 0.0,
            to_float(a) or 0.0,
            to_float(cp),
            to_float(amp),
            to_float(tn),
        ))

        if len(batch) >= BATCH_SIZE:
            lite.executemany(insert_sql, batch)
            lite.commit()
            inserted += len(batch)
            batch.clear()

            elapsed = time.time() - start
            speed = inserted / elapsed if elapsed > 0 else 0
            pct = (inserted + skipped) / total * 100
            print(f"\r  进度: {pct:5.1f}% | {inserted:>12,} 行 | {speed:>8,.0f} 行/秒 | 跳过: {skipped:,}", end="", flush=True)

    # 写入剩余
    if batch:
        lite.executemany(insert_sql, batch)
        lite.commit()
        inserted += len(batch)

    elapsed = time.time() - start
    print(f"\n\n{'=' * 60}")
    print(f"数据写入完成: {inserted:,} 行 | 跳过: {skipped:,} | 耗时: {elapsed:.1f}秒")

    # 4. 创建索引
    print("创建索引 (code, trade_date)...")
    idx_start = time.time()
    lite.execute("CREATE INDEX IF NOT EXISTS ix_daily_kline_code_date ON daily_kline (code, trade_date)")
    lite.commit()
    print(f"索引创建完成: {time.time() - idx_start:.1f}秒")

    print(f"{'=' * 60}")

    cur.close()
    mysql_conn.close()
    lite.close()


if __name__ == "__main__":
    main()
