"""
基于Pydantic的配置模型
提供类型安全的配置访问和验证
"""

from typing import List, Optional
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


class AppConfig(BaseModel):
    """应用基础配置"""
    name: str = Field(default="CampusWorld", description="应用名称")
    version: str = Field(default="0.1.0", description="应用版本")
    description: str = Field(default="A modern campus world application", description="应用描述")
    debug: bool = Field(default=False, description="调试模式")
    environment: str = Field(default="development", description="运行环境")


class APIConfig(BaseModel):
    """API配置"""
    v1_prefix: str = Field(default="/api/v1", description="API v1前缀")
    title: str = Field(default="CampusWorld API", description="API标题")
    description: str = Field(default="CampusWorld REST API Documentation", description="API描述")
    docs_url: str = Field(default="/docs", description="Swagger文档URL")
    redoc_url: str = Field(default="/redoc", description="ReDoc文档URL")
    openapi_url: str = Field(default="/openapi.json", description="OpenAPI规范URL")


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = Field(default="0.0.0.0", description="服务器主机")
    port: int = Field(default=8000, description="服务器端口")
    workers: int = Field(default=1, description="工作进程数")
    reload: bool = Field(default=True, description="自动重载")
    access_log: bool = Field(default=True, description="访问日志")


class SecurityConfig(BaseModel):
    """安全配置"""
    secret_key: str = Field(default="your-secret-key-here-change-in-production", description="JWT密钥")
    algorithm: str = Field(default="HS256", description="JWT算法")
    access_token_expire_minutes: int = Field(default=11520, description="访问令牌过期时间(分钟)")
    refresh_token_expire_days: int = Field(default=30, description="刷新令牌过期时间(天)")
    password_min_length: int = Field(default=8, description="密码最小长度")
    bcrypt_rounds: int = Field(default=12, description="BCrypt轮数")


class DatabaseConfig(BaseModel):
    """数据库配置"""
    engine: str = Field(default="postgresql", description="数据库引擎")
    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=5432, description="数据库端口")
    name: str = Field(default="campusworld", description="数据库名称")
    user: str = Field(default="", description="数据库用户")
    password: str = Field(default="", description="数据库密码")
    pool_size: int = Field(default=20, description="连接池大小")
    max_overflow: int = Field(default=30, description="最大溢出连接数")
    pool_pre_ping: bool = Field(default=True, description="连接前ping")
    pool_recycle: int = Field(default=300, description="连接回收时间")
    echo: bool = Field(default=False, description="显示SQL语句")


class RedisConfig(BaseModel):
    """Redis配置"""
    host: str = Field(default="localhost", description="Redis主机")
    port: int = Field(default=6379, description="Redis端口")
    db: int = Field(default=0, description="Redis数据库")
    password: str = Field(default="", description="Redis密码")
    max_connections: int = Field(default=10, description="最大连接数")
    socket_timeout: int = Field(default=5, description="Socket超时")
    socket_connect_timeout: int = Field(default=5, description="Socket连接超时")


class CacheConfig(BaseModel):
    """缓存配置"""
    default_ttl: int = Field(default=3600, description="默认TTL(秒)")
    max_size: int = Field(default=1000, description="最大缓存项数")
    enable_compression: bool = Field(default=True, description="启用压缩")


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="日志格式")
    date_format: str = Field(default="%Y-%m-%d %H:%M:%S", description="日期格式")
    file_path: str = Field(default="logs/campusworld.log", description="日志文件路径")
    max_file_size: str = Field(default="10MB", description="最大文件大小")
    backup_count: int = Field(default=5, description="备份文件数")
    console_output: bool = Field(default=True, description="控制台输出")
    file_output: bool = Field(default=False, description="文件输出")


class CORSConfig(BaseModel):
    """CORS配置"""
    allowed_origins: List[str] = Field(default=["*"], description="允许的源")
    allowed_methods: List[str] = Field(default=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], description="允许的方法")
    allowed_headers: List[str] = Field(default=["*"], description="允许的头部")
    allow_credentials: bool = Field(default=True, description="允许凭据")
    max_age: int = Field(default=86400, description="预检请求缓存时间")


