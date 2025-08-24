#!/bin/bash

# CampusWorld 环境配置模板生成脚本
# 用于生成不同环境的配置模板

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
    echo "CampusWorld 环境配置模板生成脚本"
    echo ""
    echo "用法: $0 [命令] [选项]"
    echo ""
    echo "命令:"
    echo "  generate <env>        生成指定环境的配置模板"
    echo "  generate-all          生成所有环境的配置模板"
    echo "  update-templates      更新现有配置模板"
    echo "  validate-templates    验证配置模板"
    echo ""
    echo "选项:"
    echo "  -h, --help           显示此帮助信息"
    echo "  -f, --force          强制覆盖现有文件"
    echo ""
    echo "环境:"
    echo "  dev                  开发环境"
    echo "  test                 测试环境"
    echo "  staging              预发布环境"
    echo "  prod                 生产环境"
    echo ""
    echo "示例:"
    echo "  $0 generate prod      # 生成生产环境配置"
    echo "  $0 generate-all       # 生成所有环境配置"
    echo "  $0 update-templates   # 更新配置模板"
}

# 生成开发环境配置模板
generate_dev_template() {
    local force="$1"
    local file="$BACKEND_CONFIG_DIR/settings.dev.yaml"
    
    if [ -f "$file" ] && [ "$force" != "true" ]; then
        echo -e "${YELLOW}⚠️  开发环境配置文件已存在: $file${NC}"
        echo "使用 -f 选项强制覆盖"
        return 1
    fi
    
    echo -e "${BLUE}📝 生成开发环境配置模板...${NC}"
    
    cat > "$file" << 'EOF'
# CampusWorld 开发环境配置
# 继承自 settings.yaml 并覆盖开发特定设置

# 应用配置
app:
  environment: "development"
  debug: true

# 服务器配置
server:
  host: "0.0.0.0"
  port: 8000
  workers: 1
  reload: true
  access_log: true

# 数据库配置
database:
  host: "localhost"
  port: 5433
  name: "campusworld_dev"
  user: "campusworld_dev_user"
  password: "campusworld_dev_password"
  pool_size: 10
  max_overflow: 20
  pool_pre_ping: true
  pool_recycle: 300
  echo: true

# Redis配置
redis:
  host: "localhost"
  port: 6380
  password: ""
  db: 0
  pool_size: 10
  socket_timeout: 5
  socket_connect_timeout: 5

# 日志配置
logging:
  level: "DEBUG"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  date_format: "%Y-%m-%d %H:%M:%S"
  file_path: "logs/campusworld.log"
  max_file_size: "10MB"
  backup_count: 5
  console_output: true
  file_output: false

# CORS配置
cors:
  allowed_origins: ["http://localhost:3000", "http://127.0.0.1:3000"]
  allowed_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  allowed_headers: ["*"]
  allow_credentials: true
  max_age: 86400

# 安全配置
security:
  secret_key: "dev-secret-key-change-in-production"
  algorithm: "HS256"
  access_token_expire_minutes: 1440  # 24小时
  refresh_token_expire_days: 7
  password_min_length: 6
  bcrypt_rounds: 10

# 缓存配置
cache:
  default_ttl: 300
  max_size: 1000
  enable_compression: false

# 邮件配置
email:
  smtp_host: "localhost"
  smtp_port: 1025
  smtp_user: ""
  smtp_password: ""
  use_tls: false
  from_email: "noreply@campusworld.dev"
  from_name: "CampusWorld Dev"

# 存储配置
storage:
  type: "local"
  local_path: "uploads"
  max_file_size: "10MB"
  allowed_extensions: ["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx"]

# 监控配置
monitoring:
  enable_metrics: false
  enable_tracing: false
  metrics_port: 9090
  health_check_path: "/health"

# 外部服务配置
external_services:
  payment_gateway:
    enabled: false
    api_key: "test-key"
    endpoint: "https://api.stripe.com/v1"
  sms_service:
    enabled: false
    api_key: "test-key"
    endpoint: "https://api.twilio.com/2010-04-01"

# 业务配置
business:
  max_users_per_organization: 1000
  max_projects_per_user: 50
  enable_advanced_features: true
  trial_period_days: 30

# 开发配置
development:
  enable_debug_toolbar: true
  enable_profiling: true
  mock_external_services: true
  seed_data: true
  hot_reload: true
  show_sql_queries: true
EOF

    echo -e "${GREEN}✅ 开发环境配置模板已生成: $file${NC}"
}

