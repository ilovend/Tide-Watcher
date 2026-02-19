"""修复 daily_kline 表中 pre_close 和 change_pct 字段。

用前一天的 close 填充 pre_close，然后计算 change_pct。
按股票分组处理，日期升序排列。

用法：
    cd backend
    ./venv/Scripts/python scripts/fix_kline_pct.py
"""

import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings

DB_PATH = Path(settings.database_url.replace("sqlite:///", "")).resolve()


def main():
    print("=" * 60)
    print("修复 daily_kline: pre_close + change_pct")
    print("=" * 60)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-200000")

    # 获取所有股票代码
    codes = [r[0] for r in conn.execute(
        "SELECT DISTINCT code FROM daily_kline ORDER BY code"
    ).fetchall()]
    print(f"共 {len(codes):,} 只股票需要处理")

    start = time.time()
    updated_total = 0

    for i, code in enumerate(codes):
        # 按日期升序取该股票所有K线
        rows = conn.execute(
            "SELECT id, trade_date, close, pre_close, change_pct "
            "FROM daily_kline WHERE code = ? ORDER BY trade_date ASC",
            (code,),
        ).fetchall()

        updates = []
        prev_close = None

        for row_id, trade_date, close, pre_close, change_pct in rows:
            need_update = False
            new_pc = pre_close
            new_pct = change_pct

            # 填充 pre_close
            if (pre_close is None or pre_close == 0) and prev_close is not None:
                new_pc = prev_close
                need_update = True

            # 计算 change_pct
            if new_pc and new_pc > 0 and close and close > 0:
                calc_pct = round((close - new_pc) / new_pc * 100, 2)
                if change_pct is None or change_pct == 0:
                    new_pct = calc_pct
                    need_update = True

            if need_update:
                updates.append((new_pc, new_pct, row_id))

            prev_close = close

        if updates:
            conn.executemany(
                "UPDATE daily_kline SET pre_close = ?, change_pct = ? WHERE id = ?",
                updates,
            )
            updated_total += len(updates)

        # 每100只股票提交一次
        if (i + 1) % 100 == 0:
            conn.commit()
            elapsed = time.time() - start
            speed = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"\r  进度: {i+1:>5,}/{len(codes):,} | 更新: {updated_total:>10,} 行 | {speed:.0f} 只/秒", end="", flush=True)

    conn.commit()
    elapsed = time.time() - start
    print(f"\n\n{'=' * 60}")
    print(f"修复完成: {updated_total:,} 行更新 | {elapsed:.1f}秒")
    print(f"{'=' * 60}")

    conn.close()


if __name__ == "__main__":
    main()
