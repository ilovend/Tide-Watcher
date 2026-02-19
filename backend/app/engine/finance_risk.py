"""
财务排雷模块 — 自动扫描全市场财务风险股票。

排雷规则：
  Rule-1: 净利润连续为负且累计亏损 > 3亿 → consecutive_loss
  Rule-2: 最近一个会计年度营收 < 1亿 → low_revenue

数据源：
  ZhituAPI /hs/gs/cwzb/{code} — 财务指标（含净利润、营收等关键数据）

缓存策略：
  扫描结果写入 SQLite financial_risk 表，季度更新。
  查询时直接读库，不调用 API。
"""

import asyncio
import datetime
import logging
from typing import Any

from sqlalchemy import select, delete

from app.data.source_zhitu import ZhituSource, normalize_code, to_pure_code
from app.store.database import async_session
from app.store.models import FinancialRisk, Stock

logger = logging.getLogger(__name__)

# ==================== 常量 ====================

LOSS_THRESHOLD = 3e8           # 累计亏损阈值：3亿元
REVENUE_THRESHOLD_MAIN = 3e8   # 主板营收阈值：3亿元（需同时亏损）
REVENUE_THRESHOLD_SMALL = 1e8  # 创业板/北交所营收阈值：1亿元
SCAN_YEARS = 3                 # 检查最近几年
MAX_CONCURRENT = 10            # 最大并发请求数（防止瞬时突发）
BATCH_DELAY = 0.5              # 批次间延时（秒）


# ==================== 财务数据解析 ====================

# ZhituAPI cwzb 接口可能使用的字段名映射（适配不同返回格式）
_NET_PROFIT_KEYS = ["kflr", "jlr", "netProfit", "net_profit", "parentNetProfit", "gsjlr"]
_REVENUE_KEYS = ["zyyw", "yysr", "totalRevenue", "total_revenue", "yyzsr", "revenue"]
_DATE_KEYS = ["date", "jzrq", "reportDate", "rq", "report_date"]


def _extract_field(row: dict, candidates: list[str]) -> float | None:
    """从字典中尝试多个候选键名提取数值。

    注意：ZhituAPI 用 "--" 表示无数据，应视为 None。
    """
    for key in candidates:
        val = row.get(key)
        if val is None or val == "--" or val == "":
            continue
        try:
            return float(val)
        except (ValueError, TypeError):
            continue
    return None


def _extract_date(row: dict) -> str:
    """提取报告期日期。"""
    for key in _DATE_KEYS:
        val = row.get(key)
        if val:
            return str(val)[:10]
    return ""


def _is_annual_report(date_str: str) -> bool:
    """判断是否为年报（报告期以 12-31 结尾）。"""
    return date_str.endswith("12-31") or date_str.endswith("1231")


def _get_revenue_threshold(code: str) -> tuple[float, str]:
    """根据股票代码判断板块，返回对应营收阈值。

    主板(60x/000x/001x): 3亿（需同时亏损）
    创业板(300x/301x): 1亿
    科创板(688x): 1亿
    北交所(4xx/8xx): 1亿
    """
    pure = code.split(".")[0] if "." in code else code
    if pure.startswith(("300", "301")):
        return REVENUE_THRESHOLD_SMALL, "创业板"
    if pure.startswith("688"):
        return REVENUE_THRESHOLD_SMALL, "科创板"
    if pure.startswith(("4", "8")):
        return REVENUE_THRESHOLD_SMALL, "北交所"
    return REVENUE_THRESHOLD_MAIN, "主板"