# 生成测试环境配置模板
generate_test_template() {
    local force="$1"
    local file="$BACKEND_CONFIG_DIR/settings.test.yaml"
    
    if [ -f "$file" ] && [ "$force" != "true" ]; then
        echo -e "${YELLOW}⚠️  测试环境配置文件已存在: $file${NC}"
        echo "使用 -f 选项强制覆盖"
        return 1
    fi
    
    echo -e "${BLUE}📝 生成测试环境配置模板...${NC}"
    
    cat > "$file" << 'EOF'
# CampusWorld 测试环境配置
# 继承自 settings.yaml 并覆盖测试特定设置

# 应用配置
app:
  environment: "testing"
  debug: false

# 服务器配置
server:
  host: "0.0.0.0"
  port: 8001
  workers: 1
  reload: false
  access_log: false

# 数据库配置
database:
  host: "localhost"
  port: 5434
  name: "campusworld_test"
  user: "campusworld_test_user"
  password: "campusworld_test_password"
  pool_size: 5
  max_overflow: 10
  pool_pre_ping: true
  pool_recycle: 300
  echo: false

# Redis配置
redis:
  host: "localhost"
  port: 6381
  password: ""
  db: 1
  pool_size: 5
  socket_timeout: 3
  socket_connect_timeout: 3

# 日志配置
logging:
  level: "WARNING"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  date_format: "%Y-%m-%d %H:%M:%S"
  file_path: "logs/campusworld_test.log"
  max_file_size: "5MB"
  backup_count: 3
  console_output: false
  file_output: true

# CORS配置
cors:
  allowed_origins: ["http://localhost:3001"]
  allowed_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  allowed_headers: ["*"]
  allow_credentials: true
  max_age: 3600

# 安全配置
security:
  secret_key: "test-secret-key-for-testing-only"
  algorithm: "HS256"
  access_token_expire_minutes: 60  # 测试环境使用短token有效期
  refresh_token_expire_days: 1
  password_min_length: 6
  bcrypt_rounds: 8

# 缓存配置
cache:
  default_ttl: 60
  max_size: 100
  enable_compression: false

# 邮件配置
email:
  smtp_host: "localhost"
  smtp_port: 1026
  smtp_user: ""
  smtp_password: ""
  use_tls: false
  from_email: "noreply@campusworld.test"
  from_name: "CampusWorld Test"

# 存储配置
storage:
  type: "local"
  local_path: "uploads_test"
  max_file_size: "5MB"
  allowed_extensions: ["jpg", "jpeg", "png", "gif"]

# 监控配置
monitoring:
  enable_metrics: false
  enable_tracing: false
  metrics_port: 9091
  health_check_path: "/health"

# 外部服务配置
external_services:
  payment_gateway:
    enabled: false
    api_key: "test-key"
    endpoint: "https://api.stripe.com/v1"
  sms_service:
    enabled: false
    api_key: "test-key"
    endpoint: "https://api.twilio.com/2010-04-01"

# 业务配置
business:
  max_users_per_organization: 100
  max_projects_per_user: 10
  enable_advanced_features: false
  trial_period_days: 7

# 开发配置
development:
  enable_debug_toolbar: false
  enable_profiling: false
  mock_external_services: true
  seed_data: true
  hot_reload: false
  show_sql_queries: false
EOF

    echo -e "${GREEN}✅ 测试环境配置模板已生成: $file${NC}"
}

