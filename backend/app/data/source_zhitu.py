import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.data.cache import (
    cache, TTL_REALTIME, TTL_POOL, TTL_KLINE, TTL_STOCK_LIST,
    TTL_COMPANY, TTL_FINANCE, TTL_INDICATOR,
)
from app.data.rate_limiter import RateLimiter, SingleCallLimiter
from app.data.source_base import DataSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 股票代码标准化工具
# ---------------------------------------------------------------------------

# 交易所识别规则
_EXCHANGE_RULES: dict[str, str] = {
    "6": "SH",   # 沪市主板
    "9": "SH",   # 沪市 B 股
    "5": "SH",   # 沪市基金/权证
    "0": "SZ",   # 深市主板
    "1": "SZ",   # 深市基金
    "2": "SZ",   # 深市 B 股
    "3": "SZ",   # 创业板
    "4": "BJ",   # 北交所（老三板/新三板）
    "8": "BJ",   # 北交所
}


def detect_exchange(pure_code: str) -> str:
    """根据纯数字代码首位推断交易所。"""
    prefix = pure_code[0]
    exchange = _EXCHANGE_RULES.get(prefix)
    if exchange is None:
        raise ValueError(f"无法识别股票代码 {pure_code} 的交易所归属")
    return exchange


def normalize_code(raw: str) -> str:
    """将任意格式的股票代码统一为 '000001.SZ' 标准格式。

    支持输入格式：
        000001  /  000001.SZ  /  sz000001  /  SZ000001
        sh600519  /  600519.SH  /  600519
    """
    raw = raw.strip().upper()

    if "." in raw:
        parts = raw.split(".")
        return f"{parts[0]}.{parts[1]}"

    if raw[:2] in ("SH", "SZ", "BJ"):
        exchange = raw[:2]
        code = raw[2:]
        return f"{code}.{exchange}"

    return f"{raw}.{detect_exchange(raw)}"


def to_pure_code(raw: str) -> str:
    """提取纯数字代码（用于公司信息等只需纯代码的接口）。"""
    raw = raw.strip().upper()
    if "." in raw:
        return raw.split(".")[0]
    if raw[:2] in ("SH", "SZ", "BJ"):
        return raw[2:]
    return raw


# ---------------------------------------------------------------------------
# 股池类型映射
# ---------------------------------------------------------------------------

_POOL_MAP: dict[str, str] = {
    "涨停股池": "ztgc",
    "跌停股池": "dtgc",
    "强势股池": "qsgc",
    "次新股池": "cxgc",
    "炸板股池": "zbgc",
    "ztgc": "ztgc",
    "dtgc": "dtgc",
    "qsgc": "qsgc",
    "cxgc": "cxgc",
    "zbgc": "zbgc",
}

# ---------------------------------------------------------------------------
# 公司信息接口路径映射
# ---------------------------------------------------------------------------

_COMPANY_INFO_MAP: dict[str, str] = {
    "gsjj": "/hs/gs/gsjj",
    "sszs": "/hs/gs/sszs",
    "ljgg": "/hs/gs/ljgg",
    "ljds": "/hs/gs/ljds",
    "ljjs": "/hs/gs/ljjs",
    "jnff": "/hs/gs/jnff",
    "jnzf": "/hs/gs/jnzf",
    "jjxs": "/hs/gs/jjxs",
    "jdlr": "/hs/gs/jdlr",
    "jdxj": "/hs/gs/jdxj",
    "yjyg": "/hs/gs/yjyg",
    "cwzb": "/hs/gs/cwzb",
    "sdgd": "/hs/gs/sdgd",
    "ltgd": "/hs/gs/ltgd",
    "gdbh": "/hs/gs/gdbh",
    "jjcg": "/hs/gs/jjcg",
    "ssbk": "/hs/gs/ssbk",
    "jyfw": "/hs/gs/jyfw",
}

# ---------------------------------------------------------------------------
# ZhituAPI 适配器
# ---------------------------------------------------------------------------

# 可重试的异常类型
_RETRYABLE = (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)


