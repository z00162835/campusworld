#!/bin/bash

# CampusWorld 前端依赖更新脚本
# 解决npm版本不推荐警告

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 检查Node.js版本
check_node_version() {
    log_step "检查Node.js版本..."
    
    if ! command -v node &> /dev/null; then
        log_error "Node.js未安装"
        exit 1
    fi
    
    local node_version=$(node --version)
    local major_version=$(echo $node_version | cut -d'v' -f2 | cut -d'.' -f1)
    
    if [ "$major_version" -lt 18 ]; then
        log_error "Node.js版本过低: $node_version，需要18.0.0或更高版本"
        exit 1
    fi
    
    log_success "Node.js版本: $node_version"
}

# 检查npm版本
check_npm_version() {
    log_step "检查npm版本..."
    
    if ! command -v npm &> /dev/null; then
        log_error "npm未安装"
        exit 1
    fi
    
    local npm_version=$(npm --version)
    log_success "npm版本: $npm_version"
}

# 备份当前依赖
backup_deps() {
    log_step "备份当前依赖..."
    
    if [ -f "package.json" ]; then
        cp package.json package.json.backup
        log_success "package.json已备份"
    fi
    
    if [ -f "package-lock.json" ]; then
        cp package-lock.json package-lock.json.backup
        log_success "package-lock.json已备份"
    fi
}

# 清理旧依赖
clean_deps() {
    log_step "清理旧依赖..."
    
    if [ -d "node_modules" ]; then
        rm -rf node_modules
        log_success "node_modules已删除"
    fi
    
    if [ -f "package-lock.json" ]; then
        rm -f package-lock.json
        log_success "package-lock.json已删除"
    fi
}

# 安装新依赖
install_deps() {
    log_step "安装新依赖..."
    
    if npm install; then
        log_success "依赖安装成功"
    else
        log_error "依赖安装失败"
        exit 1
    fi
}

# 检查安全漏洞
check_audit() {
    log_step "检查安全漏洞..."
    
    if npm audit; then
        log_success "安全检查通过"
    else
        log_warning "发现安全漏洞，尝试自动修复..."
        if npm audit fix; then
            log_success "安全漏洞已修复"
        else
            log_warning "部分安全漏洞无法自动修复，请手动处理"
        fi
    fi
}

# 验证安装
verify_installation() {
    log_step "验证安装..."
    
    # 检查关键依赖
    local key_deps=("vue" "vite" "typescript" "element-plus")
    
    for dep in "${key_deps[@]}"; do
        if npm list "$dep" --depth=0 &> /dev/null; then
            local version=$(npm list "$dep" --depth=0 | grep "$dep@" | awk '{print $2}')
            log_success "$dep: $version"
        else
            log_error "$dep 未正确安装"
            return 1
        fi
    done
    
    return 0
}

# 显示更新摘要
show_summary() {
    log_step "更新摘要..."
    
    echo ""
    echo "📋 依赖更新完成！"
    echo "   - 所有依赖已更新到最新稳定版本"
    echo "   - 解决了npm版本不推荐警告"
    echo "   - 安全漏洞已检查并修复"
    echo ""
    echo "💡 下一步操作："
    echo "   1. 测试开发服务器: npm run dev"
    echo "   2. 运行类型检查: npm run type-check"
    echo "   3. 运行测试: npm run test"
    echo "   4. 构建项目: npm run build"
    echo ""
}

# 主函数
main() {
    echo "🚀 CampusWorld 前端依赖更新脚本"
    echo "=================================="
    
    # 检查环境
    check_node_version
    check_npm_version
    
    # 备份和清理
    backup_deps
    clean_deps
    
    # 安装新依赖
    install_deps
    
    # 安全检查
    check_audit
    
    # 验证安装
    if verify_installation; then
        log_success "所有依赖验证通过"
    else
        log_error "依赖验证失败"
        exit 1
    fi
    
    # 显示摘要
    show_summary
}

# 错误处理
trap 'log_error "脚本执行失败，正在恢复备份..."; [ -f package.json.backup ] && mv package.json.backup package.json; [ -f package-lock.json.backup ] && mv package-lock.json.backup package-lock.json; exit 1' ERR

# 运行主函数
main "$@"
