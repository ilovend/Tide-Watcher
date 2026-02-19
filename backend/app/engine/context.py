import datetime
from typing import Any

from app.data.source_base import DataSource


class StrategyContext:
    """策略执行上下文。

    每次策略执行时由引擎自动创建，为策略函数提供数据访问能力。
    策略作者通过 ctx 获取行情、股池、K线等数据，无需关心底层 API 细节。
    """

    def __init__(self, source: DataSource, run_date: str | None = None) -> None:
        self._source = source
        self.run_date = run_date or datetime.date.today().strftime("%Y-%m-%d")
        self.results: list[dict[str, Any]] = []

    # ----- 便捷数据获取方法 -----

    async def get_pool(self, pool_type: str, date: str | None = None) -> list[dict[str, Any]]:
        """获取股池数据。

        Args:
            pool_type: 支持中文名（涨停股池/跌停股池/强势股池/次新股池/炸板股池）
                       或代码（ztgc/dtgc/qsgc/cxgc/zbgc）
            date:      日期，默认为策略运行日期
        """
        return await self._source.get_pool(pool_type, date or self.run_date)

    async def get_realtime(self, code: str) -> dict[str, Any]:
        """获取单只股票实时行情。"""
        return await self._source.get_realtime_quote(code)

    async def get_realtime_all(self) -> list[dict[str, Any]]:
        """获取全市场实时行情快照。"""
        return await self._source.get_realtime_all()

    async def get_kline(
        self,
        code: str,
        level: str = "d",
        adjust: str = "n",
        start: str = "",
        end: str = "",
    ) -> list[dict[str, Any]]:
        """获取历史K线。"""
        return await self._source.get_history_kline(code, level, adjust, start, end)

    async def get_company(self, code: str, info_type: str) -> dict[str, Any]:
        """获取公司信息。"""
        return await self._source.get_company_info(code, info_type)

    async def get_finance(
        self,
        code: str,
        report_type: str,
        start: str = "",
        end: str = "",
    ) -> list[dict[str, Any]]:
        """获取财务报表。"""
        return await self._source.get_finance_report(code, report_type, start, end)

    async def get_indicator(
        self,
        code: str,
        indicator: str = "macd",
        level: str = "d",
        adjust: str = "n",
    ) -> list[dict[str, Any]]:
        """获取技术指标。"""
        return await self._source.get_technical_indicator(code, indicator, level, adjust)

    async def get_fund_flow(
        self,
        code: str,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """获取资金流向。"""
        return await self._source.get_fund_flow(code, start, end, limit)

    # ----- 结果收集 -----

    def add_signal(
        self,
        code: str,
        name: str = "",
        score: float = 0.0,
        reason: str = "",
        **extra: Any,
    ) -> None:
        """添加一条选股信号到结果集。"""
        self.results.append({
            "stock_code": code,
            "stock_name": name,
            "score": score,
            "reason": reason,
            "extra": extra,
        })
