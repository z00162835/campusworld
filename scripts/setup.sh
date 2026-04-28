#!/bin/bash

# CampusWorld 项目初始化脚本
# 此脚本用于设置开发环境和初始化项目

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取项目根目录（脚本所在目录的上级目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 全局变量
SKIP_DOCKER=false
SKIP_BACKEND=false
SKIP_FRONTEND=false
SKIP_DATABASE=false
VERBOSE=false

# 显示帮助信息
show_help() {
    echo "CampusWorld 项目初始化脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help           显示此帮助信息"
    echo "  --skip-docker        跳过Docker环境启动"
    echo "  --skip-backend       跳过后端依赖安装"
    echo "  --skip-frontend      跳过前端依赖安装"
    echo "  --skip-database      跳过数据库初始化"
    echo "  -v, --verbose        详细输出"
    echo ""
    echo "环境变量:"
    echo "  RESET_DB=1           仅本地：先危险 reset（DROP public）再 migrate；会设置 CAMPUSWORLD_ALLOW_DB_RESET=true"
    echo ""
    echo "示例:"
    echo "  $0                    # 完整初始化"
    echo "  $0 --skip-docker      # 跳过Docker启动"
    echo "  $0 --skip-frontend    # 跳过前端安装"
    echo ""
    echo "项目根目录: $PROJECT_ROOT"
    echo ""
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --skip-backend)
                SKIP_BACKEND=true
                shift
                ;;
            --skip-frontend)
                SKIP_FRONTEND=true
                shift
                ;;
            --skip-database)
                SKIP_DATABASE=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            *)
                echo -e "${RED}❌ 未知选项: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
}

# 日志函数
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo -e "${BLUE}🔧 $1${NC}"
}

# 检查项目结构
check_project_structure() {
    log_step "检查项目结构..."
    
    # 检查项目根目录
    if [ ! -d "$PROJECT_ROOT" ]; then
        log_error "项目根目录不存在: $PROJECT_ROOT"
        exit 1
    fi
    
    log_info "项目根目录: $PROJECT_ROOT"
    
    # 检查必要的目录结构
    local required_dirs=(
        "backend"
        "frontend"
        "scripts"
        "docs"
    )
    
    for dir in "${required_dirs[@]}"; do
        local full_path="$PROJECT_ROOT/$dir"
        if [ ! -d "$full_path" ]; then
            log_error "必要目录不存在: $dir"
            exit 1
        fi
        log_info "✓ 目录存在: $dir"
    done
    
    # 检查配置文件目录
    local config_dir="$PROJECT_ROOT/backend/config"
    if [ ! -d "$config_dir" ]; then
        log_error "后端配置目录不存在: $config_dir"
        exit 1
    fi
    log_info "✓ 配置目录存在: backend/config"
    
    log_success "项目结构检查通过"
}

# 检查必要的工具
check_requirements() {
    log_step "检查系统要求..."
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 未安装，请先安装 Python 3.9+"
        exit 1
    fi
    
    # 检查 Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js 未安装，请先安装 Node.js 18+"
        exit 1
    fi
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    # 检查 Docker Compose
    if ! command -v docker compose &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    log_success "系统要求检查通过"
}

# 创建和配置YAML配置文件
setup_yaml_configs() {
    log_step "设置YAML配置文件..."
    
    # 使用绝对路径检查配置文件目录
    local config_dir="$PROJECT_ROOT/backend/config"
    
    # 检查配置文件目录
    if [ ! -d "$config_dir" ]; then
        log_error "后端配置目录不存在: $config_dir"
        exit 1
    fi
    
    # 检查基础配置文件
    local base_config="$config_dir/settings.yaml"
    if [ ! -f "$base_config" ]; then
        log_error "基础配置文件不存在: $base_config"
        exit 1
    fi
    
    # 检查开发环境配置文件
    local dev_config="$config_dir/settings.dev.yaml"
    if [ ! -f "$dev_config" ]; then
        log_error "开发环境配置文件不存在: $dev_config"
        exit 1
    fi
    
    log_success "YAML配置文件检查通过"
    
    # 创建配置备份
    log_step "创建配置文件备份..."
    
    # 备份基础配置文件
    local base_backup="$config_dir/settings.yaml.backup"
    if cp "$base_config" "$base_backup" 2>/dev/null; then
        log_success "基础配置文件备份完成: $base_backup"
    else
        log_warning "基础配置文件备份失败"
    fi
    
    # 备份开发环境配置文件
    local dev_backup="$config_dir/settings.dev.yaml.backup"
    if cp "$dev_config" "$dev_backup" 2>/dev/null; then
        log_success "开发环境配置文件备份完成: $dev_backup"
    else
        log_warning "开发环境配置文件备份失败"
    fi
}