def analyze_financials(data: list[dict], code: str = "") -> dict[str, Any]:
    """分析财务数据，返回风险评估结果。

    Args:
        data: cwzb 接口返回的财务指标列表
        code: 股票代码，用于判断板块确定营收阈值

    Returns:
        {
            "risks": ["consecutive_loss", "low_revenue"] 或 [],
            "loss_years": int,
            "cumulative_loss": float,
            "latest_revenue": float,
            "latest_net_profit": float,
            "reason": str,
        }
    """
    if not data:
        return {"risks": [], "loss_years": 0, "cumulative_loss": 0,
                "latest_revenue": 0, "latest_net_profit": 0, "reason": ""}

    # 按报告期倒序排列
    rows = sorted(data, key=lambda r: _extract_date(r), reverse=True)

    # 提取年报数据
    annual_reports = []
    for row in rows:
        date_str = _extract_date(row)
        if _is_annual_report(date_str):
            np_val = _extract_field(row, _NET_PROFIT_KEYS)
            rev_val = _extract_field(row, _REVENUE_KEYS)
            annual_reports.append({
                "date": date_str,
                "net_profit": np_val,
                "revenue": rev_val,
            })

    risks = []
    reasons = []
    loss_years = 0
    cumulative_loss = 0.0
    latest_revenue = 0.0
    latest_net_profit = 0.0

    # Rule-1: 净利润连续为负且累计亏损 > 3亿
    if annual_reports:
        latest_net_profit = annual_reports[0].get("net_profit") or 0
        for ar in annual_reports[:SCAN_YEARS]:
            np = ar.get("net_profit")
            if np is not None and np < 0:
                loss_years += 1
                cumulative_loss += abs(np)
            else:
                break

        if loss_years >= 2 and cumulative_loss > LOSS_THRESHOLD:
            risks.append("consecutive_loss")
            reasons.append(
                f"净利润连续 {loss_years} 年为负，"
                f"累计亏损 {cumulative_loss / 1e8:.2f} 亿元（阈值 3 亿）"
            )

    # Rule-2: 低营收检查（浮动阈值）
    # 主板：营收<3亿 且 亏损（组合指标）
    # 创业板/北交所：营收<1亿
    rev_threshold, board_name = _get_revenue_threshold(code)
    if annual_reports:
        latest_revenue = annual_reports[0].get("revenue")
        if latest_revenue is not None:
            is_loss = (latest_net_profit is not None and latest_net_profit < 0)
            # 主板需同时满足亏损+低营收；其他板块只看营收
            if rev_threshold == REVENUE_THRESHOLD_MAIN:
                if 0 < latest_revenue < rev_threshold and is_loss:
                    risks.append("low_revenue")
                    reasons.append(
                        f"{board_name}营收 {latest_revenue / 1e8:.2f} 亿 + 亏损（阈值 {rev_threshold / 1e8:.0f} 亿）"
                    )
            else:
                if 0 < latest_revenue < rev_threshold:
                    risks.append("low_revenue")
                    reasons.append(
                        f"{board_name}营收 {latest_revenue / 1e8:.4f} 亿元（阈值 {rev_threshold / 1e8:.0f} 亿）"
                    )
            if latest_revenue == 0:
                risks.append("low_revenue")
                reasons.append("最近年度营收为 0")

    risk_type = "both" if len(risks) == 2 else (risks[0] if risks else "")

    return {
        "risks": risks,
        "risk_type": risk_type,
        "loss_years": loss_years,
        "cumulative_loss": cumulative_loss,
        "latest_revenue": latest_revenue,
        "latest_net_profit": latest_net_profit,
        "reason": "；".join(reasons),
    }


# ==================== 全市场扫描 ====================

