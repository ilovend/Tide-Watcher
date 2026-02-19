from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# SQLite 需要 aiosqlite 驱动
_url = settings.database_url
if _url.startswith("sqlite:///"):
    _url = _url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

engine = create_async_engine(_url, echo=settings.is_dev)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """创建所有表（首次启动时调用）。"""
    from app.store.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
