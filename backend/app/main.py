import importlib
import logging
import pkgutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.data.dependencies import close_source
from app.store.database import init_db

logger = logging.getLogger(__name__)


def _discover_strategies() -> None:
    """自动发现并导入 strategies 目录下所有策略模块。

    导入即注册：每个策略文件中的 @strategy 装饰器会自动将策略注册到全局注册表。
    以下划线开头的文件（如 _template.py）会被跳过。
    """
    import app.strategies as pkg

    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("_"):
            continue
        module_name = f"app.strategies.{info.name}"
        try:
            importlib.import_module(module_name)
            logger.info("策略模块已加载: %s", module_name)
        except Exception:
            logger.exception("策略模块加载失败: %s", module_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化数据库和调度器，关闭时清理资源。"""
    # ----- 启动 -----
    logging.basicConfig(
        level=logging.DEBUG if settings.is_dev else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Tide-Watcher 启动中... (env=%s)", settings.app_env)

    await init_db()
    _discover_strategies()

    from app.engine.registry import get_all_strategies
    logger.info("已注册策略: %s", list(get_all_strategies().keys()))

    from app.engine.scheduler import start_scheduler
    await start_scheduler()

    yield

    # ----- 关闭 -----
    from app.engine.scheduler import stop_scheduler
    await stop_scheduler()
    await close_source()
    logger.info("Tide-Watcher 已关闭")


app = FastAPI(
    title="Tide-Watcher",
    description="A 股个人选股系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- 全局异常处理 -----
from app.api.error_handlers import global_exception_handler
app.add_exception_handler(Exception, global_exception_handler)

# ----- 注册路由 -----
from app.api.routes_stock import router as stock_router
from app.api.routes_strategy import router as strategy_router
from app.api.routes_pool import router as pool_router

app.include_router(stock_router)
app.include_router(strategy_router)
app.include_router(pool_router)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