# 创建环境变量文件（用于覆盖YAML配置）
create_env_files() {
    log_step "创建环境变量文件..."
    
    # 使用绝对路径
    local backend_env="$PROJECT_ROOT/backend/.env"
    local frontend_env="$PROJECT_ROOT/frontend/.env"
    local backend_example="$PROJECT_ROOT/backend/.env.example"
    local frontend_example="$PROJECT_ROOT/frontend/.env.example"
    
    # 后端环境变量文件
    if [ ! -f "$backend_env" ]; then
        cat > "$backend_env" << EOF
# CampusWorld Backend Environment Variables
# 这些变量会覆盖YAML配置文件中的相应设置

# 环境设置
ENVIRONMENT=development

# 安全配置
CAMPUSWORLD_SECURITY_SECRET_KEY=dev-secret-key-change-in-production

# 数据库配置
CAMPUSWORLD_DATABASE_HOST=localhost
CAMPUSWORLD_DATABASE_PORT=5433
CAMPUSWORLD_DATABASE_NAME=campusworld_dev
CAMPUSWORLD_DATABASE_USER=campusworld_dev_user
CAMPUSWORLD_DATABASE_PASSWORD=campusworld_dev_password

# Redis配置
CAMPUSWORLD_REDIS_HOST=localhost
CAMPUSWORLD_REDIS_PORT=6380

# 日志配置
CAMPUSWORLD_LOGGING_LEVEL=DEBUG
CAMPUSWORLD_LOGGING_CONSOLE_OUTPUT=true
CAMPUSWORLD_LOGGING_FILE_OUTPUT=false

# 开发配置
CAMPUSWORLD_DEVELOPMENT_ENABLE_DEBUG_TOOLBAR=true
CAMPUSWORLD_DEVELOPMENT_ENABLE_PROFILING=true
CAMPUSWORLD_DEVELOPMENT_MOCK_EXTERNAL_SERVICES=true
CAMPUSWORLD_DEVELOPMENT_SEED_DATA=true
EOF
        log_success "创建后端环境变量文件: $backend_env"
    else
        log_info "后端环境变量文件已存在，跳过创建: $backend_env"
    fi
    
    # 前端环境变量文件
    if [ ! -f "$frontend_env" ]; then
        cat > "$frontend_env" << EOF
# CampusWorld Frontend Environment Variables
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_TITLE=CampusWorld
VITE_APP_VERSION=0.1.0
VITE_APP_ENVIRONMENT=development
VITE_ENABLE_DEBUG=true
EOF
        log_success "创建前端环境变量文件: $frontend_env"
    else
        log_info "前端环境变量文件已存在，跳过创建: $frontend_env"
    fi
    
    # 创建环境变量示例文件
    if [ ! -f "$backend_example" ]; then
        cat > "$backend_example" << EOF
# CampusWorld Backend Environment Variables Example
# 复制此文件为 .env 并根据需要修改

# 环境设置
ENVIRONMENT=development

# 安全配置
CAMPUSWORLD_SECURITY_SECRET_KEY=your-secret-key-here

# 数据库配置
CAMPUSWORLD_DATABASE_HOST=localhost
CAMPUSWORLD_DATABASE_PORT=5432
CAMPUSWORLD_DATABASE_NAME=campusworld
CAMPUSWORLD_DATABASE_USER=campusworld_user
CAMPUSWORLD_DATABASE_PASSWORD=campusworld_password

# Redis配置
CAMPUSWORLD_REDIS_HOST=localhost
CAMPUSWORLD_REDIS_PORT=6379
CAMPUSWORLD_REDIS_PASSWORD=

# 日志配置
CAMPUSWORLD_LOGGING_LEVEL=INFO
CAMPUSWORLD_LOGGING_CONSOLE_OUTPUT=true
CAMPUSWORLD_LOGGING_FILE_OUTPUT=false

# 开发配置
CAMPUSWORLD_DEVELOPMENT_ENABLE_DEBUG_TOOLBAR=false
CAMPUSWORLD_DEVELOPMENT_ENABLE_PROFILING=false
CAMPUSWORLD_DEVELOPMENT_MOCK_EXTERNAL_SERVICES=false
CAMPUSWORLD_DEVELOPMENT_SEED_DATA=false
EOF
        log_success "创建后端环境变量示例文件: $backend_example"
    fi
    
    if [ ! -f "$frontend_example" ]; then
        cat > "$frontend_example" << EOF
# CampusWorld Frontend Environment Variables Example
# 复制此文件为 .env 并根据需要修改

VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_TITLE=CampusWorld
VITE_APP_VERSION=0.1.0
VITE_APP_ENVIRONMENT=development
VITE_ENABLE_DEBUG=true
EOF
        log_success "创建前端环境变量示例文件: $frontend_example"
    fi
}

