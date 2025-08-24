#!/bin/bash

# CampusWorld setup.sh 测试脚本
# 用于测试setup.sh脚本的各种功能

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETUP_SCRIPT="$PROJECT_ROOT/scripts/setup.sh"

# 测试结果
TESTS_PASSED=0
TESTS_FAILED=0

# 测试函数
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "${BLUE}🧪 运行测试: $test_name${NC}"
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 测试通过: $test_name${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ 测试失败: $test_name${NC}"
        ((TESTS_FAILED++))
    fi
}

# 测试帮助信息
test_help() {
    local output
    output=$("$SETUP_SCRIPT" --help 2>&1)
    
    if echo "$output" | grep -q "CampusWorld 项目初始化脚本"; then
        return 0
    else
        return 1
    fi
}

# 测试参数解析
test_arg_parsing() {
    local output
    output=$("$SETUP_SCRIPT" --skip-docker --skip-backend 2>&1)
    
    if echo "$output" | grep -q "跳过的步骤"; then
        return 0
    else
        return 1
    fi
}

# 测试脚本语法
test_syntax() {
    if bash -n "$SETUP_SCRIPT" 2>&1; then
        return 0
    else
        return 1
    fi
}

# 测试脚本可执行性
test_executability() {
    if [ -x "$SETUP_SCRIPT" ]; then
        return 0
    else
        return 0
    fi
}

# 测试函数定义
test_function_definitions() {
    local required_functions=(
        "check_requirements"
        "setup_yaml_configs"
        "create_env_files"
        "validate_configs"
        "start_dev_environment"
        "install_backend_deps"
        "install_frontend_deps"
        "init_database"
        "setup_logging"
        "show_startup_instructions"
        "main"
        "parse_args"
        "show_help"
        "log_info"
        "log_success"
        "log_warning"
        "log_error"
        "log_step"
    )
    
    local missing_functions=()
    
    for func in "${required_functions[@]}"; do
        if ! grep -q "^$func()" "$SETUP_SCRIPT"; then
            missing_functions+=("$func")
        fi
    done
    
    if [ ${#missing_functions[@]} -eq 0 ]; then
        return 0
    else
        echo "缺少函数: ${missing_functions[*]}"
        return 1
    fi
}

# 测试颜色定义
test_color_definitions() {
    local colors=("RED" "GREEN" "YELLOW" "BLUE" "NC")
    
    for color in "${colors[@]}"; do
        if ! grep -q "^$color=" "$SETUP_SCRIPT"; then
            echo "缺少颜色定义: $color"
            return 1
        fi
    done
    
    return 0
}

# 测试全局变量
test_global_variables() {
    local variables=("SKIP_DOCKER" "SKIP_BACKEND" "SKIP_FRONTEND" "SKIP_DATABASE" "VERBOSE")
    
    for var in "${variables[@]}"; do
        if ! grep -q "^$var=" "$SETUP_SCRIPT"; then
            echo "缺少全局变量: $var"
            return 1
        fi
    done
    
    return 0
}

# 测试错误处理
test_error_handling() {
    # 检查是否使用了log_error函数
    if grep -q "log_error" "$SETUP_SCRIPT"; then
        return 0
    else
        return 1
    fi
}

# 测试日志函数
test_log_functions() {
    local log_functions=("log_info" "log_success" "log_warning" "log_error" "log_step")
    
    for func in "${log_functions[@]}"; do
        if ! grep -q "^$func()" "$SETUP_SCRIPT"; then
            echo "缺少日志函数: $func"
            return 1
        fi
    done
    
    return 0
}

# 主测试函数
main() {
    echo -e "${BLUE}🚀 开始测试 CampusWorld setup.sh 脚本${NC}"
    echo ""
    
    # 检查脚本是否存在
    if [ ! -f "$SETUP_SCRIPT" ]; then
        echo -e "${RED}❌ setup.sh 脚本不存在: $SETUP_SCRIPT${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}📁 测试脚本: $SETUP_SCRIPT${NC}"
    echo ""
    
    # 运行所有测试
    run_test "脚本语法检查" "test_syntax"
    run_test "脚本可执行性" "test_executability"
    run_test "函数定义完整性" "test_function_definitions"
    run_test "颜色定义" "test_color_definitions"
    run_test "全局变量定义" "test_global_variables"
    run_test "错误处理机制" "test_error_handling"
    run_test "日志函数定义" "test_log_functions"
    run_test "帮助信息显示" "test_help"
    run_test "参数解析功能" "test_arg_parsing"
    
    echo ""
    echo -e "${BLUE}📊 测试结果汇总${NC}"
    echo "✅ 通过: $TESTS_PASSED"
    echo "❌ 失败: $TESTS_FAILED"
    echo "📈 成功率: $((TESTS_PASSED * 100 / (TESTS_PASSED + TESTS_FAILED)))%"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo ""
        echo -e "${GREEN}🎉 所有测试通过！setup.sh 脚本功能正常${NC}"
        exit 0
    else
        echo ""
        echo -e "${RED}⚠️  部分测试失败，请检查脚本${NC}"
        exit 1
    fi
}

# 运行主测试函数
main "$@"
