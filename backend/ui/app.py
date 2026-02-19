"""
观潮看板 (Tide-Watcher Dashboard)

Streamlit 暗色主题实时看板，集成择时引擎、盘面守卫和财务排雷。

启动方式：
    cd backend
    ./venv/Scripts/streamlit run ui/app.py
"""

import sys
from pathlib import Path

# 确保能导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import datetime
import asyncio
import streamlit as st
import plotly.graph_objects as go

from app.engine.calendar import (
    is_trading_day,
    futures_settlement_day,
    options_settlement_day,
)
from app.engine.timing import evaluate, Light, Action
from app.engine.finance_risk import get_risk_by_code, get_risk_list
from app.data.source_zhitu import ZhituSource, normalize_code, to_pure_code


# ==================== 工具函数 ====================

def run_async(coro):
    """在 Streamlit 同步环境中运行异步函数。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def get_source():
    if "source" not in st.session_state:
        st.session_state.source = ZhituSource()
    return st.session_state.source


# ==================== 页面配置 ====================

st.set_page_config(
    page_title="观潮看板 | Tide-Watcher",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================== Section 1: 交易红绿灯 (HUD) ====================

today = datetime.date.today()
signal = evaluate(today)

light_config = {
    Light.RED: {"emoji": "🔴", "bg": "rgba(239,68,68,0.08)", "border": "#ef4444", "label": "红灯"},
    Light.YELLOW: {"emoji": "🟡", "bg": "rgba(234,179,8,0.08)", "border": "#eab308", "label": "黄灯"},
    Light.GREEN: {"emoji": "🟢", "bg": "rgba(34,197,94,0.08)", "border": "#22c55e", "label": "绿灯"},
}
cfg = light_config[signal.light]

st.markdown(f"""
<div style="
    background: {cfg['bg']};
    border: 2px solid {cfg['border']};
    border-radius: 16px;
    padding: 32px;
    text-align: center;
    margin-bottom: 24px;
">
    <div style="font-size: 64px; margin-bottom: 8px;">{cfg['emoji']}</div>
    <div style="font-size: 28px; font-weight: bold; color: {cfg['border']};">
        {cfg['label']}：{signal.action.value}
    </div>
    <div style="font-size: 16px; color: #94a3b8; margin-top: 8px;">
        {signal.reason}
    </div>
    <div style="font-size: 13px; color: #64748b; margin-top: 12px;">
        📅 {today.strftime('%Y-%m-%d')} {'（交易日）' if is_trading_day(today) else '（非交易日）'}
        &nbsp;|&nbsp; 优先级 L{signal.level}
    </div>