# 验证配置文件
validate_configs() {
    log_step "验证配置文件..."
    
    # 切换到后端目录
    cd "$PROJECT_ROOT/backend/scripts"

    # 加载后端 .env（混合配置模式：YAML 为主，env 为覆盖）
    # 说明：
    # - setup.sh 运行在单独的 shell 进程中，如果不 source .env，子进程 python 将读不到变量
    # - 使用 set -a 自动 export，确保变量对子进程可见
    local backend_env="$PROJECT_ROOT/backend/.env"
    if [ -f "$backend_env" ]; then
        set -a
        # shellcheck disable=SC1090
        source "$backend_env"
        set +a
        log_info "已加载后端环境变量文件: $backend_env"
    else
        log_warning "后端环境变量文件不存在，跳过加载: $backend_env"
    fi

    # 检查Python环境
    if command -v conda &> /dev/null; then
        eval "$(conda shell.bash hook)"
        if conda env list | grep -q "campusworld"; then
            conda activate campusworld
            # 使用conda环境中的python
            PYTHON_CMD="python"
        else
            PYTHON_CMD="python3"
        fi
    else
        PYTHON_CMD="python3"
    fi
    
    # 使用专门的配置验证脚本
    if $PYTHON_CMD validate_config.py; then
        log_success "配置文件验证成功"
    else
        log_error "配置文件验证失败"
        exit 1
    fi
    
    # 返回项目根目录
    cd "$PROJECT_ROOT"
}

# 启动开发环境
start_dev_environment() {
    if [ "$SKIP_DOCKER" = true ]; then
        log_info "跳过Docker环境启动"
        return 0
    fi
    
    log_step "启动开发环境..."
    
    # 检查Docker服务状态
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker服务未运行，请启动Docker"
        exit 1
    fi
    
    # 使用绝对路径的docker-compose文件
    local docker_compose_file="$PROJECT_ROOT/docker-compose.dev.yml"
    if [ ! -f "$docker_compose_file" ]; then
        log_error "Docker Compose文件不存在: $docker_compose_file"
        exit 1
    fi
    
    # 启动数据库和缓存服务
    log_info "启动PostgreSQL、Redis和Adminer服务..."
    if docker compose -f "$docker_compose_file" up -d; then
        log_success "Docker服务启动成功"
    else
        log_error "Docker服务启动失败"
        exit 1
    fi
    
    log_info "等待服务启动..."
    sleep 15
    
    # 检查服务状态
    log_step "检查服务状态..."
    if docker compose -f "$docker_compose_file" ps | grep -q "Up"; then
        log_success "开发环境启动完成"
    else
        log_error "开发环境启动失败"
        exit 1
    fi
}

