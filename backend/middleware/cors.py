"""
CORS 中间件配置
允许前端跨域访问 API
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def setup_cors(app: FastAPI):
    """
    配置 CORS 中间件

    Args:
        app: FastAPI 应用实例
    """

    # 允许的源（开发环境）
    origins = [
        "http://localhost:5173",  # Vite 默认端口
        "http://localhost:5174",  # Vite 备用端口
        "http://localhost:5175",  # Vite 备用端口
        "http://localhost:5176",  # Vite 备用端口
        "http://localhost:5177",  # Vite 备用端口
        "http://localhost:3000",  # 备用前端端口
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
        "http://127.0.0.1:5177",
        "http://127.0.0.1:3000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,  # 允许的源
        allow_credentials=True,  # 允许携带 Cookie
        allow_methods=["*"],     # 允许所有 HTTP 方法
        allow_headers=["*"],     # 允许所有请求头
    )

    print("[CORS] Middleware configured successfully")
