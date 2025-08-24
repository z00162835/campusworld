#!/usr/bin/env python3
"""
SSH服务器启动脚本
提供便捷的启动和管理功能
"""

import os
import sys
import signal
import argparse
import logging
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ssh.server import CampusWorldSSHServer
from app.ssh.config import get_ssh_config, reload_ssh_config


def setup_logging(config):
    """设置日志配置"""
    # 创建日志目录
    log_dir = Path(config.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 配置日志
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format=config.log_format,
        handlers=[
            logging.FileHandler(config.log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )


def signal_handler(signum, frame):
    """信号处理器"""
    print(f"\nReceived signal {signum}, shutting down...")
    if hasattr(signal_handler, 'server'):
        signal_handler.server.stop()
    sys.exit(0)


def start_server(config, args):
    """启动SSH服务器"""
    try:
        # 验证配置
        if not config.validate_config():
            print("❌ Configuration validation failed!")
            return False
        
        # 设置日志
        setup_logging(config)
        logger = logging.getLogger(__name__)
        
        # 显示配置信息
        if args.verbose:
            print(config.get_config_summary())
        
        # 创建并启动服务器
        server = CampusWorldSSHServer(config.host, config.port)
        signal_handler.server = server  # 保存引用用于信号处理
        
        logger.info("Starting CampusWorld SSH Server...")
        print(f"🚀 Starting SSH server on {config.host}:{config.port}")
        
        # 启动服务器
        server.start()
        
    except KeyboardInterrupt:
        print("\n⚠️  Server interrupted by user")
        return True
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        print(f"❌ Failed to start server: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="CampusWorld SSH Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_ssh_server.py                    # 使用默认配置启动
  python start_ssh_server.py --port 2223       # 指定端口
  python start_ssh_server.py --verbose         # 显示详细配置
  python start_ssh_server.py --config-check    # 检查配置
        """
    )
    
    parser.add_argument(
        '--host', 
        default=None,
        help='SSH server host (default: from config)'
    )
    
    parser.add_argument(
        '--port', 
        type=int,
        default=None,
        help='SSH server port (default: from config)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show verbose configuration information'
    )
    
    parser.add_argument(
        '--config-check',
        action='store_true',
        help='Check configuration and exit'
    )
    
    parser.add_argument(
        '--reload-config',
        action='store_true',
        help='Reload configuration from files'
    )
    
    args = parser.parse_args()
    
    # 获取配置
    config = get_ssh_config()
    
    # 处理配置重载
    if args.reload_config:
        print("🔄 Reloading configuration...")
        config = reload_ssh_config()
        print("✅ Configuration reloaded")
        return
    
    # 处理配置检查
    if args.config_check:
        print("🔍 Checking configuration...")
        if config.validate_config():
            print("✅ Configuration is valid")
            print(config.get_config_summary())
        else:
            print("❌ Configuration validation failed!")
        return
    
    # 应用命令行参数
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 显示启动信息
    print("=" * 60)
    print("🏗️  CampusWorld SSH Server")
    print("=" * 60)
    print(f"Host: {config.host}")
    print(f"Port: {config.port}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print("=" * 60)
    
    # 启动服务器
    success = start_server(config, args)
    
    if success:
        print("✅ Server stopped gracefully")
    else:
        print("❌ Server failed to start or encountered an error")
        sys.exit(1)


if __name__ == "__main__":
    main()