# 安装后端依赖
install_backend_deps() {
    if [ "$SKIP_BACKEND" = true ]; then
        log_info "跳过后端依赖安装"
        return 0
    fi
    
    log_step "安装后端依赖..."
    
    # 切换到后端目录
    cd "$PROJECT_ROOT/backend"
    
    # 检查 conda 是否安装
    if ! command -v conda &> /dev/null; then
        log_error "Miniconda 未安装，请先安装 Miniconda"
        log_info "下载地址: https://docs.conda.io/en/latest/miniconda.html"
        exit 1
    fi
    
    # 检查environment.yml文件
    local env_file="$PROJECT_ROOT/backend/environment.yml"
    if [ ! -f "$env_file" ]; then
        log_error "environment.yml文件不存在: $env_file"
        exit 1
    fi
    
    # 创建 conda 环境
    if ! conda env list | grep -q "campusworld"; then
        log_info "从 environment.yml 创建 Conda 环境..."
        if conda env create -f "$env_file"; then
            log_success "创建 Conda 环境: campusworld"
        else
            log_error "创建 Conda 环境失败"
            exit 1
        fi
    else
        log_info "更新现有 Conda 环境..."
        if conda env update -f "$env_file"; then
            log_success "更新 Conda 环境: campusworld"
        else
            log_warning "更新 Conda 环境失败，继续使用现有环境"
        fi
    fi
    
    # 激活 conda 环境并安装依赖
    eval "$(conda shell.bash hook)"
    conda activate campusworld
    
    log_info "升级pip..."
    if pip install --upgrade pip; then
        log_success "pip升级成功"
    else
        log_warning "pip升级失败，继续安装依赖"
    fi
    
    # 检查requirements文件
    local req_file="$PROJECT_ROOT/backend/requirements/dev.txt"
    if [ ! -f "$req_file" ]; then
        log_error "requirements文件不存在: $req_file"
        exit 1
    fi
    
    log_info "安装Python依赖..."
    if pip install -r "$req_file"; then
        log_success "Python依赖安装成功"
    else
        log_error "Python依赖安装失败"
        exit 1
    fi
    
    # 返回项目根目录
    cd "$PROJECT_ROOT"
    log_success "后端依赖安装完成"
}

# 安装前端依赖
install_frontend_deps() {
    if [ "$SKIP_FRONTEND" = true ]; then
        log_info "跳过前端依赖安装"
        return 0
    fi
    
    log_step "安装前端依赖..."
    
    # 切换到前端目录
    cd "$PROJECT_ROOT/frontend"
    
    # 检查package.json是否存在
    local package_file="$PROJECT_ROOT/frontend/package.json"
    if [ ! -f "$package_file" ]; then
        log_error "package.json 文件不存在: $package_file"
        exit 1
    fi
    
    # 安装依赖
    log_info "安装npm依赖..."
    if npm install; then
        log_success "npm依赖安装成功"
    else
        log_error "npm依赖安装失败"
        exit 1
    fi
    
    # 返回项目根目录
    cd "$PROJECT_ROOT"
    log_success "前端依赖安装完成"
}

# 初始化数据库
init_database() {
    if [ "$SKIP_DATABASE" = true ]; then
        log_info "跳过数据库初始化"
        return 0
    fi
    
    log_step "初始化数据库..."
    
    # 切换到后端目录
    cd "$PROJECT_ROOT/backend"
    
    # 激活 conda 环境
    eval "$(conda shell.bash hook)"
    conda activate campusworld
    
    # 运行数据库迁移（RESET_DB=1 时先 PostgreSQL public 危险重建，见 --help）
    log_info "运行数据库迁移..."
    if [ "${RESET_DB:-}" = "1" ]; then
        log_warning "RESET_DB=1：将执行 reset（DROP SCHEMA public CASCADE），仅用于本地开发"
        export CAMPUSWORLD_ALLOW_DB_RESET=true
        if python -m db.init_database reset --i-understand; then
            log_success "数据库初始化成功（已 reset）"
        else
            log_error "数据库初始化失败"
            exit 1
        fi
    elif python -m db.init_database; then
        log_success "数据库初始化成功"
    else
        log_error "数据库初始化失败"
        exit 1
    fi
    
    # 返回项目根目录
    cd "$PROJECT_ROOT"
}

# 创建日志目录
setup_logging() {
    log_step "设置日志目录..."
    
    # 使用绝对路径
    local backend_logs="$PROJECT_ROOT/backend/logs"
    local frontend_logs="$PROJECT_ROOT/frontend/logs"
    
    # 创建后端日志目录
    if [ ! -d "$backend_logs" ]; then
        if mkdir -p "$backend_logs"; then
            log_success "创建后端日志目录: $backend_logs"
        else
            log_warning "创建后端日志目录失败"
        fi
    else
        log_info "后端日志目录已存在: $backend_logs"
    fi
    
    # 创建前端日志目录
    if [ ! -d "$frontend_logs" ]; then
        if mkdir -p "$frontend_logs"; then
            log_success "创建前端日志目录: $frontend_logs"
        else
            log_warning "创建前端日志目录失败"
        fi
    else
        log_info "前端日志目录已存在: $frontend_logs"
    fi
    
    # 设置日志文件权限
    local backend_log_file="$backend_logs/campusworld.log"
    if touch "$backend_log_file" 2>/dev/null; then
        chmod 644 "$backend_log_file" 2>/dev/null || true
        log_success "后端日志文件设置完成: $backend_log_file"
    else
        log_warning "后端日志文件设置失败"
    fi
    
    local frontend_log_file="$frontend_logs/frontend.log"
    if touch "$frontend_log_file" 2>/dev/null; then
        chmod 644 "$frontend_log_file" 2>/dev/null || true
        log_success "前端日志文件设置完成: $frontend_log_file"
    else
        log_warning "前端日志文件设置失败"
    fi
    
    log_success "日志目录设置完成"
}

