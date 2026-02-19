import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理器，将未捕获的异常转为友好 JSON 响应。"""
    error_msg = str(exc)

    if "ZhituAPI 错误" in error_msg:
        logger.warning("ZhituAPI 业务错误: %s %s → %s", request.method, request.url.path, error_msg)
        return JSONResponse(
            status_code=502,
            content={"error": "数据源返回错误", "detail": error_msg},
        )

    if "HTTPStatusError" in type(exc).__name__ or "400" in error_msg:
        logger.warning("上游 API 错误: %s %s → %s", request.method, request.url.path, error_msg)
        return JSONResponse(
            status_code=502,
            content={"error": "数据源请求失败", "detail": error_msg},
        )

    if "ValueError" in type(exc).__name__:
        return JSONResponse(
            status_code=400,
            content={"error": "参数错误", "detail": error_msg},
        )

    logger.error("未处理异常: %s %s\n%s", request.method, request.url.path, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": "服务器内部错误", "detail": error_msg},
    )
