#!/bin/bash

# CampusWorld 配置管理脚本
# 用于管理不同环境的配置文件和环境变量

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_CONFIG_DIR="$PROJECT_ROOT/backend/config"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# 显示帮助信息
show_help() {
    echo "CampusWorld 配置管理脚本"
    echo ""
    echo "用法: $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  list                   列出所有配置文件"
    echo "  validate              验证配置文件"
    echo "  backup                备份配置文件"
    echo "  restore              恢复配置文件"
    echo "  switch-env <env>     切换到指定环境 (dev/test/prod)"
    echo "  create-env <env>     创建新环境配置"
    echo "  diff-env <env1> <env2> 比较两个环境的配置差异"
    echo "  update-env           更新环境变量文件"
    echo "  clean                清理临时配置文件"
    echo ""
    echo "选项:"
    echo "  -h, --help           显示此帮助信息"
    echo "  -v, --verbose        详细输出"
    echo ""
    echo "环境:"
    echo "  dev                  开发环境"
    echo "  test                 测试环境"
    echo "  prod                 生产环境"
    echo ""
    echo "示例:"
    echo "  $0 list                    # 列出所有配置"
    echo "  $0 validate                # 验证配置"
    echo "  $0 switch-env prod         # 切换到生产环境"
    echo "  $0 create-env staging      # 创建staging环境"
}

# 检查配置文件是否存在
check_config_files() {
    local env="$1"
    
    if [ ! -d "$BACKEND_CONFIG_DIR" ]; then
        echo -e "${RED}❌ 后端配置目录不存在: $BACKEND_CONFIG_DIR${NC}"
        return 1
    fi
    
    if [ ! -f "$BACKEND_CONFIG_DIR/settings.yaml" ]; then
        echo -e "${RED}❌ 基础配置文件不存在: $BACKEND_CONFIG_DIR/settings.yaml${NC}"
        return 1
    fi
    
    if [ -n "$env" ] && [ ! -f "$BACKEND_CONFIG_DIR/settings.$env.yaml" ]; then
        echo -e "${RED}❌ 环境配置文件不存在: $BACKEND_CONFIG_DIR/settings.$env.yaml${NC}"
        return 1
    fi
    
    return 0
}

