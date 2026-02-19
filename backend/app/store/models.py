import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, Boolean, func, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ==========================================================================
# 第一层：基础数据
# ==========================================================================

class Stock(Base):
    """股票基本信息表（增强版）。"""

    __tablename__ = "stocks"

    code: Mapped[str] = mapped_column(String(12), primary_key=True, comment="标准代码 如 000001.SZ")
    name: Mapped[str] = mapped_column(String(20), comment="股票名称")
    exchange: Mapped[str] = mapped_column(String(4), comment="交易所 SH/SZ/BJ")
    list_date: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="上市日期")
    total_shares: Mapped[float | None] = mapped_column(Float, nullable=True, comment="总股本(万股)")
    float_shares: Mapped[float | None] = mapped_column(Float, nullable=True, comment="流通股本(万股)")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否活跃")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class DailyKline(Base):
    """日K线数据表（1578万行历史数据，每日ZhituAPI增量更新）。"""

    __tablename__ = "daily_kline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(12), index=True, comment="股票代码 如 000001.SZ")
    trade_date: Mapped[str] = mapped_column(String(10), index=True, comment="交易日期 yyyy-MM-dd")
    open: Mapped[float] = mapped_column(Float, comment="开盘价")
    high: Mapped[float] = mapped_column(Float, comment="最高价")
    low: Mapped[float] = mapped_column(Float, comment="最低价")
    close: Mapped[float] = mapped_column(Float, comment="收盘价")
    pre_close: Mapped[float | None] = mapped_column(Float, nullable=True, comment="昨收价")
    volume: Mapped[float] = mapped_column(Float, default=0, comment="成交量")
    amount: Mapped[float] = mapped_column(Float, default=0, comment="成交额")
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="涨跌幅%")
    amplitude: Mapped[float | None] = mapped_column(Float, nullable=True, comment="振幅%")
    turnover: Mapped[float | None] = mapped_column(Float, nullable=True, comment="换手率%")


# ==========================================================================
# 第二层：盘面数据（结构化股池）
# ==========================================================================

class LimitUpPool(Base):
    """涨停股池（每日盘后从ZhituAPI同步）。"""

    __tablename__ = "limit_up_pool"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True, comment="交易日期")
    code: Mapped[str] = mapped_column(String(12), comment="股票代码")
    name: Mapped[str] = mapped_column(String(20), default="", comment="名称")
    price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="现价")
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="涨跌幅%")
    amount: Mapped[float | None] = mapped_column(Float, nullable=True, comment="成交额")
    float_mv: Mapped[float | None] = mapped_column(Float, nullable=True, comment="流通市值")
    total_mv: Mapped[float | None] = mapped_column(Float, nullable=True, comment="总市值")
    turnover: Mapped[float | None] = mapped_column(Float, nullable=True, comment="换手率%")
    limit_count: Mapped[int] = mapped_column(Integer, default=1, comment="连板数")
    first_limit_time: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="首次封板时间")
    last_limit_time: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="最后封板时间")
    limit_amount: Mapped[float | None] = mapped_column(Float, nullable=True, comment="封单金额")
    break_count: Mapped[int] = mapped_column(Integer, default=0, comment="开板次数")
    limit_stat: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="连板统计如3/3")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("ix_limit_up_code_date", "code", "trade_date"),)


class BrokenBoardPool(Base):
    """炸板股池（每日盘后从ZhituAPI同步）。"""

    __tablename__ = "broken_board_pool"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True, comment="交易日期")
    code: Mapped[str] = mapped_column(String(12), comment="股票代码")
    name: Mapped[str] = mapped_column(String(20), default="", comment="名称")
    price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="现价")
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="涨跌幅%")
    amount: Mapped[float | None] = mapped_column(Float, nullable=True, comment="成交额")
    float_mv: Mapped[float | None] = mapped_column(Float, nullable=True, comment="流通市值")
    turnover: Mapped[float | None] = mapped_column(Float, nullable=True, comment="换手率%")
    break_count: Mapped[int] = mapped_column(Integer, default=0, comment="开板次数")
    first_limit_time: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="首次封板时间")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("ix_broken_code_date", "code", "trade_date"),)


class StrongPool(Base):
    """强势股池（每日盘后从ZhituAPI同步）。"""

    __tablename__ = "strong_pool"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True, comment="交易日期")
    code: Mapped[str] = mapped_column(String(12), comment="股票代码")
    name: Mapped[str] = mapped_column(String(20), default="", comment="名称")
    price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="现价")
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True, comment="涨跌幅%")
    amount: Mapped[float | None] = mapped_column(Float, nullable=True, comment="成交额")
    float_mv: Mapped[float | None] = mapped_column(Float, nullable=True, comment="流通市值")
    turnover: Mapped[float | None] = mapped_column(Float, nullable=True, comment="换手率%")
    streak_days: Mapped[int] = mapped_column(Integer, default=0, comment="强势天数")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("ix_strong_code_date", "code", "trade_date"),)


# ==========================================================================
# 第三层：情绪数据
# ==========================================================================

