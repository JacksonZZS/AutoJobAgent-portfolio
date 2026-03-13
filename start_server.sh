#!/bin/bash

# AutoJobAgent 服务器启动脚本
# 自动配置 WeasyPrint 所需的环境变量

echo "🚀 启动 AutoJobAgent 后端服务器..."
echo ""

# 设置 WeasyPrint 系统依赖库路径
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/pango/lib:/opt/homebrew/opt/gdk-pixbuf/lib:/opt/homebrew/opt/libffi/lib:$DYLD_LIBRARY_PATH"

echo "✅ 环境变量已设置:"
echo "   DYLD_LIBRARY_PATH=$DYLD_LIBRARY_PATH"
echo ""

# 激活虚拟环境
source venv_career/bin/activate

echo "✅ 虚拟环境已激活: venv_career"
echo ""

# 启动服务器
echo "🌐 启动 Uvicorn 服务器..."
echo "   访问地址: http://localhost:8000"
echo "   API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "=" * 80
echo ""

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
