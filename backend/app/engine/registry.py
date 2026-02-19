import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# 策略函数签名: async def my_strategy(ctx: StrategyContext) -> list[dict]
StrategyFunc = Callable[..., Coroutine[Any, Any, list[dict[str, Any]]]]


@dataclass
class StrategyMeta:
    """策略元信息。"""

    name: str
    func: StrategyFunc
    schedule: str = ""
    description: str = ""
    enabled: bool = True
    tags: list[str] = field(default_factory=list)


# 全局策略注册表（单例）
_registry: dict[str, StrategyMeta] = {}


def strategy(
    name: str,
    schedule: str = "",
    description: str = "",
    enabled: bool = True,
    tags: list[str] | None = None,
) -> Callable[[StrategyFunc], StrategyFunc]:
    """策略注册装饰器。

    用法：
        @strategy(name="涨停板筛选", schedule="14:50")
        async def limit_up_filter(ctx):
            ...

    Args:
        name:        策略显示名称（中文）
        schedule:    每日执行时间（HH:MM 格式），空字符串表示仅手动触发
        description: 策略描述
        enabled:     是否启用
        tags:        标签列表，用于分类筛选
    """

    def decorator(func: StrategyFunc) -> StrategyFunc:
        if name in _registry:
            logger.warning("策略 '%s' 已注册，将被覆盖", name)

        _registry[name] = StrategyMeta(
            name=name,
            func=func,
            schedule=schedule,
            description=description or (func.__doc__ or "").strip(),
            enabled=enabled,
            tags=tags or [],
        )
        logger.info("策略已注册: %s (定时: %s)", name, schedule or "手动")
        return func

    return decorator


def get_strategy(name: str) -> StrategyMeta | None:
    return _registry.get(name)


def get_all_strategies() -> dict[str, StrategyMeta]:
    return dict(_registry)


def get_enabled_strategies() -> list[StrategyMeta]:
    return [s for s in _registry.values() if s.enabled]


def get_scheduled_strategies() -> list[StrategyMeta]:
    return [s for s in _registry.values() if s.enabled and s.schedule]