# 列出所有配置文件
list_configs() {
    echo -e "${BLUE}📋 配置文件列表:${NC}"
    echo ""
    
    # 后端配置文件
    echo -e "${YELLOW}后端配置:${NC}"
    if [ -d "$BACKEND_CONFIG_DIR" ]; then
        for file in "$BACKEND_CONFIG_DIR"/*.yaml; do
            if [ -f "$file" ]; then
                local filename=$(basename "$file")
                local size=$(du -h "$file" | cut -f1)
                local modified=$(stat -f "%Sm" "$file" 2>/dev/null || stat -c "%y" "$file" 2>/dev/null)
                echo "  📄 $filename ($size, 修改: $modified)"
            fi
        done
    else
        echo "  ❌ 配置目录不存在"
    fi
    
    echo ""
    
    # 环境变量文件
    echo -e "${YELLOW}环境变量文件:${NC}"
    for dir in "$BACKEND_DIR" "$FRONTEND_DIR"; do
        if [ -d "$dir" ]; then
            local dirname=$(basename "$dir")
            echo "  📁 $dirname:"
            if [ -f "$dir/.env" ]; then
                local size=$(du -h "$dir/.env" | cut -f1)
                echo "    📄 .env ($size)"
            fi
            if [ -f "$dir/.env.example" ]; then
                local size=$(du -h "$dir/.env.example" | cut -f1)
                echo "    📄 .env.example ($size)"
            fi
        fi
    done
    
    echo ""
    
    # 当前环境
    local current_env=$(grep -E "^ENVIRONMENT=" "$BACKEND_DIR/.env" 2>/dev/null | cut -d'=' -f2 || echo "未设置")
    echo -e "${YELLOW}当前环境:${NC} $current_env"
}

# 验证配置文件
validate_configs() {
    echo -e "${BLUE}🔍 验证配置文件...${NC}"
    
    if ! check_config_files; then
        return 1
    fi
    
    cd "$BACKEND_DIR"
    
    # 检查Python环境
    if command -v conda &> /dev/null; then
        eval "$(conda shell.bash hook)"
        if conda env list | grep -q "campusworld"; then
            conda activate campusworld
        fi
    fi
    
    # 运行配置验证
    if python3 -c "
try:
    from app.core.config_manager import ConfigManager
    from app.core.settings import create_settings_from_config
    print('✅ 配置模块导入成功')
    
    # 测试配置加载
    config_manager = ConfigManager('config')
    if config_manager.validate():
        print('✅ 配置验证通过')
        
        # 测试Pydantic模型创建
        settings = create_settings_from_config(config_manager)
        print('✅ Pydantic模型创建成功')
        
        # 显示关键配置
        print(f'应用名称: {config_manager.get(\"app.name\")}')
        print(f'运行环境: {config_manager.get(\"app.environment\")}')
        print(f'数据库主机: {config_manager.get(\"database.host\")}')
        print(f'Redis主机: {config_manager.get(\"redis.host\")}')
        
        return True
    else:
        print('❌ 配置验证失败')
        return False
        
except Exception as e:
    print(f'❌ 配置验证失败: {e}')
    return False
"; then
        echo -e "${GREEN}✅ 配置文件验证成功${NC}"
        return 0
    else
        echo -e "${RED}❌ 配置文件验证失败${NC}"
        return 1
    fi
}

# 备份配置文件
backup_configs() {
    echo -e "${BLUE}📦 备份配置文件...${NC}"
    
    local backup_dir="$PROJECT_ROOT/config_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    # 备份YAML配置文件
    if [ -d "$BACKEND_CONFIG_DIR" ]; then
        cp -r "$BACKEND_CONFIG_DIR" "$backup_dir/"
        echo -e "${GREEN}✅ YAML配置文件已备份到: $backup_dir${NC}"
    fi
    
    # 备份环境变量文件
    for dir in "$BACKEND_DIR" "$FRONTEND_DIR"; do
        if [ -d "$dir" ]; then
            local dirname=$(basename "$dir")
            mkdir -p "$backup_dir/$dirname"
            if [ -f "$dir/.env" ]; then
                cp "$dir/.env" "$backup_dir/$dirname/"
            fi
            if [ -f "$dir/.env.example" ]; then
                cp "$dir/.env.example" "$backup_dir/$dirname/"
            fi
        fi
    done
    
    echo -e "${GREEN}✅ 配置文件备份完成: $backup_dir${NC}"
}

# 恢复配置文件
restore_configs() {
    local backup_dir="$1"
    
    if [ -z "$backup_dir" ]; then
        echo -e "${RED}❌ 请指定备份目录${NC}"
        echo "用法: $0 restore <backup_directory>"
        return 1
    fi
    
    if [ ! -d "$backup_dir" ]; then
        echo -e "${RED}❌ 备份目录不存在: $backup_dir${NC}"
        return 1
    fi
    
    echo -e "${BLUE}🔄 恢复配置文件...${NC}"
    
    # 恢复YAML配置文件
    if [ -d "$backup_dir/config" ]; then
        cp -r "$backup_dir/config"/* "$BACKEND_CONFIG_DIR/"
        echo -e "${GREEN}✅ YAML配置文件已恢复${NC}"
    fi
    
    # 恢复环境变量文件
    for dir in "$BACKEND_DIR" "$FRONTEND_DIR"; do
        if [ -d "$dir" ]; then
            local dirname=$(basename "$dir")
            if [ -d "$backup_dir/$dirname" ]; then
                if [ -f "$backup_dir/$dirname/.env" ]; then
                    cp "$backup_dir/$dirname/.env" "$dir/"
                fi
                if [ -f "$backup_dir/$dirname/.env.example" ]; then
                    cp "$backup_dir/$dirname/.env.example" "$dir/"
                fi
            fi
        fi
    done
    
    echo -e "${GREEN}✅ 配置文件恢复完成${NC}"
}

# 切换环境
switch_env() {
    local target_env="$1"
    
    if [ -z "$target_env" ]; then
        echo -e "${RED}❌ 请指定目标环境${NC}"
        echo "用法: $0 switch-env <environment>"
        return 1
    fi
    
    if ! check_config_files "$target_env"; then
        return 1
    fi
    
    echo -e "${BLUE}🔄 切换到 $target_env 环境...${NC}"
    
    # 更新后端环境变量
    if [ -f "$BACKEND_DIR/.env" ]; then
        sed -i.bak "s/^ENVIRONMENT=.*/ENVIRONMENT=$target_env/" "$BACKEND_DIR/.env"
        echo -e "${GREEN}✅ 后端环境已切换到: $target_env${NC}"
    fi
    
    # 更新前端环境变量
    if [ -f "$FRONTEND_DIR/.env" ]; then
        sed -i.bak "s/^VITE_APP_ENVIRONMENT=.*/VITE_APP_ENVIRONMENT=$target_env/" "$FRONTEND_DIR/.env"
        echo -e "${GREEN}✅ 前端环境已切换到: $target_env${NC}"
    fi
    
    echo -e "${GREEN}✅ 环境切换完成${NC}"
}

