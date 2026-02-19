"""股池监控 — 涨停/跌停/强势/炸板/次新 五大股池实时查看。"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import datetime
import asyncio
import streamlit as st
import pandas as pd

from app.data.source_zhitu import ZhituSource

st.set_page_config(page_title="股池监控 | Tide-Watcher", page_icon="📋", layout="wide")


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def get_source():
    if "source" not in st.session_state:
        st.session_state.source = ZhituSource()
    return st.session_state.source


POOLS = {
    "ztgc": "🔴 涨停股池",
    "dtgc": "🟢 跌停股池",
    "qsgc": "🟠 强势股池",
    "zbgc": "🟡 炸板股池",
    "cxgc": "🔵 次新股池",
}

st.markdown("# 📋 股池监控")
st.markdown("实时跟踪涨停、跌停、强势、炸板、次新股池")

col_date, col_pool = st.columns([1, 3])
with col_date:
    date = st.date_input("日期", value=datetime.date.today())
with col_pool:
    pool_code = st.radio("股池", list(POOLS.keys()), format_func=lambda x: POOLS[x], horizontal=True)

date_str = date.strftime("%Y-%m-%d")

try:
    source = get_source()
    data = run_async(source.get_pool(pool_code, date_str))
except Exception as e:
    st.error(f"数据获取失败: {e}")
    data = []

if not data:
    st.info("暂无数据（非交易日或接口未返回）")
else:
    st.markdown(f"**{POOLS[pool_code]}** — {date_str} — 共 **{len(data)}** 只")

    rows = []
    for s in data:
        row = {
            "代码": s.get("dm", ""),
            "名称": s.get("mc", ""),
            "价格": f"{s.get('p', 0):.2f}" if s.get("p") else "-",
            "涨幅%": f"{s.get('zf', 0):+.2f}" if s.get("zf") is not None else "-",
        }
        if pool_code == "ztgc":
            lbc = s.get("lbc", 0) or 0
            row["连板"] = f"{'🔥' * min(lbc, 5)} {lbc}" if lbc >= 2 else str(lbc)
            row["封板时间"] = s.get("fbt", "-")
            row["炸板次数"] = s.get("zbc", 0)
            row["统计"] = s.get("tj", "-")
        elif pool_code == "zbgc":
            row["炸板次数"] = s.get("zbc", 0)
            row["首封时间"] = s.get("fbt", "-")
        elif pool_code == "dtgc":
            row["连续跌停"] = s.get("lbc", 0)
        elif pool_code == "qsgc":
            row["量比"] = f"{s.get('lb', 0):.1f}" if s.get("lb") else "-"

        cje = s.get("cje", 0) or 0
        row["成交额"] = f"{cje / 1e8:.2f}亿" if cje >= 1e8 else f"{cje / 1e4:.0f}万" if cje >= 1e4 else "-"
        rows.append(row)

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=min(len(rows) * 38 + 40, 700))
