"""个股查询 — 实时行情 + 财务排雷 + 综合操作建议。"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import datetime
import asyncio
import streamlit as st

from app.data.source_zhitu import ZhituSource, to_pure_code
from app.engine.timing import evaluate, Action
from app.engine.finance_risk import get_risk_by_code

st.set_page_config(page_title="个股查询 | Tide-Watcher", page_icon="🔍", layout="wide")


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


st.markdown("# 🔍 个股查询")

code = st.text_input("输入股票代码", placeholder="如 000001 或 600519")

if code:
    code = code.strip()
    source = get_source()
    today = datetime.date.today()
    timing_sig = evaluate(today)

    # 并发获取数据
    async def _fetch_all():
        quote = await source.get_realtime_quote(code)
        risk = await get_risk_by_code(code)
        company = None
        try:
            company = await source.get_company_info(to_pure_code(code), "gsjj")
        except Exception:
            pass
        kline = []
        try:
            kline = await source.get_latest_kline(code, "d", "n", 20)
        except Exception:
            pass
        return quote, risk, company, kline

    try:
        quote, risk, company, kline = run_async(_fetch_all())
    except Exception as e:
        st.error(f"查询失败: {e}")
        st.stop()

    name = quote.get("mc", code)
    price = quote.get("p", 0)
    pct = quote.get("pc", 0) or 0
    pct_color = "#ef4444" if pct >= 0 else "#22c55e"

    # 行情卡片
    st.markdown(f"""
    <div style="background:#1e293b;border-radius:12px;padding:24px;margin-bottom:16px;">
        <div style="font-size:24px;font-weight:bold;">{name}
            <span style="color:#64748b;font-size:14px;margin-left:8px;">{code}</span>
        </div>
        <div style="font-size:36px;font-weight:bold;color:{pct_color};margin-top:8px;">
            {price:.2f}
            <span style="font-size:20px;">{'+' if pct >= 0 else ''}{pct:.2f}%</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 财务风险警告
    if risk and risk.is_extreme_risk:
        st.markdown(f"""
        <div style="background:rgba(239,68,68,0.15);border:2px solid #ef4444;border-radius:12px;padding:20px;animation:pulse 1.5s infinite;">
            <div style="font-size:22px;font-weight:bold;color:#ef4444;">⚠️ 极高退市/ST风险</div>
            <div style="color:#fca5a5;margin-top:8px;">{risk.reason}</div>
            <div style="color:#64748b;font-size:12px;margin-top:8px;">连续亏损 {risk.loss_years} 年 | 扫描日期: {risk.scan_date}</div>
        </div>
        <style>@keyframes pulse {{0%,100%{{opacity:1;}}50%{{opacity:0.7;}}}}</style>
        """, unsafe_allow_html=True)
    elif risk:
        st.warning(f"⚠️ 财务风险提示：{risk.reason}")

    # 综合建议
    has_risk = risk is not None
    is_extreme = risk.is_extreme_risk if risk else False

    if timing_sig.action == Action.FORCE_EMPTY:
        st.error("🚫 **禁买**：当前处于绝对禁区（财报暴雷季）")
    elif timing_sig.action == Action.CLEAR_EXIT:
        st.warning("🚨 **清仓离场**：风险预警期")
    elif is_extreme:
        st.error("🚫 **禁买**：环境不稳且个股有雷（极端退市风险）")
    elif has_risk:
        st.warning("⚠️ **回避**：该股存在财务风险")
    elif timing_sig.action == Action.PROBE_ENTRY:
        st.success("✅ **可试探**：择时绿灯 + 财务安全")
    else:
        st.success("✅ **正常交易**：择时正常 + 财务安全")

    # 行情详情
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 📊 行情数据")
        metrics = {
            "开盘": quote.get("o"), "最高": quote.get("h"),
            "最低": quote.get("l"), "昨收": quote.get("yc"),
            "成交额": f"{(quote.get('cje', 0) or 0) / 1e8:.2f}亿",
            "换手率": f"{quote.get('hs', 0) or 0:.2f}%",
            "市盈率": quote.get("pe"), "市净率": quote.get("sjl"),
            "总市值": f"{(quote.get('sz', 0) or 0) / 1e8:.2f}亿",
        }
        for k, v in metrics.items():
            st.markdown(f"**{k}**：{v}")

    with col2:
        if company:
            st.markdown("#### 🏢 公司信息")
            info = company if isinstance(company, dict) else {}
            st.markdown(f"**公司名称**：{info.get('gsmc', '-')}")
            st.markdown(f"**上市日期**：{info.get('ssrq', '-')}")
            st.markdown(f"**行业**：{info.get('hy', '-')}")
            gnbk = info.get("gnbk", [])
            if gnbk and isinstance(gnbk, list):
                tags = " ".join([f"`{t}`" for t in gnbk[:10]])
                st.markdown(f"**概念**：{tags}")

    # K线数据
    if kline:
        st.markdown("#### 📈 近20日K线")
        import pandas as pd
        rows = []
        for bar in reversed(kline):
            raw = bar if isinstance(bar, dict) else {}
            d = str(raw.get("d", raw.get("t", "")))[:10]
            o = float(raw.get("o", 0))
            h = float(raw.get("h", 0))
            l_val = float(raw.get("l", 0))
            c = float(raw.get("c", 0))
            v = float(raw.get("v", 0))
            a = float(raw.get("a", 0))
            zf = float(raw.get("zf", 0) or raw.get("change_pct", 0) or 0)
            rows.append({
                "日期": d, "开盘": f"{o:.2f}", "最高": f"{h:.2f}",
                "最低": f"{l_val:.2f}", "收盘": f"{c:.2f}",
                "涨跌%": f"{zf:+.2f}",
                "成交量": f"{v / 1e4:.0f}万手",
                "成交额": f"{a / 1e8:.2f}亿" if a >= 1e8 else f"{a / 1e4:.0f}万",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
