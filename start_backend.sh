#!/bin/bash
# 启动后端服务（排除数据目录，避免无限重启）

cd "$(dirname "$0")"

python -m uvicorn backend.main:app \
    --reload \
    --port 8000 \
    --reload-exclude "data/*" \
    --reload-exclude "chrome_profile/*" \
    --reload-exclude "*.pyc" \
    --reload-exclude "__pycache__/*"