# 生成生产环境配置模板
generate_prod_template() {
    local force="$1"
    local file="$BACKEND_CONFIG_DIR/settings.prod.yaml"
    
    if [ -f "$file" ] && [ "$force" != "true" ]; then
        echo -e "${YELLOW}⚠️  生产环境配置文件已存在: $file${NC}"
        echo "使用 -f 选项强制覆盖"
        return 1
    fi
    
    echo -e "${BLUE}📝 生成生产环境配置模板...${NC}"
    
    cat > "$file" << 'EOF'
# CampusWorld 生产环境配置
# 继承自 settings.yaml 并覆盖生产特定设置

# 应用配置
app:
  environment: "production"
  debug: false

# 服务器配置
server:
  host: "0.0.0.0"
  port: 8000
  workers: 4
  reload: false
  access_log: true

# 数据库配置
database:
  host: "postgres"
  port: 5432
  name: "campusworld"
  user: "campusworld_user"
  password: "CHANGE_ME_IN_PRODUCTION"
  pool_size: 20
  max_overflow: 30
  pool_pre_ping: true
  pool_recycle: 3600
  echo: false

# Redis配置
redis:
  host: "redis"
  port: 6379
  password: "CHANGE_ME_IN_PRODUCTION"
  db: 0
  pool_size: 20
  socket_timeout: 10
  socket_connect_timeout: 10

# 日志配置
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  date_format: "%Y-%m-%d %H:%M:%S"
  file_path: "logs/campusworld.log"
  max_file_size: "100MB"
  backup_count: 10
  console_output: false
  file_output: true

# CORS配置
cors:
  allowed_origins: ["https://campusworld.com", "https://www.campusworld.com"]
  allowed_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  allowed_headers: ["*"]
  allow_credentials: true
  max_age: 86400

# 安全配置
security:
  secret_key: "CHANGE_ME_IN_PRODUCTION"
  algorithm: "HS256"
  access_token_expire_minutes: 1440  # 24小时
  refresh_token_expire_days: 30
  password_min_length: 8
  bcrypt_rounds: 12

# 缓存配置
cache:
  default_ttl: 3600
  max_size: 10000
  enable_compression: true

# 邮件配置
email:
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  smtp_user: "noreply@campusworld.com"
  smtp_password: "CHANGE_ME_IN_PRODUCTION"
  use_tls: true
  from_email: "noreply@campusworld.com"
  from_name: "CampusWorld"

# 存储配置
storage:
  type: "s3"
  s3_bucket: "campusworld-uploads"
  s3_region: "us-east-1"
  s3_access_key: "CHANGE_ME_IN_PRODUCTION"
  s3_secret_key: "CHANGE_ME_IN_PRODUCTION"
  max_file_size: "50MB"
  allowed_extensions: ["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx", "xls", "xlsx"]

# 监控配置
monitoring:
  enable_metrics: true
  enable_tracing: true
  metrics_port: 9090
  health_check_path: "/health"

# 外部服务配置
external_services:
  payment_gateway:
    enabled: true
    api_key: "CHANGE_ME_IN_PRODUCTION"
    endpoint: "https://api.stripe.com/v1"
  smS_service:
    enabled: true
    api_key: "CHANGE_ME_IN_PRODUCTION"
    endpoint: "https://api.twilio.com/2010-04-01"

# 业务配置
business:
  max_users_per_organization: 10000
  max_projects_per_user: 100
  enable_advanced_features: true
  trial_period_days: 30

# 开发配置
development:
  enable_debug_toolbar: false
  enable_profiling: false
  mock_external_services: false
  seed_data: false
  hot_reload: false
  show_sql_queries: false
EOF

    echo -e "${GREEN}✅ 生产环境配置模板已生成: $file${NC}"
}

