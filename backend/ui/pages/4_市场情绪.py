"""市场情绪 — 基于涨停数据的情绪阶段监测与历史走势。"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import asyncio
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from app.store.database import async_session
from sqlalchemy import text

st.set_page_config(page_title="市场情绪 | Tide-Watcher", page_icon="🌡️", layout="wide")


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


PHASE_CFG = {
    "ice":     ("❄️ 冰点期", "#60a5fa"),
    "retreat": ("📉 退潮期", "#4ade80"),
    "ferment": ("⚡ 发酵期", "#facc15"),
    "boom":    ("🔥 爆发期", "#fb923c"),
    "frenzy":  ("🌋 狂热期", "#ef4444"),
}

st.markdown("# 🌡️ 市场情绪")
st.markdown("基于涨停数据的市场情绪监测与阶段判断")

async def _load_data(limit=60):
    async with async_session() as session:
        r = await session.execute(text(
            "SELECT trade_date, phase, phase_score, limit_up_count, broken_board_count, "
            "broken_rate, max_streak, first_board_count, promotion_rate, total_limit_amount "
            "FROM emotion_snapshot ORDER BY trade_date DESC LIMIT :limit"
        ), {"limit": limit})
        return r.fetchall()

data = run_async(_load_data())

if not data:
    st.info("暂无情绪数据。情绪快照会在每日盘后股池同步时自动计算。")
    st.stop()

latest = data[0]
phase_label, phase_color = PHASE_CFG.get(latest[1], ("❓ 未知", "#94a3b8"))

# 顶部指标卡片
cols = st.columns(5)
with cols[0]:
    st.markdown(f"""
    <div style="background:#1e293b;border-radius:12px;padding:16px;text-align:center;">
        <div style="color:#94a3b8;font-size:12px;">当前阶段</div>
        <div style="color:{phase_color};font-size:24px;font-weight:bold;margin-top:4px;">{phase_label}</div>
        <div style="color:#64748b;font-size:12px;margin-top:4px;">{latest[0]}</div>
    </div>""", unsafe_allow_html=True)

score = latest[2]
score_color = "#ef4444" if score >= 60 else "#fb923c" if score >= 40 else "#facc15" if score >= 20 else "#60a5fa"
with cols[1]:
    st.markdown(f"""
    <div style="background:#1e293b;border-radius:12px;padding:16px;text-align:center;">
        <div style="color:#94a3b8;font-size:12px;">情绪评分</div>
        <div style="color:{score_color};font-size:24px;font-weight:bold;margin-top:4px;">{score:.0f}</div>
        <div style="color:#64748b;font-size:12px;margin-top:4px;">满分 100</div>
    </div>""", unsafe_allow_html=True)

with cols[2]:
    st.markdown(f"""
    <div style="background:#1e293b;border-radius:12px;padding:16px;text-align:center;">
        <div style="color:#94a3b8;font-size:12px;">涨停 / 炸板</div>
        <div style="font-size:24px;font-weight:bold;margin-top:4px;">
            <span style="color:#ef4444;">{latest[3]}</span>
            <span style="color:#475569;"> / </span>
            <span style="color:#eab308;">{latest[4]}</span>
        </div>
        <div style="color:#64748b;font-size:12px;margin-top:4px;">炸板率 {latest[5]:.1f}%</div>
    </div>""", unsafe_allow_html=True)

with cols[3]:
    st.markdown(f"""
    <div style="background:#1e293b;border-radius:12px;padding:16px;text-align:center;">
        <div style="color:#94a3b8;font-size:12px;">最高连板</div>
        <div style="font-size:24px;font-weight:bold;margin-top:4px;">{latest[6]}</div>
        <div style="color:#64748b;font-size:12px;margin-top:4px;">晋级率 {latest[8]:.1f}%</div>
    </div>""", unsafe_allow_html=True)

with cols[4]:
    st.markdown(f"""
    <div style="background:#1e293b;border-radius:12px;padding:16px;text-align:center;">
        <div style="color:#94a3b8;font-size:12px;">首板数</div>
        <div style="font-size:24px;font-weight:bold;margin-top:4px;">{latest[7]}</div>
        <div style="color:#64748b;font-size:12px;margin-top:4px;">涨停总额 {latest[9] / 1e8:.1f}亿</div>
    </div>""", unsafe_allow_html=True)

st.markdown("")

# 情绪评分走势图
dates = [d[0] for d in reversed(data)]
scores = [d[2] for d in reversed(data)]
zt_counts = [d[3] for d in reversed(data)]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=dates, y=scores, name="情绪评分",
    line=dict(color="#facc15", width=2),
    fill="tozeroy", fillcolor="rgba(250,204,21,0.08)",
))
fig.add_trace(go.Bar(
    x=dates, y=zt_counts, name="涨停数",
    marker_color="rgba(239,68,68,0.4)", yaxis="y2",
))
fig.update_layout(
    title="情绪评分 & 涨停数走势",
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    height=350,
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(orientation="h", y=1.1),
    yaxis=dict(title="评分", range=[0, 100]),
    yaxis2=dict(title="涨停数", overlaying="y", side="right"),
)
st.plotly_chart(fig, use_container_width=True)

# 情绪历史表格
st.markdown("### 📊 情绪走势明细")
rows = []
for d in data:
    pl, pc = PHASE_CFG.get(d[1], ("?", "#94a3b8"))
    rows.append({
        "日期": d[0], "阶段": pl, "评分": f"{d[2]:.0f}",
        "涨停": d[3], "炸板": d[4], "炸板率": f"{d[5]:.1f}%",
        "连板": d[6], "首板": d[7], "晋级率": f"{d[8]:.1f}%",
    })
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=500)
