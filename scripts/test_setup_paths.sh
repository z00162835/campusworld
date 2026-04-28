#!/bin/bash

# CampusWorld setup.sh 路径测试脚本
# 用于测试setup.sh脚本的路径设置是否正确

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

echo -e "${BLUE}🧪 测试 CampusWorld setup.sh 路径设置${NC}"
echo ""

# 检查脚本是否存在
if [ ! -f "$SETUP_SCRIPT" ]; then
    echo -e "${RED}❌ setup.sh 脚本不存在: $SETUP_SCRIPT${NC}"
    exit 1
fi

echo -e "${GREEN}✅ setup.sh 脚本存在: $SETUP_SCRIPT${NC}"

# 测试项目根目录设置
echo ""
echo -e "${BLUE}📁 测试项目根目录设置...${NC}"

# 提取PROJECT_ROOT变量值
PROJECT_ROOT_FROM_SCRIPT=$(grep "^PROJECT_ROOT=" "$SETUP_SCRIPT" | cut -d'"' -f2)

if [ -n "$PROJECT_ROOT_FROM_SCRIPT" ]; then
    echo -e "${GREEN}✅ PROJECT_ROOT 已设置: $PROJECT_ROOT_FROM_SCRIPT${NC}"
    
    # 检查路径是否正确
    if [ "$PROJECT_ROOT_FROM_SCRIPT" = "$PROJECT_ROOT" ]; then
        echo -e "${GREEN}✅ PROJECT_ROOT 路径正确${NC}"
    else
        echo -e "${YELLOW}⚠️  PROJECT_ROOT 路径可能不正确${NC}"
        echo "  脚本中的路径: $PROJECT_ROOT_FROM_SCRIPT"
        echo "  实际项目路径: $PROJECT_ROOT"
    fi
else
    echo -e "${RED}❌ PROJECT_ROOT 未设置${NC}"
fi

# 测试脚本目录设置
echo ""
echo -e "${BLUE}📁 测试脚本目录设置...${NC}"

SCRIPT_DIR_FROM_SCRIPT=$(grep "^SCRIPT_DIR=" "$SETUP_SCRIPT" | cut -d'"' -f2)

if [ -n "$SCRIPT_DIR_FROM_SCRIPT" ]; then
    echo -e "${GREEN}✅ SCRIPT_DIR 已设置: $SCRIPT_DIR_FROM_SCRIPT${NC}"
    
    # 检查路径是否正确
    if [ "$SCRIPT_DIR_FROM_SCRIPT" = "$PROJECT_ROOT/scripts" ]; then
        echo -e "${GREEN}✅ SCRIPT_DIR 路径正确${NC}"
    else
        echo -e "${YELLOW}⚠️  SCRIPT_DIR 路径可能不正确${NC}"
        echo "  脚本中的路径: $SCRIPT_DIR_FROM_SCRIPT"
        echo "  预期脚本路径: $PROJECT_ROOT/scripts"
    fi
else
    echo -e "${RED}❌ SCRIPT_DIR 未设置${NC}"
fi

# 测试配置文件路径
echo ""
echo -e "${BLUE}🔧 测试配置文件路径...${NC}"

# 检查是否使用了绝对路径
if grep -q "\$PROJECT_ROOT/backend/config" "$SETUP_SCRIPT"; then
    echo -e "${GREEN}✅ 后端配置目录使用绝对路径${NC}"
else
    echo -e "${RED}❌ 后端配置目录未使用绝对路径${NC}"
fi

if grep -q "\$PROJECT_ROOT/backend/.env" "$SETUP_SCRIPT"; then
    echo -e "${GREEN}✅ 后端环境变量文件使用绝对路径${NC}"
else
    echo -e "${RED}❌ 后端环境变量文件未使用绝对路径${NC}"
fi

if grep -q "\$PROJECT_ROOT/frontend/.env" "$SETUP_SCRIPT"; then
    echo -e "${GREEN}✅ 前端环境变量文件使用绝对路径${NC}"
else
    echo -e "${RED}❌ 前端环境变量文件未使用绝对路径${NC}"
fi

# 测试Docker Compose文件路径
echo ""
echo -e "${BLUE}🐳 测试Docker Compose文件路径...${NC}"

if grep -q "\$PROJECT_ROOT/docker-compose.dev.yml" "$SETUP_SCRIPT"; then
    echo -e "${GREEN}✅ Docker Compose文件使用绝对路径${NC}"
else
    echo -e "${RED}❌ Docker Compose文件未使用绝对路径${NC}"
fi

# 测试requirements文件路径
echo ""
echo -e "${BLUE}📦 测试requirements文件路径...${NC}"

if grep -q "\$PROJECT_ROOT/backend/requirements/dev.txt" "$SETUP_SCRIPT"; then
    echo -e "${GREEN}✅ requirements文件使用绝对路径${NC}"
else
    echo -e "${RED}❌ requirements文件未使用绝对路径${NC}"
fi

# 测试environment.yml文件路径
if grep -q "\$PROJECT_ROOT/backend/environment.yml" "$SETUP_SCRIPT"; then
    echo -e "${GREEN}✅ environment.yml文件使用绝对路径${NC}"
else
    echo -e "${RED}❌ environment.yml文件未使用绝对路径${NC}"
fi

# 测试日志目录路径
echo ""
echo -e "${BLUE}📝 测试日志目录路径...${NC}"

if grep -q "\$PROJECT_ROOT/backend/logs" "$SETUP_SCRIPT"; then
    echo -e "${GREEN}✅ 后端日志目录使用绝对路径${NC}"
else
    echo -e "${RED}❌ 后端日志目录未使用绝对路径${NC}"
fi

if grep -q "\$PROJECT_ROOT/frontend/logs" "$SETUP_SCRIPT"; then
    echo -e "${GREEN}✅ 前端日志目录使用绝对路径${NC}"
else
    echo -e "${RED}❌ 前端日志目录未使用绝对路径${NC}"
fi

# 测试项目结构检查函数
echo ""
echo -e "${BLUE}🏗️  测试项目结构检查函数...${NC}"

if grep -q "check_project_structure" "$SETUP_SCRIPT"; then
    echo -e "${GREEN}✅ 项目结构检查函数存在${NC}"
else
    echo -e "${RED}❌ 项目结构检查函数不存在${NC}"
fi

# 测试主函数调用
echo ""
echo -e "${BLUE}🚀 测试主函数调用...${NC}"

if grep -q "check_project_structure" "$SETUP_SCRIPT" | grep -A 20 "main()"; then
    echo -e "${GREEN}✅ 主函数中调用了项目结构检查${NC}"
else
    echo -e "${YELLOW}⚠️  主函数中可能未调用项目结构检查${NC}"
fi

echo ""
echo -e "${BLUE}📊 测试完成${NC}"
echo ""
echo -e "${GREEN}✅ setup.sh 脚本路径设置检查完成${NC}"
echo ""
echo -e "${BLUE}💡 建议：${NC}"
echo "1. 确保所有文件路径都使用绝对路径"
echo "2. 验证PROJECT_ROOT和SCRIPT_DIR设置正确"
echo "3. 测试脚本在不同目录下的执行情况"