</div>
""", unsafe_allow_html=True)

if signal.details:
    with st.expander("📋 详细说明", expanded=False):
        for d in signal.details:
            st.markdown(f"- {d}")

# ==================== Section 1.5: 情绪阶段 + 策略统计（吸收自 Next.js） ====================

PHASE_LABELS = {
    "ice": ("❄️ 冰点期", "#60a5fa"),
    "retreat": ("📉 退潮期", "#4ade80"),
    "ferment": ("⚡ 发酵期", "#facc15"),
    "boom": ("🔥 爆发期", "#fb923c"),
    "frenzy": ("🌋 狂热期", "#ef4444"),
}

try:
    from app.store.database import async_session
    from sqlalchemy import text as sql_text

    # 情绪快照
    async def _load_emotion():
        async with async_session() as session:
            r = await session.execute(sql_text(
                "SELECT trade_date, phase, phase_score, limit_up_count, broken_board_count, broken_rate, max_streak "
                "FROM emotion_snapshot ORDER BY trade_date DESC LIMIT 1"
            ))
            return r.first()

    # 策略数
    async def _load_strategy_count():
        from app.engine.registry import get_all_strategies
        return len(get_all_strategies())

    emotion = run_async(_load_emotion())
    strategy_count = run_async(_load_strategy_count())

    info_cols = st.columns(4)
    if emotion:
        phase_label, phase_color = PHASE_LABELS.get(emotion[1], ("❓ 未知", "#94a3b8"))
        with info_cols[0]:
            st.markdown(f"""
            <div style="background:#1e293b;border-radius:12px;padding:16px;text-align:center;">
                <div style="color:#94a3b8;font-size:12px;">市场情绪</div>
                <div style="color:{phase_color};font-size:22px;font-weight:bold;margin-top:4px;">{phase_label}</div>
                <div style="color:#64748b;font-size:12px;margin-top:4px;">评分 {emotion[2]:.0f}/100 | {emotion[0]}</div>
            </div>""", unsafe_allow_html=True)
        with info_cols[1]:
            st.markdown(f"""
            <div style="background:#1e293b;border-radius:12px;padding:16px;text-align:center;">
                <div style="color:#94a3b8;font-size:12px;">涨停 / 炸板</div>
                <div style="font-size:22px;font-weight:bold;margin-top:4px;">
                    <span style="color:#ef4444;">{emotion[3]}</span>
                    <span style="color:#475569;"> / </span>
                    <span style="color:#eab308;">{emotion[4]}</span>
                </div>
                <div style="color:#64748b;font-size:12px;margin-top:4px;">炸板率 {emotion[5]:.1f}% | 连板 {emotion[6]}</div>
            </div>""", unsafe_allow_html=True)
    else:
        with info_cols[0]:
            st.markdown('<div style="background:#1e293b;border-radius:12px;padding:16px;text-align:center;color:#64748b;">情绪数据暂无</div>', unsafe_allow_html=True)
        with info_cols[1]:
            st.markdown('<div style="background:#1e293b;border-radius:12px;padding:16px;text-align:center;color:#64748b;">涨停数据暂无</div>', unsafe_allow_html=True)

    with info_cols[2]:
        st.markdown(f"""
        <div style="background:#1e293b;border-radius:12px;padding:16px;text-align:center;">
            <div style="color:#94a3b8;font-size:12px;">已注册策略</div>
            <div style="font-size:22px;font-weight:bold;margin-top:4px;">{strategy_count}</div>
            <div style="color:#64748b;font-size:12px;margin-top:4px;">详见「策略中心」页</div>
        </div>""", unsafe_allow_html=True)

    # 风险股统计
    async def _risk_stats():
        async with async_session() as session:
            total = (await session.execute(sql_text("SELECT COUNT(*) FROM financial_risk"))).scalar() or 0
            extreme = (await session.execute(sql_text("SELECT COUNT(*) FROM financial_risk WHERE is_extreme_risk = 1"))).scalar() or 0
        return total, extreme

    risk_total, risk_extreme = run_async(_risk_stats())
    with info_cols[3]:
        st.markdown(f"""
        <div style="background:#1e293b;border-radius:12px;padding:16px;text-align:center;">
            <div style="color:#94a3b8;font-size:12px;">财务雷区</div>
            <div style="font-size:22px;font-weight:bold;margin-top:4px;">
                <span style="color:#ef4444;">{risk_extreme}</span>
                <span style="color:#475569;font-size:14px;"> / {risk_total}</span>
            </div>
            <div style="color:#64748b;font-size:12px;margin-top:4px;">极端风险 / 总标记</div>
        </div>""", unsafe_allow_html=True)

except Exception as e:
    st.warning(f"统计信息加载失败: {e}")

st.markdown("")  # 间距

# ==================== Section 2: 市场实时脉搏 + 涨停TOP10 ====================

st.markdown("## 📊 市场实时脉搏")

if is_trading_day(today):
    try:
        source = get_source()
        quotes = run_async(source.get_realtime_all())

        up_count = 0
        down_count = 0
        flat_count = 0
        limit_up = 0
        limit_down = 0

        for q in quotes:
            pct = q.get("pc", 0) or 0
            if pct > 0:
                up_count += 1
            elif pct < 0:
                down_count += 1
            else:
                flat_count += 1
            if pct >= 9.8:
                limit_up += 1
            elif pct <= -9.8:
                limit_down += 1

        col1, col2 = st.columns(2)

        with col1:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=["上涨", "平盘", "下跌"],
                y=[up_count, flat_count, down_count],
                marker_color=["#ef4444", "#64748b", "#22c55e"],
                text=[up_count, flat_count, down_count],
                textposition="auto",
            ))
            fig.update_layout(
                title="涨跌家数",
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=300,
                margin=dict(l=20, r=20, t=40, b=20),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("涨停", f"{limit_up}", delta=None)
            m2.metric("跌停", f"{limit_down}", delta=None)
            m3.metric("涨跌比", f"{up_count}:{down_count}")
            m4.metric("总家数", f"{len(quotes)}")

    except Exception as e:
        st.warning(f"市场数据获取失败: {e}")

    # 涨停TOP10（吸收自 Next.js dashboard）
    try:
        zt_data = run_async(source.get_pool("ztgc", today.strftime("%Y-%m-%d")))
        if zt_data and len(zt_data) > 0:
            st.markdown("### 🏆 涨停 TOP10")
            import pandas as pd
            top10 = zt_data[:10]
            rows = []
            for s in top10:
                lbc = s.get("lbc", 0) or 0
                rows.append({
                    "代码": s.get("dm", ""),
                    "名称": s.get("mc", ""),
                    "连板": f"{'🔥' * min(lbc, 5)} {lbc}板" if lbc >= 2 else f"{lbc}板",
                    "封板时间": s.get("fbt", "-"),
                    "炸板": s.get("zbc", 0),
                    "成交额": f"{(s.get('cje', 0) or 0) / 1e8:.2f}亿" if s.get('cje') else "-",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except Exception:
        pass

else:
    st.info("🌙 今日非交易日，市场数据暂不可用")

# ==================== Section 3: 智能排雷搜索 ====================

st.markdown("## 🔍 智能排雷搜索")

search_code = st.text_input("输入股票代码", placeholder="如 000001 或 600519")

if search_code:
    code = search_code.strip()
    timing_sig = signal  # 当前择时信号

    # 财务风险查询
    risk = run_async(get_risk_by_code(code))

    # 实时行情
    try:
        source = get_source()
        quote = run_async(source.get_realtime_quote(code))
        name = quote.get("mc", code)
        price = quote.get("p", 0)
        pct = quote.get("pc", 0)
        pct_str = f"+{pct:.2f}%" if pct >= 0 else f"{pct:.2f}%"
        pct_color = "#ef4444" if pct >= 0 else "#22c55e"
    except Exception:
        name = code
        price = 0
        pct_str = "--"
        pct_color = "#64748b"

    # 行情卡片
    st.markdown(f"""
    <div style="
        background: #1e293b;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    ">
        <div style="font-size: 20px; font-weight: bold;">{name}
            <span style="color: #64748b; font-size: 14px; margin-left: 8px;">{code}</span>
        </div>
        <div style="font-size: 32px; font-weight: bold; color: {pct_color}; margin-top: 8px;">
            {price:.2f}
            <span style="font-size: 18px;">{pct_str}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 财务雷达
    if risk and risk.is_extreme_risk:
        st.markdown(f"""
        <div style="
            background: rgba(239,68,68,0.15);
            border: 2px solid #ef4444;
            border-radius: 12px;
            padding: 20px;
            animation: pulse 1.5s infinite;
        ">
            <div style="font-size: 22px; font-weight: bold; color: #ef4444;">
                ⚠️ 极高退市/ST风险
            </div>
            <div style="color: #fca5a5; margin-top: 8px;">{risk.reason}</div>
            <div style="color: #64748b; font-size: 12px; margin-top: 8px;">
                连续亏损 {risk.loss_years} 年 | 扫描日期: {risk.scan_date}
            </div>
        </div>
        <style>
            @keyframes pulse {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.7; }}
            }}
        </style>
        """, unsafe_allow_html=True)
    elif risk:
        st.markdown(f"""
        <div style="
            background: rgba(234,179,8,0.1);
            border: 1px solid #eab308;
            border-radius: 12px;
            padding: 16px;
        ">
            <div style="font-size: 18px; font-weight: bold; color: #eab308;">
                ⚠️ 财务风险提示
            </div>
            <div style="color: #fde68a; margin-top: 8px;">{risk.reason}</div>
        </div>
        """, unsafe_allow_html=True)

    # 综合操作建议
    st.markdown("#### 💡 综合操作建议")
    has_risk = risk is not None
    is_extreme = risk.is_extreme_risk if risk else False

    if timing_sig.action == Action.FORCE_EMPTY:
        advice = "🚫 **禁买**：当前处于绝对禁区（财报暴雷季），严禁任何建仓操作"
        advice_color = "#ef4444"
    elif timing_sig.action == Action.CLEAR_EXIT:
        advice = "🚨 **清仓离场**：风险预警期，仅允许离场操作"
        advice_color = "#eab308"
    elif timing_sig.action == Action.REST:
        advice = "😴 **休息**：12月资金面枯竭期，建议空仓"
        advice_color = "#eab308"
    elif is_extreme:
        advice = "🚫 **禁买**：环境不稳且个股有雷（极端退市风险）"
        advice_color = "#ef4444"
    elif has_risk and timing_sig.action == Action.PROBE_ENTRY:
        advice = "⚠️ **谨慎**：择时允许试探，但该股有财务风险，不建议参与"
        advice_color = "#eab308"
    elif has_risk:
        advice = "⚠️ **回避**：该股存在财务风险，建议回避"
        advice_color = "#eab308"
    elif timing_sig.action == Action.PROBE_ENTRY:
        advice = "✅ **可试探**：择时绿灯 + 财务安全，可收盘前轻仓试探"
        advice_color = "#22c55e"
    elif timing_sig.action == Action.NORMAL:
        advice = "✅ **正常交易**：择时正常 + 财务安全"
        advice_color = "#22c55e"
    else:
        advice = f"ℹ️ {timing_sig.action.value}"
        advice_color = "#94a3b8"

    st.markdown(f'<div style="color: {advice_color}; font-size: 16px; padding: 12px 0;">{advice}</div>', unsafe_allow_html=True)