class EmotionSnapshot(Base):
    """市场情绪快照（基于涨停/炸板数据自动计算）。"""

    __tablename__ = "emotion_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), unique=True, comment="交易日期")
    limit_up_count: Mapped[int] = mapped_column(Integer, default=0, comment="涨停数")
    broken_board_count: Mapped[int] = mapped_column(Integer, default=0, comment="炸板数")
    broken_rate: Mapped[float] = mapped_column(Float, default=0.0, comment="炸板率%")
    max_streak: Mapped[int] = mapped_column(Integer, default=0, comment="最高连板")
    first_board_count: Mapped[int] = mapped_column(Integer, default=0, comment="首板数量")
    promotion_rate: Mapped[float] = mapped_column(Float, default=0.0, comment="晋级率%")
    total_limit_amount: Mapped[float] = mapped_column(Float, default=0.0, comment="涨停总成交额")
    phase: Mapped[str] = mapped_column(String(20), default="", comment="情绪阶段 ice/retreat/ferment/boom/frenzy")
    phase_score: Mapped[float] = mapped_column(Float, default=0.0, comment="情绪评分 0-100")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())


# ==========================================================================
# 第四层：板块数据
# ==========================================================================

class Sector(Base):
    """板块定义表（从MySQL迁移的静态映射数据）。"""

    __tablename__ = "sector"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_code: Mapped[str] = mapped_column(String(30), unique=True, comment="板块代码 如 101075.BKZS")
    sector_name: Mapped[str] = mapped_column(String(100), comment="板块名称")
    sector_type: Mapped[str] = mapped_column(String(20), index=True, comment="类型 concept/industry")
    stock_count: Mapped[int] = mapped_column(Integer, default=0, comment="成分股数量")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否活跃")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class StockSector(Base):
    """股票-板块关联表（多对多，从MySQL迁移）。"""

    __tablename__ = "stock_sector"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(12), index=True, comment="股票代码（纯代码如000001）")
    sector_code: Mapped[str] = mapped_column(String(30), index=True, comment="板块代码")
    sector_name: Mapped[str] = mapped_column(String(100), default="", comment="板块名称（冗余）")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (Index("ix_ss_stock_sector", "stock_code", "sector_code", unique=True),)


# ==========================================================================
# 第四层B：财务风控
# ==========================================================================

class FinancialRisk(Base):
    """财务风险标记表（季度扫描，缓存在SQLite中）。

    排雷规则：
      - consecutive_loss: 净利润连续为负且累计亏损>3亿
      - low_revenue: 最近一个会计年度营收<1亿
    """

    __tablename__ = "financial_risk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(12), index=True, comment="股票代码 如 000001.SZ")
    name: Mapped[str] = mapped_column(String(20), default="", comment="股票名称")
    risk_type: Mapped[str] = mapped_column(String(30), comment="风险类型 consecutive_loss/low_revenue/both")
    risk_level: Mapped[str] = mapped_column(String(10), default="high", comment="风险等级 high/medium")
    reason: Mapped[str] = mapped_column(Text, default="", comment="风险说明")
    cumulative_loss: Mapped[float | None] = mapped_column(Float, nullable=True, comment="累计亏损(元)")
    latest_revenue: Mapped[float | None] = mapped_column(Float, nullable=True, comment="最新年度营收(元)")
    latest_net_profit: Mapped[float | None] = mapped_column(Float, nullable=True, comment="最新净利润(元)")
    loss_years: Mapped[int] = mapped_column(Integer, default=0, comment="连续亏损年数")
    is_extreme_risk: Mapped[bool] = mapped_column(Boolean, default=False, comment="极端风险（连续3年扣非亏损）")
    scan_date: Mapped[str] = mapped_column(String(10), index=True, comment="扫描日期")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_fr_code_scan", "code", "scan_date"),)


# ==========================================================================
# 第五层：策略与用户
# ==========================================================================

class StrategySignal(Base):
    """策略产生的选股信号表。"""

    __tablename__ = "strategy_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(50), index=True, comment="策略名称")
    stock_code: Mapped[str] = mapped_column(String(12), index=True, comment="股票代码")
    stock_name: Mapped[str] = mapped_column(String(20), default="", comment="股票名称")
    signal_date: Mapped[str] = mapped_column(String(10), index=True, comment="信号日期 yyyy-MM-dd")
    score: Mapped[float] = mapped_column(Float, default=0.0, comment="信号评分 0~100")
    reason: Mapped[str] = mapped_column(Text, default="", comment="入选理由")
    extra_data: Mapped[str] = mapped_column(Text, default="{}", comment="附加数据 JSON")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class Watchlist(Base):
    """自选股表。"""

    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(12), index=True, comment="股票代码")
    name: Mapped[str] = mapped_column(String(20), default="", comment="名称")
    note: Mapped[str] = mapped_column(Text, default="", comment="备注")
    tags: Mapped[str] = mapped_column(String(200), default="", comment="标签(逗号分隔)")
    added_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
