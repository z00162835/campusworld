#!/bin/bash

# CampusWorld 项目初始化脚本
# 此脚本用于设置开发环境和初始化项目

set -e

echo "🚀 开始初始化 CampusWorld 项目..."

# 检查必要的工具
check_requirements() {
    echo "📋 检查系统要求..."
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 未安装，请先安装 Python 3.9+"
        exit 1
    fi
    
    # 检查 Node.js
    if ! command -v node &> /dev/null; then
        echo "❌ Node.js 未安装，请先安装 Node.js 18+"
        exit 1
    fi
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    # 检查 Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    echo "✅ 系统要求检查通过"
}

# 创建环境配置文件
create_env_files() {
    echo "🔧 创建环境配置文件..."
    
    # 后端环境配置
    if [ ! -f "backend/.env" ]; then
        cat > backend/.env << EOF
# CampusWorld Backend Environment Configuration
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=your-secret-key-here-change-in-production
DATABASE_URL=postgresql://campusworld_dev_user:campusworld_dev_password@localhost:5433/campusworld_dev
REDIS_URL=redis://localhost:6380
LOG_LEVEL=DEBUG
EOF
        echo "✅ 创建后端环境配置文件"
    fi
    
    # 前端环境配置
    if [ ! -f "frontend/.env" ]; then
        cat > frontend/.env << EOF
# CampusWorld Frontend Environment Configuration
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_TITLE=CampusWorld
VITE_APP_VERSION=0.1.0
EOF
        echo "✅ 创建前端环境配置文件"
    fi
}

# 启动开发环境
start_dev_environment() {
    echo "🐳 启动开发环境..."
    
    # 启动数据库和缓存服务
    docker-compose -f docker-compose.dev.yml up -d
    
    echo "⏳ 等待服务启动..."
    sleep 10
    
    echo "✅ 开发环境启动完成"
}

# 安装后端依赖
install_backend_deps() {
    echo "🐍 安装后端依赖..."
    
    cd backend
    
    # 创建虚拟环境
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo "✅ 创建 Python 虚拟环境"
    fi
    
    # 激活虚拟环境并安装依赖
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements/dev.txt
    
    cd ..
    echo "✅ 后端依赖安装完成"
}

# 安装前端依赖
install_frontend_deps() {
    echo "📦 安装前端依赖..."
    
    cd frontend
    npm install
    cd ..
    
    echo "✅ 前端依赖安装完成"
}

# 初始化数据库
init_database() {
    echo "🗄️ 初始化数据库..."
    
    cd backend
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 运行数据库迁移
    python -c "
from app.core.database import init_db
from app.core.config import settings
print('初始化数据库...')
init_db()
print('数据库初始化完成')
"
    
    cd ..
    echo "✅ 数据库初始化完成"
}

# 显示启动说明
show_startup_instructions() {
    echo ""
    echo "🎉 CampusWorld 项目初始化完成！"
    echo ""
    echo "📖 启动说明："
    echo "1. 启动后端服务："
    echo "   cd backend && source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    echo ""
    echo "2. 启动前端服务："
    echo "   cd frontend && npm run dev"
    echo ""
    echo "3. 访问应用："
    echo "   - 前端: http://localhost:3000"
    echo "   - 后端 API: http://localhost:8000"
    echo "   - API 文档: http://localhost:8000/api/v1/docs"
    echo "   - 数据库管理: http://localhost:8080"
    echo ""
    echo "🔧 开发工具："
    echo "   - 代码格式化: cd backend && black app tests"
    echo "   - 代码检查: cd backend && flake8 app tests"
    echo "   - 类型检查: cd backend && mypy app"
    echo "   - 运行测试: cd backend && pytest"
    echo ""
    echo "📚 更多信息请查看 docs/ 目录下的文档"
}

# 主函数
main() {
    check_requirements
    create_env_files
    start_dev_environment
    install_backend_deps
    install_frontend_deps
    init_database
    show_startup_instructions
}

# 运行主函数
main