# 创建新环境配置
create_env() {
    local env_name="$1"
    
    if [ -z "$env_name" ]; then
        echo -e "${RED}❌ 请指定环境名称${NC}"
        echo "用法: $0 create-env <environment_name>"
        return 1
    fi
    
    if [ -f "$BACKEND_CONFIG_DIR/settings.$env_name.yaml" ]; then
        echo -e "${YELLOW}⚠️  环境配置文件已存在: settings.$env_name.yaml${NC}"
        return 1
    fi
    
    echo -e "${BLUE}📝 创建新环境配置: $env_name${NC}"
    
    # 基于开发环境配置创建新环境
    if [ -f "$BACKEND_CONFIG_DIR/settings.dev.yaml" ]; then
        cp "$BACKEND_CONFIG_DIR/settings.dev.yaml" "$BACKEND_CONFIG_DIR/settings.$env_name.yaml"
        
        # 修改环境名称
        sed -i "s/environment: \"development\"/environment: \"$env_name\"/" "$BACKEND_CONFIG_DIR/settings.$env_name.yaml"
        
        echo -e "${GREEN}✅ 环境配置文件已创建: settings.$env_name.yaml${NC}"
    else
        echo -e "${RED}❌ 开发环境配置文件不存在，无法创建新环境${NC}"
        return 1
    fi
}

# 比较环境配置差异
diff_env() {
    local env1="$1"
    local env2="$2"
    
    if [ -z "$env1" ] || [ -z "$env2" ]; then
        echo -e "${RED}❌ 请指定两个环境进行比较${NC}"
        echo "用法: $0 diff-env <env1> <env2>"
        return 1
    fi
    
    if ! check_config_files "$env1" || ! check_config_files "$env2"; then
        return 1
    fi
    
    echo -e "${BLUE}🔍 比较环境配置: $env1 vs $env2${NC}"
    
    # 使用diff命令比较配置文件
    if command -v diff &> /dev/null; then
        diff -u "$BACKEND_CONFIG_DIR/settings.$env1.yaml" "$BACKEND_CONFIG_DIR/settings.$env2.yaml" || true
    else
        echo -e "${YELLOW}⚠️  diff命令不可用，无法比较配置文件${NC}"
    fi
}

# 更新环境变量文件
update_env() {
    echo -e "${BLUE}🔄 更新环境变量文件...${NC}"
    
    # 更新后端环境变量示例文件
    if [ -f "$BACKEND_DIR/.env.example" ]; then
        echo -e "${GREEN}✅ 后端环境变量示例文件已存在${NC}"
    else
        echo -e "${YELLOW}⚠️  后端环境变量示例文件不存在，请运行 setup.sh 创建${NC}"
    fi
    
    # 更新前端环境变量示例文件
    if [ -f "$FRONTEND_DIR/.env.example" ]; then
        echo -e "${GREEN}✅ 前端环境变量示例文件已存在${NC}"
    else
        echo -e "${YELLOW}⚠️  前端环境变量示例文件不存在，请运行 setup.sh 创建${NC}"
    fi
    
    echo -e "${GREEN}✅ 环境变量文件更新完成${NC}"
}

# 清理临时配置文件
clean_configs() {
    echo -e "${BLUE}🧹 清理临时配置文件...${NC}"
    
    # 清理备份文件
    find "$PROJECT_ROOT" -name "*.bak" -type f -delete 2>/dev/null || true
    echo -e "${GREEN}✅ 已清理 .bak 备份文件${NC}"
    
    # 清理临时配置文件
    find "$PROJECT_ROOT" -name "*.tmp" -type f -delete 2>/dev/null || true
    echo -e "${GREEN}✅ 已清理 .tmp 临时文件${NC}"
    
    # 清理配置备份目录（保留最近3个）
    if [ -d "$PROJECT_ROOT" ]; then
        local backup_dirs=($(find "$PROJECT_ROOT" -maxdepth 1 -name "config_backup_*" -type d | sort -r))
        if [ ${#backup_dirs[@]} -gt 3 ]; then
            for dir in "${backup_dirs[@]:3}"; do
                rm -rf "$dir"
                echo -e "${GREEN}✅ 已清理旧备份目录: $(basename "$dir")${NC}"
            done
        fi
    fi
    
    echo -e "${GREEN}✅ 清理完成${NC}"
}

# 主函数
main() {
    local command="$1"
    shift
    
    case "$command" in
        "list")
            list_configs
            ;;
        "validate")
            validate_configs
            ;;
        "backup")
            backup_configs
            ;;
        "restore")
            restore_configs "$1"
            ;;
        "switch-env")
            switch_env "$1"
            ;;
        "create-env")
            create_env "$1"
            ;;
        "diff-env")
            diff_env "$1" "$2"
            ;;
        "update-env")
            update_env
            ;;
        "clean")
            clean_configs
            ;;
        "-h"|"--help"|"help"|"")
            show_help
            ;;
        *)
            echo -e "${RED}❌ 未知命令: $command${NC}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"
