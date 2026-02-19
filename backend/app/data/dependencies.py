from app.data.source_zhitu import ZhituSource

_shared_source: ZhituSource | None = None


def get_source() -> ZhituSource:
    """获取全局共享的 ZhituSource 实例（惰性初始化）。"""
    global _shared_source
    if _shared_source is None:
        _shared_source = ZhituSource()
    return _shared_source


async def close_source() -> None:
    """关闭共享数据源连接（应用关闭时调用）。"""
    global _shared_source
    if _shared_source is not None:
        await _shared_source.close()
        _shared_source = None