async def scan_all_stocks(source: ZhituSource, batch_size: int = 30) -> dict[str, Any]:
    """全市场财务排雷扫描。

    流程：
      1. 从数据库获取所有活跃股票
      2. 通过信号量控制并发，逐批调用 cwzb 接口
      3. 应用排雷规则
      4. 结果写入 financial_risk 表

    频率安全：
      - ZhituSource 内置 RateLimiter（3000次/分）
      - 本模块额外限制最大并发 10 + 批次间 0.5s 延时
      - 实际吞吐约 40~45 次/秒，远低于 50 次/秒上限

    Args:
        batch_size: 每批处理股票数（控制 API 压力）

    Returns:
        扫描统计信息
    """
    scan_date = datetime.date.today().strftime("%Y-%m-%d")
    logger.info("开始财务排雷扫描 — %s", scan_date)

    # 获取所有股票（直接SQL，兼容旧表结构）
    from sqlalchemy import text
    async with async_session() as session:
        result = await session.execute(text("SELECT code, name FROM stocks"))
        stocks = result.all()

    total = len(stocks)
    logger.info("待扫描股票: %d 只", total)

    # 并发信号量：限制同时在飞的请求数
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def _guarded_scan(code: str, name: str):
        async with semaphore:
            return await _scan_one(source, code, name)

    flagged: list[FinancialRisk] = []
    errors = 0
    scanned = 0

    # 分批扫描，每批之间有延时
    for i in range(0, total, batch_size):
        batch = stocks[i:i + batch_size]
        tasks = [_guarded_scan(code, name) for code, name in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (code, name), res in zip(batch, results):
            scanned += 1
            if isinstance(res, Exception):
                errors += 1
                if errors <= 10:
                    logger.warning("扫描 %s 失败: %s", code, res)
                continue

            if res and res["risks"]:
                flagged.append(FinancialRisk(
                    code=code,
                    name=name,
                    risk_type=res["risk_type"],
                    risk_level="high",
                    reason=res["reason"],
                    cumulative_loss=res["cumulative_loss"],
                    latest_revenue=res["latest_revenue"],
                    latest_net_profit=res["latest_net_profit"],
                    loss_years=res["loss_years"],
                    scan_date=scan_date,
                ))

        if scanned % 500 == 0:
            logger.info("扫描进度: %d/%d (风险: %d, 错误: %d)", scanned, total, len(flagged), errors)

        # 批次间延时，避免突发
        await asyncio.sleep(BATCH_DELAY)

    # 写入数据库（先清除旧数据，再写入新数据）
    async with async_session() as session:
        await session.execute(delete(FinancialRisk))
        session.add_all(flagged)
        await session.commit()

    stats = {
        "scan_date": scan_date,
        "total_stocks": total,
        "scanned": scanned,
        "flagged": len(flagged),
        "errors": errors,
    }
    logger.info("财务排雷完成: %s", stats)
    return stats


async def _scan_one(source: ZhituSource, code: str, name: str) -> dict[str, Any] | None:
    """扫描单只股票的财务风险。"""
    pure = to_pure_code(code)
    try:
        data = await source.get_company_info(pure, "cwzb")
        if not data:
            return None
        # cwzb 可能返回 dict 或 list
        if isinstance(data, dict):
            data = data.get("data", []) if "data" in data else [data]
        if not isinstance(data, list):
            return None
        return analyze_financials(data, code=code)
    except Exception as e:
        raise RuntimeError(f"{code}({name}): {e}") from e


# ==================== 查询接口 ====================

async def get_risk_by_code(code: str) -> FinancialRisk | None:
    """查询单只股票的财务风险标记（从缓存数据库读取）。"""
    code = normalize_code(code)
    async with async_session() as session:
        # 精确匹配优先，兼容数据库中 000004.SZ.BJ 格式的历史数据
        result = await session.execute(
            select(FinancialRisk).where(
                FinancialRisk.code.startswith(code)
            ).limit(1)
        )
        return result.scalar_one_or_none()


async def get_risk_list() -> list[FinancialRisk]:
    """获取全部财务风险股票名单。"""
    async with async_session() as session:
        result = await session.execute(
            select(FinancialRisk).order_by(FinancialRisk.risk_type, FinancialRisk.code)
        )
        return list(result.scalars().all())


async def check_risks_batch(codes: list[str]) -> dict[str, dict]:
    """批量查询多只股票的风险标记。

    Returns:
        { "000001.SZ": {"risk_type": "...", "reason": "..."}, ... }
        只返回有风险的股票。
    """
    normalized = [normalize_code(c) for c in codes]
    async with async_session() as session:
        result = await session.execute(
            select(FinancialRisk).where(FinancialRisk.code.in_(normalized))
        )
        risks = result.scalars().all()
    return {
        r.code: {
            "risk_type": r.risk_type,
            "risk_level": r.risk_level,
            "reason": r.reason,
            "loss_years": r.loss_years,
            "cumulative_loss": r.cumulative_loss,
            "latest_revenue": r.latest_revenue,
        }
        for r in risks
    }


# ==================== 深度扫描（income 接口） ====================

def _analyze_income_for_loss(data: list[dict]) -> dict[str, Any]:
    """分析利润表数据，判断是否连续3年亏损。

    Args:
        data: /hs/fin/income 接口返回的利润表列表

    Returns:
        {"consecutive_loss_years": int, "cumulative_loss": float, "is_extreme": bool}
    """
    # 提取年报数据（截止日期以 12-31 结尾）
    annual = []
    for row in data:
        d = _extract_date(row)
        if _is_annual_report(d):
            jlr = _extract_field(row, ["jlr", "kflr"] + _NET_PROFIT_KEYS)
            if jlr is not None:
                annual.append({"date": d, "net_profit": jlr})

    # 按日期倒序
    annual.sort(key=lambda x: x["date"], reverse=True)

    # 连续亏损计数
    loss_years = 0
    cumulative = 0.0
    for ar in annual[:SCAN_YEARS]:
        if ar["net_profit"] < 0:
            loss_years += 1
            cumulative += abs(ar["net_profit"])
        else:
            break

    return {
        "consecutive_loss_years": loss_years,
        "cumulative_loss": cumulative,
        "is_extreme": loss_years >= 3,
    }


async def deep_scan_flagged(source: ZhituSource) -> dict[str, Any]:
    """对已标记风险股进行深度扫描（利润表3年数据）。

    仅扫描 financial_risk 表中已有记录的股票，
    通过 /hs/fin/income 接口获取完整利润表，
    检查连续3年净利润为负 → 标记 is_extreme_risk。

    频率安全：同 scan_all_stocks（信号量+批次延时）
    """
    logger.info("开始深度扫描（income 利润表）")

    async with async_session() as session:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT id, code, name FROM financial_risk")
        )
        flagged = result.all()

    total = len(flagged)
    logger.info("待深度扫描: %d 只", total)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    updated = 0
    extreme_count = 0
    errors = 0

    async def _deep_one(code: str) -> dict[str, Any] | None:
        async with semaphore:
            try:
                income_data = await source.get_finance_report(code, "income")
                if not income_data or not isinstance(income_data, list):
                    return None
                return _analyze_income_for_loss(income_data)
            except Exception as e:
                raise RuntimeError(f"deep_scan {code}: {e}") from e

    for i in range(0, total, 30):
        batch = flagged[i:i + 30]
        tasks = [_deep_one(row[1]) for row in batch]  # row[1] = code
        results = await asyncio.gather(*tasks, return_exceptions=True)

        async with async_session() as session:
            from sqlalchemy import text as sql_text
            for (rid, code, name), res in zip(batch, results):
                if isinstance(res, Exception):
                    errors += 1
                    if errors <= 5:
                        logger.warning("深度扫描 %s 失败: %s", code, res)
                    continue

                if res is None:
                    continue

                updated += 1
                is_ext = res["is_extreme"]
                if is_ext:
                    extreme_count += 1

                # 更新数据库
                new_loss_years = res["consecutive_loss_years"]
                new_loss = res["cumulative_loss"]
                old_reason_result = await session.execute(
                    sql_text("SELECT reason, risk_type FROM financial_risk WHERE id = :rid"),
                    {"rid": rid}
                )
                old_row = old_reason_result.first()
                old_reason = old_row[0] if old_row else ""
                old_type = old_row[1] if old_row else ""

                new_reason = old_reason
                new_type = old_type
                if is_ext:
                    loss_note = f"连续 {new_loss_years} 年净利润为负，累计亏损 {new_loss / 1e8:.2f} 亿"
                    new_reason = f"{old_reason}；{loss_note}" if old_reason else loss_note
                    new_type = "both" if old_type == "low_revenue" else "consecutive_loss"

                await session.execute(
                    sql_text(
                        "UPDATE financial_risk SET "
                        "is_extreme_risk = :ext, loss_years = :ly, "
                        "cumulative_loss = :cl, reason = :reason, risk_type = :rt "
                        "WHERE id = :rid"
                    ),
                    {
                        "ext": 1 if is_ext else 0,
                        "ly": new_loss_years,
                        "cl": new_loss,
                        "reason": new_reason,
                        "rt": new_type,
                        "rid": rid,
                    },
                )
            await session.commit()

        if (i + 30) % 100 == 0:
            logger.info("深度进度: %d/%d (极端: %d)", i + 30, total, extreme_count)

        await asyncio.sleep(BATCH_DELAY)

    stats = {
        "total_scanned": total,
        "updated": updated,
        "extreme_risk_count": extreme_count,
        "errors": errors,
    }
    logger.info("深度扫描完成: %s", stats)
    return stats
