import asyncio
import logging
import time
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class MemoryCache:
    """内存缓存层。

    按 key 缓存数据，支持 TTL 过期。
    用于减少对 ZhituAPI 的重复请求，节省配额。

    缓存策略：
    - 实时行情：60秒（realall 接口本身每分钟限1次）
    - 股票列表：1小时（每日仅更新一次）
    - 股池数据：5分钟（交易时段每10分钟更新）
    - 公司信息：24小时（每日凌晨更新）
    - K线数据：5分钟（盘中实时更新）
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """获取缓存值，过期返回 None。"""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """设置缓存值。

        Args:
            key:   缓存键
            value: 缓存值
            ttl:   存活时间（秒）
        """
        async with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)

    async def get_or_fetch(
        self,
        key: str,
        ttl: int,
        fetcher: Callable[[], Coroutine[Any, Any, Any]],
    ) -> Any:
        """获取缓存，未命中则调用 fetcher 获取并缓存。"""
        cached = await self.get(key)
        if cached is not None:
            logger.debug("缓存命中: %s", key)
            return cached

        logger.debug("缓存未命中，请求数据: %s", key)
        value = await fetcher()
        await self.set(key, value, ttl)
        return value

    async def invalidate(self, key: str) -> None:
        """手动使某个缓存失效。"""
        async with self._lock:
            self._store.pop(key, None)

    async def clear(self) -> None:
        """清空全部缓存。"""
        async with self._lock:
            self._store.clear()
            logger.info("缓存已清空")

    @property
    def size(self) -> int:
        return len(self._store)


# 预定义 TTL 常量（秒）
TTL_REALTIME = 60       # 实时行情 60 秒
TTL_POOL = 300          # 股池 5 分钟
TTL_KLINE = 300         # K线 5 分钟
TTL_STOCK_LIST = 3600   # 股票列表 1 小时
TTL_COMPANY = 86400     # 公司信息 24 小时
TTL_FINANCE = 3600      # 财务数据 1 小时
TTL_INDICATOR = 300     # 技术指标 5 分钟

# 全局缓存单例
cache = MemoryCache()
