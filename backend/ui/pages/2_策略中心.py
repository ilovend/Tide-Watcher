"""策略中心 — 策略管理、执行和信号历史。"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import asyncio
import streamlit as st
import pandas as pd

from app.data.source_zhitu import ZhituSource
from app.engine.registry import get_all_strategies
from app.engine.runner import run_strategy

st.set_page_config(page_title="策略中心 | Tide-Watcher", page_icon="🧠", layout="wide")


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


st.markdown("# 🧠 策略中心")
st.markdown("管理和执行选股策略，查看历史信号")

tab_list, tab_signals = st.tabs(["📋 策略列表", "📜 信号历史"])

# ==================== 策略列表 ====================
with tab_list:
    strategies = list(get_all_strategies().values())
    if not strategies:
        st.info("暂无已注册策略。在 `strategies/` 目录创建策略文件并使用 `@strategy` 装饰器注册。")
    else:
        cols = st.columns(2)
        for i, meta in enumerate(strategies):
            with cols[i % 2]:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"### 🧬 {meta.name}")
                        st.caption(meta.description or "暂无描述")
                        tags = " ".join([f"`{t}`" for t in (meta.tags or [])])
                        if tags:
                            st.markdown(tags)
                        if meta.schedule:
                            st.markdown(f"⏰ 每交易日 **{meta.schedule}** 自动执行")
                    with c2:
                        enabled = "✅ 已启用" if meta.enabled else "⏸️ 已禁用"
                        st.markdown(f"**{enabled}**")
                        if st.button(f"▶ 执行", key=f"run_{meta.name}"):
                            with st.spinner(f"正在执行 {meta.name}..."):
                                try:
                                    source = get_source()
                                    result = run_async(run_strategy(meta, source))
                                    st.success(f"✅ 完成！产生 {len(result)} 条信号")
                                    if result:
                                        df = pd.DataFrame([
                                            {"代码": s["stock_code"], "名称": s["stock_name"],
                                             "评分": s["score"], "理由": s["reason"]}
                                            for s in result
                                        ])
                                        st.dataframe(df, use_container_width=True, hide_index=True)
                                except Exception as e:
                                    st.error(f"执行失败: {e}")

# ==================== 信号历史 ====================
with tab_signals:
    try:
        from app.store.database import async_session
        from sqlalchemy import text

        async def _load_signals(limit=100):
            async with async_session() as session:
                r = await session.execute(text(
                    "SELECT id, strategy_name, stock_code, stock_name, signal_date, score, reason, created_at "
                    "FROM strategy_signals ORDER BY created_at DESC LIMIT :limit"
                ), {"limit": limit})
                return r.fetchall()

        signals = run_async(_load_signals())
        if not signals:
            st.info("暂无信号记录，请先执行策略")
        else:
            st.markdown(f"**最近 {len(signals)} 条信号**")
            rows = []
            for s in signals:
                score = s[5]
                level = "🔴 强" if score >= 70 else "🟡 中" if score >= 40 else "⚪ 弱"
                rows.append({
                    "策略": s[1],
                    "代码": s[2],
                    "名称": s[3],
                    "日期": s[4],
                    "评分": f"{level} {score:.0f}",
                    "理由": (s[6] or "")[:60],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=600)
    except Exception as e:
        st.error(f"加载信号历史失败: {e}")