# 生成预发布环境配置模板
generate_staging_template() {
    local force="$1"
    local file="$BACKEND_CONFIG_DIR/settings.staging.yaml"
    
    if [ -f "$file" ] && [ "$force" != "true" ]; then
        echo -e "${YELLOW}⚠️  预发布环境配置文件已存在: $file${NC}"
        echo "使用 -f 选项强制覆盖"
        return 1
    fi
    
    echo -e "${BLUE}📝 生成预发布环境配置模板...${NC}"
    
    cat > "$file" << 'EOF'
# CampusWorld 预发布环境配置
# 继承自 settings.yaml 并覆盖预发布特定设置

# 应用配置
app:
  environment: "staging"
  debug: false

# 服务器配置
server:
  host: "0.0.0.0"
  port: 8000
  workers: 2
  reload: false
  access_log: true

# 数据库配置
database:
  host: "postgres-staging"
  port: 5432
  name: "campusworld_staging"
  user: "campusworld_staging_user"
  password: "CHANGE_ME_IN_STAGING"
  pool_size: 10
  max_overflow: 15
  pool_pre_ping: true
  pool_recycle: 1800
  echo: false

# Redis配置
redis:
  host: "redis-staging"
  port: 6379
  password: "CHANGE_ME_IN_STAGING"
  db: 0
  pool_size: 10
  socket_timeout: 8
  socket_connect_timeout: 8

# 日志配置
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  date_format: "%Y-%m-%d %H:%M:%S"
  file_path: "logs/campusworld_staging.log"
  max_file_size: "50MB"
  backup_count: 7
  console_output: false
  file_output: true

# CORS配置
cors:
  allowed_origins: ["https://staging.campusworld.com"]
  allowed_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  allowed_headers: ["*"]
  allow_credentials: true
  max_age: 86400

# 安全配置
security:
  secret_key: "CHANGE_ME_IN_STAGING"
  algorithm: "HS256"
  access_token_expire_minutes: 1440  # 24小时
  refresh_token_expire_days: 7
  password_min_length: 8
  bcrypt_rounds: 10

# 缓存配置
cache:
  default_ttl: 1800
  max_size: 5000
  enable_compression: false

# 邮件配置
email:
  smtp_host: "smtp.mailtrap.io"
  smtp_port: 2525
  smtp_user: "CHANGE_ME_IN_STAGING"
  smtp_password: "CHANGE_ME_IN_STAGING"
  use_tls: false
  from_email: "noreply@staging.campusworld.com"
  from_name: "CampusWorld Staging"

# 存储配置
storage:
  type: "s3"
  s3_bucket: "campusworld-staging-uploads"
  s3_region: "us-east-1"
  s3_access_key: "CHANGE_ME_IN_STAGING"
  s3_secret_key: "CHANGE_ME_IN_STAGING"
  max_file_size: "25MB"
  allowed_extensions: ["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx"]

# 监控配置
monitoring:
  enable_metrics: true
  enable_tracing: false
  metrics_port: 9090
  health_check_path: "/health"

# 外部服务配置
external_services:
  payment_gateway:
    enabled: true
    api_key: "CHANGE_ME_IN_STAGING"
    endpoint: "https://api.stripe.com/v1"
  sms_service:
    enabled: false
    api_key: "CHANGE_ME_IN_STAGING"
    endpoint: "https://api.twilio.com/2010-04-01"

# 业务配置
business:
  max_users_per_organization: 1000
  max_projects_per_user: 50
  enable_advanced_features: true
  trial_period_days: 15

# 开发配置
development:
  enable_debug_toolbar: false
  enable_profiling: false
  mock_external_services: false
  seed_data: true
  hot_reload: false
  show_sql_queries: false
EOF

    echo -e "${GREEN}✅ 预发布环境配置模板已生成: $file${NC}"
}

# 生成所有环境配置模板
generate_all_templates() {
    local force="$1"
    
    echo -e "${BLUE}🚀 生成所有环境配置模板...${NC}"
    
    generate_dev_template "$force"
    generate_test_template "$force"
    generate_staging_template "$force"
    generate_prod_template "$force"
    
    echo -e "${GREEN}✅ 所有环境配置模板生成完成${NC}"
}

