"""
全局错误处理中间件
提供统一的错误响应格式
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import traceback


async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理器

    Args:
        request: 请求对象
        exc: 异常对象

    Returns:
        统一格式的错误响应
    """

    # 打印详细错误信息（开发环境）
    print(f"[ERROR] {request.method} {request.url.path}")
    print(f"[ERROR] {type(exc).__name__}: {str(exc)}")
    traceback.print_exc()

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": str(exc),
            "path": str(request.url.path),
            "method": request.method
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    请求验证错误处理器

    Args:
        request: 请求对象
        exc: 验证异常对象

    Returns:
        格式化的验证错误响应
    """

    print(f"[VALIDATION ERROR] {request.method} {request.url.path}")
    print(f"[VALIDATION ERROR] {exc.errors()}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "path": str(request.url.path)
        }
    )
