#!/bin/bash
# 本地开发环境一键启动
# 用法: bash scripts/dev.sh

set -e
cd "$(dirname "$0")/.."

# 1. 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# 2. 检查 .env
if [ ! -f .env ]; then
    echo "⚠️  缺少 .env，从模板创建..."
    cp deploy/.env.example .env
    echo "请编辑 .env 填入飞书凭证后重新运行"
    exit 1
fi

# 3. 启动服务
echo "🚀 启动开发服务器..."
echo "   API:    http://localhost:8000"
echo "   文档:   http://localhost:8000/api/docs"
echo "   健康检查: http://localhost:8000/api/health"
echo ""
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
