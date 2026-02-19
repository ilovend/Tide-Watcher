from abc import ABC, abstractmethod
from typing import Any


class DataSource(ABC):
    """数据源抽象基类。

    所有外部数据源（ZhituAPI、东财、同花顺等）都必须实现此接口。
    业务层只依赖此基类，不直接依赖具体数据源，实现可插拔替换。
    """

    @abstractmethod
    async def get_stock_list(self) -> list[dict[str, Any]]:
        """获取全市场股票列表。"""

    @abstractmethod
    async def get_realtime_quote(self, code: str) -> dict[str, Any]:
        """获取单只股票实时行情。"""

    @abstractmethod
    async def get_realtime_all(self) -> list[dict[str, Any]]:
        """获取全市场实时行情快照。"""

    @abstractmethod
    async def get_history_kline(
        self,
        code: str,
        level: str,
        adjust: str,
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        """获取历史K线数据。

        Args:
            code:   股票代码（标准格式，如 000001.SZ）
            level:  K线级别 (5/15/30/60/d/w/m/y)
            adjust: 复权类型 (n/f/b/fr/br)
            start:  开始日期 YYYYMMDD
            end:    结束日期 YYYYMMDD
        """

    @abstractmethod
    async def get_pool(self, pool_type: str, date: str) -> list[dict[str, Any]]:
        """获取股池数据。

        Args:
            pool_type: 股池类型 (ztgc/dtgc/qsgc/cxgc/zbgc)
            date:      日期 yyyy-MM-dd
        """

    @abstractmethod
    async def get_company_info(self, code: str, info_type: str) -> dict[str, Any]:
        """获取公司信息。

        Args:
            code:      纯股票代码（如 000001）
            info_type: 信息类型 (gsjj/sszs/cwzb/sdgd/ltgd/ssbk 等)
        """

    @abstractmethod
    async def get_finance_report(
        self,
        code: str,
        report_type: str,
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        """获取财务报表。

        Args:
            code:        股票代码（标准格式，如 000001.SZ）
            report_type: 报表类型 (balance/income/cashflow/ratios)
            start:       开始日期 YYYYMMDD
            end:         结束日期 YYYYMMDD
        """

    @abstractmethod
    async def get_technical_indicator(
        self,
        code: str,
        indicator: str,
        level: str,
        adjust: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        """获取技术指标数据。

        Args:
            code:      股票代码（标准格式，如 000001.SZ）
            indicator: 指标类型 (macd/ma/boll/kdj)
            level:     K线级别
            adjust:    复权类型
            start:     开始日期（可选）
            end:       结束日期（可选）
        """

    @abstractmethod
    async def get_fund_flow(
        self,
        code: str,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """获取资金流向数据。"""