# 更新现有配置模板
update_templates() {
    echo -e "${BLUE}🔄 更新现有配置模板...${NC}"
    
    # 检查哪些模板存在
    local templates=("dev" "test" "staging" "prod")
    local existing_templates=()
    
    for template in "${templates[@]}"; do
        if [ -f "$BACKEND_CONFIG_DIR/settings.$template.yaml" ]; then
            existing_templates+=("$template")
        fi
    done
    
    if [ ${#existing_templates[@]} -eq 0 ]; then
        echo -e "${YELLOW}⚠️  没有找到现有的配置模板${NC}"
        echo "运行 'generate-all' 命令生成所有模板"
        return 1
    fi
    
    echo -e "${YELLOW}找到以下现有模板: ${existing_templates[*]}${NC}"
    echo "使用 -f 选项强制更新所有模板"
    
    for template in "${existing_templates[@]}"; do
        case "$template" in
            "dev")
                generate_dev_template "true"
                ;;
            "test")
                generate_test_template "true"
                ;;
            "staging")
                generate_staging_template "true"
                ;;
            "prod")
                generate_prod_template "true"
                ;;
        esac
    done
    
    echo -e "${GREEN}✅ 现有配置模板更新完成${NC}"
}

# 验证配置模板
validate_templates() {
    echo -e "${BLUE}🔍 验证配置模板...${NC}"
    
    if ! check_config_files; then
        return 1
    fi
    
    local templates=("dev" "test" "staging" "prod")
    local valid_count=0
    
    for template in "${templates[@]}"; do
        local file="$BACKEND_CONFIG_DIR/settings.$template.yaml"
        if [ -f "$file" ]; then
            echo -e "${YELLOW}验证 $template 环境配置...${NC}"
            
            # 检查YAML语法
            if python3 -c "
import yaml
try:
    with open('$file', 'r') as f:
        yaml.safe_load(f)
    print('✅ YAML语法正确')
except Exception as e:
    print(f'❌ YAML语法错误: {e}')
    exit(1)
"; then
                echo -e "${GREEN}✅ $template 环境配置验证通过${NC}"
                ((valid_count++))
            else
                echo -e "${RED}❌ $template 环境配置验证失败${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  $template 环境配置文件不存在${NC}"
        fi
    done
    
    echo ""
    echo -e "${BLUE}验证结果: $valid_count/${#templates[@]} 个配置模板验证通过${NC}"
    
    if [ $valid_count -eq ${#templates[@]} ]; then
        echo -e "${GREEN}✅ 所有配置模板验证通过${NC}"
        return 0
    else
        echo -e "${RED}❌ 部分配置模板验证失败${NC}"
        return 1
    fi
}

# 检查配置文件
check_config_files() {
    if [ ! -d "$BACKEND_CONFIG_DIR" ]; then
        echo -e "${RED}❌ 后端配置目录不存在: $BACKEND_CONFIG_DIR${NC}"
        return 1
    fi
    
    if [ ! -f "$BACKEND_CONFIG_DIR/settings.yaml" ]; then
        echo -e "${RED}❌ 基础配置文件不存在: $BACKEND_CONFIG_DIR/settings.yaml${NC}"
        return 1
    fi
    
    return 0
}

# 主函数
main() {
    local command="$1"
    local force="false"
    
    # 检查选项
    if [ "$1" = "-f" ] || [ "$1" = "--force" ]; then
        force="true"
        shift
        command="$1"
    fi
    
    case "$command" in
        "generate")
            local env="$2"
            case "$env" in
                "dev")
                    generate_dev_template "$force"
                    ;;
                "test")
                    generate_test_template "$force"
                    ;;
                "staging")
                    generate_staging_template "$force"
                    ;;
                "prod")
                    generate_prod_template "$force"
                    ;;
                *)
                    echo -e "${RED}❌ 未知环境: $env${NC}"
                    echo "支持的环境: dev, test, staging, prod"
                    exit 1
                    ;;
            esac
            ;;
        "generate-all")
            generate_all_templates "$force"
            ;;
        "update-templates")
            update_templates
            ;;
        "validate-templates")
            validate_templates
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