# 显示启动说明
show_startup_instructions() {
    echo ""
    echo -e "${GREEN}🎉 CampusWorld 项目初始化完成！${NC}"
    echo ""
    echo -e "${BLUE}📁 项目信息：${NC}"
    echo "项目根目录: $PROJECT_ROOT"
    echo "脚本目录: $SCRIPT_DIR"
    echo ""
    echo -e "${BLUE}📖 启动说明：${NC}"
    echo "1. 启动后端服务："
    echo "   cd $PROJECT_ROOT/backend && conda activate campusworld && python campusworld.py"
    echo ""
    echo "2. 启动前端服务："
    echo "   cd $PROJECT_ROOT/frontend && npm run dev"
    echo ""
    echo "3. 访问应用："
    echo "   - 前端: http://localhost:3000"
    echo "   - 后端 API: http://localhost:8000"
    echo "   - API 文档: http://localhost:8000/api/v1/docs"
    echo "   - 数据库管理: http://localhost:8080"
    echo ""
    echo -e "${BLUE}🔧 开发工具：${NC}"
    echo "   - 代码格式化: cd $PROJECT_ROOT/backend && conda activate campusworld && black app tests"
    echo "   - 代码检查: cd $PROJECT_ROOT/backend && conda activate campusworld && flake8 app tests"
    echo "   - 类型检查: cd $PROJECT_ROOT/backend && conda activate campusworld && mypy app"
    echo "   - 运行测试: cd $PROJECT_ROOT/backend && conda activate campusworld && pytest"
    echo "   - 配置验证: cd $PROJECT_ROOT/backend && python scripts/validate_config.py"
    echo ""
    echo -e "${BLUE}📚 更多信息请查看 docs/ 目录下的文档${NC}"
    echo ""
    echo -e "${BLUE}🔧 配置文件说明：${NC}"
    echo "   - 后端配置: $PROJECT_ROOT/backend/config/settings.yaml (基础配置)"
    echo "   - 环境配置: $PROJECT_ROOT/backend/config/settings.dev.yaml (开发环境)"
    echo "   - 环境变量: $PROJECT_ROOT/backend/.env (覆盖YAML配置)"
    echo "   - 前端配置: $PROJECT_ROOT/frontend/.env (前端环境变量)"
    echo ""
    echo -e "${BLUE}🛠️  配置管理工具：${NC}"
    echo "   - 配置管理: $PROJECT_ROOT/scripts/manage_config.sh"
    echo "   - 模板生成: $PROJECT_ROOT/scripts/generate_env_template.sh"
}

# 显示跳过信息
show_skip_info() {
    if [ "$SKIP_DOCKER" = true ] || [ "$SKIP_BACKEND" = true ] || [ "$SKIP_FRONTEND" = true ] || [ "$SKIP_DATABASE" = true ]; then
        echo ""
        echo -e "${YELLOW}⚠️  跳过的步骤：${NC}"
        [ "$SKIP_DOCKER" = true ] && echo "  - Docker环境启动"
        [ "$SKIP_BACKEND" = true ] && echo "  - 后端依赖安装"
        [ "$SKIP_FRONTEND" = true ] && echo "  - 前端依赖安装"
        [ "$SKIP_DATABASE" = true ] && echo "  - 数据库初始化"
        echo ""
    fi
}

# 主函数
main() {
    echo -e "${BLUE}🚀 开始初始化 CampusWorld 项目...${NC}"
    echo -e "${BLUE}📁 项目根目录: $PROJECT_ROOT${NC}"
    echo -e "${BLUE}📁 脚本目录: $SCRIPT_DIR${NC}"
    echo ""
    
    # 解析命令行参数
    parse_args "$@"
    
    # 显示跳过信息
    show_skip_info
    
    # 执行初始化步骤
    check_project_structure
    check_requirements
    setup_yaml_configs
    create_env_files
    setup_logging
    start_dev_environment
    install_backend_deps
    install_frontend_deps
    validate_configs
    init_database
    show_startup_instructions
}

# 运行主函数
main "$@"