class EmailConfig(BaseModel):
    """邮件配置"""
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP主机")
    smtp_port: int = Field(default=587, description="SMTP端口")
    smtp_user: str = Field(default="", description="SMTP用户")
    smtp_password: str = Field(default="", description="SMTP密码")
    use_tls: bool = Field(default=True, description="使用TLS")
    from_email: str = Field(default="noreply@campusworld.com", description="发件人邮箱")
    from_name: str = Field(default="CampusWorld", description="发件人名称")


class StorageConfig(BaseModel):
    """文件存储配置"""
    type: str = Field(default="local", description="存储类型")
    local_path: str = Field(default="uploads/", description="本地存储路径")
    max_file_size: str = Field(default="10MB", description="最大文件大小")
    allowed_extensions: List[str] = Field(default=["jpg", "jpeg", "png", "gif", "pdf", "doc", "docx"], description="允许的文件扩展名")


class MonitoringConfig(BaseModel):
    """监控配置"""
    enable_metrics: bool = Field(default=True, description="启用指标")
    metrics_port: int = Field(default=9090, description="指标端口")
    health_check_interval: int = Field(default=30, description="健康检查间隔")
    enable_tracing: bool = Field(default=False, description="启用链路追踪")
    tracing_host: str = Field(default="localhost", description="追踪主机")
    tracing_port: int = Field(default=6831, description="追踪端口")


class PaymentServiceConfig(BaseModel):
    """支付服务配置"""
    provider: str = Field(default="stripe", description="支付提供商")
    api_key: str = Field(default="", description="API密钥")
    webhook_secret: str = Field(default="", description="Webhook密钥")


class SMSServiceConfig(BaseModel):
    """短信服务配置"""
    provider: str = Field(default="twilio", description="短信提供商")
    account_sid: str = Field(default="", description="账户SID")
    auth_token: str = Field(default="", description="认证令牌")
    from_number: str = Field(default="", description="发送号码")


class MapsServiceConfig(BaseModel):
    """地图服务配置"""
    provider: str = Field(default="google", description="地图提供商")
    api_key: str = Field(default="", description="API密钥")


class ExternalServicesConfig(BaseModel):
    """第三方服务配置"""
    payment: PaymentServiceConfig = Field(default_factory=PaymentServiceConfig)
    sms: SMSServiceConfig = Field(default_factory=SMSServiceConfig)
    maps: MapsServiceConfig = Field(default_factory=MapsServiceConfig)


class UserBusinessConfig(BaseModel):
    """用户业务配置"""
    default_avatar: str = Field(default="default-avatar.png", description="默认头像")
    max_login_attempts: int = Field(default=5, description="最大登录尝试次数")
    lockout_duration: int = Field(default=900, description="锁定持续时间(秒)")


class CampusBusinessConfig(BaseModel):
    """校园业务配置"""
    max_members: int = Field(default=1000, description="最大成员数")
    max_activities: int = Field(default=100, description="最大活动数")


class WorldBusinessConfig(BaseModel):
    """世界业务配置"""
    max_players: int = Field(default=10000, description="最大玩家数")
    save_interval: int = Field(default=300, description="保存间隔(秒)")


class BusinessConfig(BaseModel):
    """业务配置"""
    user: UserBusinessConfig = Field(default_factory=UserBusinessConfig)
    campus: CampusBusinessConfig = Field(default_factory=CampusBusinessConfig)
    world: WorldBusinessConfig = Field(default_factory=WorldBusinessConfig)


class DevelopmentConfig(BaseModel):
    """开发配置"""
    enable_debug_toolbar: bool = Field(default=False, description="启用调试工具栏")
    enable_profiling: bool = Field(default=False, description="启用性能分析")
    mock_external_services: bool = Field(default=True, description="模拟外部服务")
    seed_data: bool = Field(default=True, description="种子数据")


class Settings(BaseModel):
    """应用设置"""
    app: AppConfig = Field(default_factory=AppConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    cors: CORSConfig = Field(default_factory=CORSConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    external_services: ExternalServicesConfig = Field(default_factory=ExternalServicesConfig)
    business: BusinessConfig = Field(default_factory=BusinessConfig)
    development: DevelopmentConfig = Field(default_factory=DevelopmentConfig)
    
    @validator('security')
    def validate_secret_key(cls, v):
        # 在开发环境中允许使用默认密钥
        if not v.secret_key:
            raise ValueError("Secret key must be set")
        return v


def create_settings_from_config(config_manager) -> Settings:
    """从配置管理器创建设置实例"""
    config_data = config_manager.get_all()
    return Settings(**config_data)