class ZhituSource(DataSource):
    """ZhituAPI 数据源适配器。

    特性：
    - 自动频率控制（通用 3000 次/分 + realall 1 次/分）
    - 网络异常自动重试（指数退避，最多 3 次）
    - 股票代码自动标准化
    """

    def __init__(self) -> None:
        self._base_url = settings.zhitu_base_url
        self._token = settings.zhitu_token
        self._timeout = settings.zhitu_timeout
        self._max_retries = settings.zhitu_max_retries

        self._general_limiter = RateLimiter(settings.zhitu_rate_limit)
        self._realall_limiter = SingleCallLimiter(cooldown_seconds=60)

        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ----- 底层请求 -----

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        use_realall_limiter: bool = False,
    ) -> Any:
        """统一请求入口，自带频率控制和重试。"""
        if use_realall_limiter:
            await self._realall_limiter.acquire()
        await self._general_limiter.acquire()

        client = await self._ensure_client()
        merged_params = {"token": self._token}
        if params:
            merged_params.update(params)
        resp = await client.get(path, params=merged_params)
        resp.raise_for_status()
        payload = resp.json()

        if isinstance(payload, dict) and payload.get("code") not in (None, 0, 200):
            msg = payload.get("msg", "未知错误")
            logger.error("ZhituAPI 业务错误: %s → %s", path, msg)
            raise RuntimeError(f"ZhituAPI 错误: {msg}")

        data = payload.get("data", payload) if isinstance(payload, dict) else payload
        return data

    # ----- 基础列表 -----

    async def get_stock_list(self) -> list[dict[str, Any]]:
        return await cache.get_or_fetch(
            "stock_list", TTL_STOCK_LIST,
            lambda: self._request("/hs/list/all"),
        )

    # ----- 实时行情 -----

    async def get_realtime_quote(self, code: str) -> dict[str, Any]:
        code = normalize_code(code)
        pure = to_pure_code(code)
        return await cache.get_or_fetch(
            f"realtime:{pure}", TTL_REALTIME,
            lambda: self._request(f"/hs/real/ssjy/{pure}"),
        )

    async def get_realtime_all(self) -> list[dict[str, Any]]:
        return await cache.get_or_fetch(
            "realtime_all", TTL_REALTIME,
            lambda: self._request("/hs/public/realall", use_realall_limiter=True),
        )

    async def get_realtime_batch(self, codes: list[str]) -> list[dict[str, Any]]:
        """批量获取实时行情（最多 20 只）。"""
        normalized = [to_pure_code(normalize_code(c)) for c in codes[:20]]
        return await self._request(
            "/hs/public/ssjymore",
            params={"stock_codes": ",".join(normalized)},
        )

    # ----- 历史K线 -----

    async def get_history_kline(
        self,
        code: str,
        level: str = "d",
        adjust: str = "n",
        start: str = "",
        end: str = "",
    ) -> list[dict[str, Any]]:
        code = normalize_code(code)
        params: dict[str, str] = {}
        if start:
            params["st"] = start
        if end:
            params["et"] = end
        return await self._request(
            f"/hs/history/{code}/{level}/{adjust}",
            params=params or None,
        )

    async def get_latest_kline(
        self,
        code: str,
        level: str = "d",
        adjust: str = "n",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """获取最新 N 条K线。

        注意：ZhituAPI 的 latest 接口 limit 最大为 5，
        超过时自动切换到历史数据接口获取。
        """
        code = normalize_code(code)
        if limit <= 5:
            return await self._request(
                f"/hs/latest/{code}/{level}/{adjust}",
                params={"limit": str(limit)},
            )
        # limit > 5 时用历史接口，取足够长的日期范围
        import datetime
        end = datetime.date.today().strftime("%Y%m%d")
        # 日线取 limit*2 天覆盖非交易日；分钟级取更短范围
        days_back = limit * 2 if level in ("d", "w", "m", "y") else limit
        start = (datetime.date.today() - datetime.timedelta(days=days_back)).strftime("%Y%m%d")
        data = await self.get_history_kline(code, level, adjust, start, end)
        return data[-limit:] if len(data) > limit else data

    # ----- 股池 -----

    async def get_pool(self, pool_type: str, date: str) -> list[dict[str, Any]]:
        slug = _POOL_MAP.get(pool_type)
        if slug is None:
            raise ValueError(
                f"未知股池类型: {pool_type}，可选: {list(_POOL_MAP.keys())}"
            )
        return await cache.get_or_fetch(
            f"pool:{slug}:{date}", TTL_POOL,
            lambda: self._request(f"/hs/pool/{slug}/{date}"),
        )

    # ----- 公司信息 -----

    async def get_company_info(self, code: str, info_type: str) -> dict[str, Any]:
        pure = to_pure_code(code)
        path_prefix = _COMPANY_INFO_MAP.get(info_type)
        if path_prefix is None:
            raise ValueError(
                f"未知公司信息类型: {info_type}，可选: {list(_COMPANY_INFO_MAP.keys())}"
            )
        return await self._request(f"{path_prefix}/{pure}")

    # ----- 财务报表 -----

    async def get_finance_report(
        self,
        code: str,
        report_type: str,
        start: str = "",
        end: str = "",
    ) -> list[dict[str, Any]]:
        code = normalize_code(code)
        report_path_map = {
            "balance": "/hs/fin/balance",
            "income": "/hs/fin/income",
            "cashflow": "/hs/fin/cashflow",
            "ratios": "/hs/fin/ratios",
            "capital": "/hs/fin/capital",
            "topholder": "/hs/fin/topholder",
            "flowholder": "/hs/fin/flowholder",
            "hm": "/hs/fin/hm",
        }
        prefix = report_path_map.get(report_type)
        if prefix is None:
            raise ValueError(
                f"未知报表类型: {report_type}，可选: {list(report_path_map.keys())}"
            )
        params: dict[str, str] = {}
        if start:
            params["st"] = start
        if end:
            params["et"] = end
        return await self._request(f"{prefix}/{code}", params=params or None)

    # ----- 技术指标 -----

    async def get_technical_indicator(
        self,
        code: str,
        indicator: str = "macd",
        level: str = "d",
        adjust: str = "n",
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        code = normalize_code(code)
        valid = ("macd", "ma", "boll", "kdj")
        if indicator not in valid:
            raise ValueError(f"未知技术指标: {indicator}，可选: {valid}")
        params: dict[str, str] = {}
        if start:
            params["st"] = start
        if end:
            params["et"] = end
        return await self._request(
            f"/hs/history/{indicator}/{code}/{level}/{adjust}",
            params=params or None,
        )

    # ----- 资金流向 -----

    async def get_fund_flow(
        self,
        code: str,
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        pure = to_pure_code(code)
        params: dict[str, str] = {}
        if start:
            params["st"] = start
        if end:
            params["et"] = end
        if limit:
            params["lt"] = str(limit)
        return await self._request(
            f"/hs/history/transaction/{pure}",
            params=params or None,
        )

    # ----- 行情指标 -----

    async def get_market_indicators(
        self,
        code: str,
        start: str = "",
        end: str = "",
    ) -> list[dict[str, Any]]:
        """获取量比、涨速、多日涨幅等行情指标。"""
        code = normalize_code(code)
        params: dict[str, str] = {}
        if start:
            params["st"] = start
        if end:
            params["et"] = end
        return await self._request(
            f"/hs/indicators/{code}",
            params=params or None,
        )

    # ----- 五档盘口 -----

    async def get_order_book(self, code: str) -> dict[str, Any]:
        """获取买卖五档盘口。"""
        pure = to_pure_code(code)
        return await self._request(f"/hs/real/five/{pure}")

    # ----- 股票基础信息 -----

    async def get_instrument(self, code: str) -> dict[str, Any]:
        """获取股票基础信息（涨跌停价、市值、停牌状态等）。"""
        code = normalize_code(code)
        return await self._request(f"/hs/instrument/{code}")
