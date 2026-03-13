#!/bin/bash

# ============================================
# AutoJobAgent - One-Click Deploy Script
# ============================================

set -e

echo "🚀 AutoJobAgent 一键部署脚本"
echo "================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  建议使用普通用户运行，而非 root${NC}"
fi

# Step 1: Check Docker
echo ""
echo "📦 Step 1: 检查 Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker 未安装${NC}"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose 未安装${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker 已就绪${NC}"

# Step 2: Check .env file
echo ""
echo "🔑 Step 2: 检查环境变量..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo -e "${YELLOW}⚠️  未找到 .env 文件，从模板创建...${NC}"
        cp .env.example .env
        echo -e "${RED}❗ 请编辑 .env 文件，填入你的 ANTHROPIC_API_KEY${NC}"
        echo "   nano .env"
        exit 1
    else
        echo -e "${RED}❌ 未找到 .env.example 文件${NC}"
        exit 1
    fi
fi

# Check if API key is set
if grep -q "sk-ant-xxxxx" .env; then
    echo -e "${RED}❗ 请先在 .env 中设置你的 ANTHROPIC_API_KEY${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 环境变量已配置${NC}"

# Step 3: Create necessary directories
echo ""
echo "📁 Step 3: 创建数据目录..."
mkdir -p data/uploads data/outputs data/status data/sessions data/browser_profiles data/locks deploy/ssl
echo -e "${GREEN}✅ 目录已创建${NC}"

# Step 4: Build and start
echo ""
echo "🔨 Step 4: 构建 Docker 镜像..."
docker compose build --no-cache

echo ""
echo "🚀 Step 5: 启动服务..."
docker compose up -d

# Step 6: Wait for health check
echo ""
echo "⏳ Step 6: 等待服务启动..."
sleep 5

# Check if service is running
if docker compose ps | grep -q "Up"; then
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}✅ 部署成功！${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "🌐 访问地址: http://$(hostname -I | awk '{print $1}'):8000"
    echo "📊 健康检查: http://$(hostname -I | awk '{print $1}'):8000/health"
    echo ""
    echo "📝 常用命令:"
    echo "   查看日志: docker compose logs -f"
    echo "   停止服务: docker compose down"
    echo "   重启服务: docker compose restart"
    echo ""
else
    echo -e "${RED}❌ 启动失败，请检查日志:${NC}"
    docker compose logs
    exit 1
fi
