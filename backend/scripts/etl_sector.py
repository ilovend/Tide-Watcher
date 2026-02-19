"""ETL 脚本：将 MySQL sector + stock_sector 静态映射数据迁移到 SQLite。

sector: ~2218 行板块定义
stock_sector: ~20.6万行股票-板块关联

用法：
    cd backend
    ./venv/Scripts/python scripts/etl_sector.py
"""

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymysql
from app.config import settings

DB_PATH = Path(settings.database_url.replace("sqlite:///", "")).resolve()


def main():
    print("=" * 60)
    print("ETL: MySQL sector + stock_sector → SQLite")
    print("=" * 60)

    # 1. 准备 SQLite
    lite = sqlite3.connect(str(DB_PATH))
    lite.execute("PRAGMA journal_mode=WAL")
    lite.execute("PRAGMA synchronous=OFF")

    # 确保表存在
    lite.execute("""
        CREATE TABLE IF NOT EXISTS sector (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sector_code VARCHAR(30) UNIQUE,
            sector_name VARCHAR(100),
            sector_type VARCHAR(20),
            stock_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    lite.execute("""
        CREATE TABLE IF NOT EXISTS stock_sector (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code VARCHAR(12),
            sector_code VARCHAR(30),
            sector_name VARCHAR(100) DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    lite.commit()

    # 清空旧数据
    for table in ("sector", "stock_sector"):
        count = lite.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count > 0:
            print(f"清空 {table}: {count:,} 行")
            lite.execute(f"DELETE FROM {table}")
    lite.execute("DROP INDEX IF EXISTS ix_ss_stock_sector")
    lite.commit()

    # 2. 连接 MySQL
    mysql_conn = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
    )

    # 3. 迁移 sector
    print("\n--- sector ---")
    with mysql_conn.cursor() as cur:
        cur.execute("SELECT sector_code, sector_name, sector_type, stock_count, is_active FROM sector")
        rows = cur.fetchall()
    print(f"MySQL sector: {len(rows):,} 行")

    lite.executemany(
        "INSERT INTO sector (sector_code, sector_name, sector_type, stock_count, is_active) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    lite.commit()
    print(f"写入 SQLite: {len(rows):,} 行")

    # 4. 迁移 stock_sector
    print("\n--- stock_sector ---")
    with mysql_conn.cursor() as cur:
        cur.execute("SELECT stock_code, sector_code, sector_name FROM stock_sector")
        rows = cur.fetchall()
    print(f"MySQL stock_sector: {len(rows):,} 行")

    start = time.time()
    batch_size = 50000
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        lite.executemany(
            "INSERT INTO stock_sector (stock_code, sector_code, sector_name) VALUES (?, ?, ?)",
            batch,
        )
        lite.commit()
        print(f"  写入: {min(i + batch_size, len(rows)):,} / {len(rows):,}")

    elapsed = time.time() - start
    print(f"写入完成: {len(rows):,} 行, {elapsed:.1f}秒")

    # 5. 创建索引
    print("\n创建索引...")
    lite.execute("CREATE INDEX IF NOT EXISTS ix_stock_sector_stock ON stock_sector (stock_code)")
    lite.execute("CREATE INDEX IF NOT EXISTS ix_stock_sector_sector ON stock_sector (sector_code)")
    lite.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_ss_stock_sector ON stock_sector (stock_code, sector_code)")
    lite.execute("CREATE INDEX IF NOT EXISTS ix_sector_type ON sector (sector_type)")
    lite.commit()
    print("索引创建完成")

    print(f"\n{'=' * 60}")
    print("ETL 完成!")
    print(f"{'=' * 60}")

    mysql_conn.close()
    lite.close()


if __name__ == "__main__":
    main()