# ==================== Section 4: 风险日历预览 ====================

st.markdown("## 📅 风险日历预览")

upcoming = []
d = today
months_checked = 0
last_month = None

while len(upcoming) < 6 and months_checked < 6:
    m = d.month
    y = d.year
    if (y, m) != last_month:
        last_month = (y, m)
        months_checked += 1
        try:
            fd = futures_settlement_day(y, m)
            if fd >= today:
                days_left = (fd - today).days
                upcoming.append(("期货交割", fd, days_left))
        except Exception:
            pass
        try:
            od = options_settlement_day(y, m)
            if od >= today:
                days_left = (od - today).days
                upcoming.append(("期权结算", od, days_left))
        except Exception:
            pass
    d = d.replace(day=1) + datetime.timedelta(days=32)
    d = d.replace(day=1)

upcoming.sort(key=lambda x: x[1])
upcoming = upcoming[:6]

cols = st.columns(min(len(upcoming), 3))
for i, (label, date, days) in enumerate(upcoming[:3]):
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    wd = weekday_names[date.weekday()]

    if days == 0:
        countdown = "🔥 今天"
        border_color = "#ef4444"
    elif days <= 3:
        countdown = f"⚡ {days} 天后"
        border_color = "#eab308"
    else:
        countdown = f"📆 {days} 天后"
        border_color = "#334155"

    with cols[i]:
        st.markdown(f"""
        <div style="
            background: #1e293b;
            border: 1px solid {border_color};
            border-radius: 12px;
            padding: 16px;
            text-align: center;
        ">
            <div style="font-size: 14px; color: #94a3b8;">{label}</div>
            <div style="font-size: 20px; font-weight: bold; margin-top: 4px;">
                {date.strftime('%m-%d')} {wd}
            </div>
            <div style="font-size: 14px; margin-top: 4px; color: {border_color};">
                {countdown}
            </div>
        </div>
        """, unsafe_allow_html=True)

# 底部信息
st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #475569; font-size: 12px;">'
    '🌊 Tide-Watcher 观潮系统 v0.2 | 数据源: ZhituAPI | 仅供辅助决策参考'
    '</div>',
    unsafe_allow_html=True,
)
