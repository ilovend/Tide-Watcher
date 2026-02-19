import asyncio
import time
from collections import deque


class RateLimiter:
    """滑动窗口频率控制器。

    使用滑动窗口算法精确控制每分钟请求数，
    防止超出 ZhituAPI 的频率限制。
    """

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self._max_requests = max_requests
        self._window = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """获取一个请求许可，超频时自动等待。"""
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self._window
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) >= self._max_requests:
                wait_time = self._timestamps[0] - cutoff
                await asyncio.sleep(wait_time)
                now = time.monotonic()
                cutoff = now - self._window
                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.popleft()

            self._timestamps.append(time.monotonic())


class SingleCallLimiter:
    """单次调用限制器。

    专为 realall 等"每分钟最多1次"的接口设计。
    """

    def __init__(self, cooldown_seconds: int = 60):
        self._cooldown = cooldown_seconds
        self._last_call: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._cooldown:
                await asyncio.sleep(self._cooldown - elapsed)
            self._last_call = time.monotonic()
