"""
了了中间件 — 错误追踪、日志、请求度量

从 server.py 提取，与 pipeline.py 配合。
"""

import time
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


# ═══ 全局错误追踪 ═══
_pipeline_errors: list = []


def pipeline_error(layer: str, error: Exception, context: str = "") -> None:
    """记录管线层错误。"""
    msg = f"[{layer}] {type(error).__name__}: {str(error)[:100]}"
    if context:
        msg += f" | {context[:80]}"
    _pipeline_errors.append(msg)
    print(f"⚠ Pipeline error: {msg}")


def get_pipeline_errors() -> list:
    return _pipeline_errors


def clear_pipeline_errors() -> None:
    _pipeline_errors.clear()


# ═══ 请求度量和日志 ═══

class RequestTracker:
    """追踪请求计数和最近请求。"""
    _count: int = 0
    _last_request: str = ""
    _start_time: float = time.time()

    @classmethod
    def tick(cls, path: str = "") -> None:
        cls._count += 1
        cls._last_request = path

    @classmethod 
    def stats(cls) -> dict:
        return {
            "total_requests": cls._count,
            "uptime_seconds": int(time.time() - cls._start_time),
            "last_request": cls._last_request,
        }


class PipelineMetricsMiddleware(BaseHTTPMiddleware):
    """FastAPI 中间件：追踪请求，注入 pipeline 错误追踪。"""
    
    async def dispatch(self, request: Request, call_next):
        RequestTracker.tick(request.url.path)
        
        response = await call_next(request)
        
        # 在响应头注入 pipeline 错误计数
        errors = get_pipeline_errors()
        if errors:
            response.headers["X-Pipeline-Errors"] = str(len(errors))
        
        return response


def create_middleware(app):
    """注册所有中间件到 FastAPI app。"""
    app.add_middleware(PipelineMetricsMiddleware)
