#!/usr/bin/env python3
"""
CampusWorld主程序，作为CampusOS系统的实验性项目的主入口
"""

import os
import sys
import signal
import time
from pathlib import Path
from typing import Optional, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.ssh.server import CampusWorldSSHServer
from app.core.config_manager import get_setting, get_config
from app.core.log import (
    get_logger, 
    setup_logging, 
    LoggerNames,
)
from app.core.paths import get_logs_dir
from app.game_engine.manager import game_engine_manager

class CampusWorld:
    """CampusWorld主程序类"""
    
    def __init__(self):
        # 初始化配置管理器
        self.config_manager = get_config()
        
        # 初始化日志系统
        self._setup_logging()
        
        # 获取专用日志器
        self.logger = get_logger(LoggerNames.APP)
        
        # 系统状态
        self.is_running = False
        self.start_time = None
        
        # 核心组件
        self.ssh_server = None
        
        # 使用游戏引擎管理器而不是直接实例
        self.game_engine_manager = game_engine_manager
        
        self.logger.info("CampusWorld主程序初始化完成")
    
    def _setup_logging(self):
        """设置日志系统"""
        try:
            # 使用项目的日志管理器
            setup_logging(
                level=get_setting('logging.level', 'INFO'),
                format_str=get_setting('logging.format'),
                file_path=str(get_logs_dir(self.config_manager) / get_setting('logging.file_name', 'campusworld.log')),
                console_output=get_setting('logging.console_output', True),
                file_output=get_setting('logging.file_output', True)
            )
            
        except Exception as e:
            print(f"日志系统初始化失败: {e}")
            # 使用默认配置作为后备
            setup_logging()
    
    def load_config(self) -> bool:
        """加载配置"""
        try:
            # 验证配置
            if not self.config_manager.validate():
                self.logger.error("配置验证失败")
                return False
            
            # 获取配置摘要
            config_summary = self.config_manager.get_config_summary()
            self.logger.info(f"配置加载成功:\n{config_summary}")
            return True
            
        except Exception as e:
            self.logger.error(f"配置加载失败: {e}", exc_info=True, extra={
                "error_type": "config_load_error",
                "error_message": str(e)
            })
            return False
    
    def initialize_games(self) -> bool:
        """通过游戏引擎管理器初始化需加载的内容"""
        try:
            
            # 初始化内容引擎
            if not self.game_engine_manager.initialize_engine():
                self.logger.error("引擎初始化失败")
                return False
            
            # 启动内容引擎
            if not self.game_engine_manager.start_engine():
                self.logger.error("引擎启动失败")
                return False
            return True
        except Exception as e:
            self.logger.error(f"内容初始化失败: {e}")
            return False
    
    def initialize_ssh_server(self) -> bool:
        """初始化SSH服务器"""
        try:
            self.logger.info("正在初始化SSH服务器...")
            
            # 从配置获取SSH设置
            ssh_config = self.config_manager.get_ssh_config()
            host = ssh_config.get('host', '0.0.0.0')
            port = ssh_config.get('port', 2222)
            max_connections = ssh_config.get('max_connections', 10)
            worker_threads = ssh_config.get('worker_threads', 2)
            
            self.logger.info(f"SSH配置: host={host}, port={port}, max_connections={max_connections}")
            
            # 创建SSH服务器
            self.ssh_server = CampusWorldSSHServer(host=host, port=port)
            
            self.logger.info(f"SSH服务器初始化成功 ({host}:{port})")
            return True
            
        except Exception as e:
            self.logger.error(f"SSH服务器初始化失败: {e}", exc_info=True, extra={
                "error_type": "ssh_init_error",
                "error_message": str(e)
            })
            return False
    
    def start_ssh_server(self) -> bool:
        """启动SSH服务器"""
        try:
            if not self.ssh_server:
                self.logger.error("SSH服务器未初始化")
                return False
            
            # 启动SSH服务器
            self.ssh_server.start()
            self.logger.info("SSH服务器启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"SSH服务器启动失败: {e}", exc_info=True, extra={
                "error_type": "ssh_start_error",
                "error_message": str(e)
            })
            return False
    
    def start(self) -> bool:
        """启动CampusWorld系统"""
        try:
            if self.is_running:
                self.logger.warning("CampusWorld已在运行中")
                return True
            
            self.start_time = time.time()
            self.is_running = True
            
            self.logger.info("正在启动CampusWorld系统...")
            
            # 1. 加载配置
            if not self.load_config():
                return False
            
            # 2. 初始化游戏
            if not self.initialize_games():
                return False
            
            # 3. 初始化SSH服务器
            if not self.initialize_ssh_server():
                return False
            
            # 4. 启动SSH服务器
            if not self.start_ssh_server():
                return False
            
            self.logger.info("CampusWorld系统启动成功")
            return True
            
        except Exception as e:
            self.logger.error(f"CampusWorld系统启动失败: {e}", exc_info=True, extra={
                "error_type": "system_start_error",
                "error_message": str(e)
            })
            return False
    
    def stop(self) -> bool:
        """停止CampusWorld系统"""
        try:
            if not self.is_running:
                self.logger.warning("CampusWorld未在运行")
                return True
            
            self.logger.info("正在停止CampusWorld系统...")
            
            # 停止SSH服务器
            if self.ssh_server:
                try:
                    self.ssh_server.stop()
                    self.logger.info("SSH服务器已停止")
                except Exception as e:
                    self.logger.error(f"停止SSH服务器失败: {e}", exc_info=True, extra={
                        "error_type": "ssh_stop_error",
                        "host": self.ssh_server.host,
                        "port": self.ssh_server.port
                    })
            
            # 停止内容引擎
            try:
                engine = self.game_engine_manager.get_engine()
                if engine:
                    engine.stop_engine()
                    self.logger.info("内容引擎已停止")
                else:
                    self.logger.warning("内容引擎未初始化，无法停止内容")
            except Exception as e:
                self.logger.error(f"停止内容引擎失败: {e}", exc_info=True, extra={
                    "error_type": "engine_stop_error",
                })
            
            self.is_running = False
            runtime = time.time() - self.start_time if self.start_time else 0
            
            self.logger.info(f"CampusWorld系统已停止，运行时间: {runtime:.2f}秒", extra={
                "runtime_seconds": runtime,
                "stop_time": time.time()
            })
            return True
            
        except Exception as e:
            self.logger.error(f"停止CampusWorld系统失败: {e}", exc_info=True, extra={
                "error_type": "system_stop_error",
                "error_message": str(e)
            })
            return False
    
    def get_status(self) -> dict:
        """获取系统状态 - 通过游戏引擎管理器"""
        status = {
            "is_running": self.is_running,
            "start_time": self.start_time,
            "runtime": time.time() - self.start_time if self.start_time else 0,
            "ssh_server": {
                "is_running": self.ssh_server.is_running if self.ssh_server else False,
                "host": self.ssh_server.host if self.ssh_server else None,
                "port": self.ssh_server.port if self.ssh_server else None,
            } if self.ssh_server else None,
            "config": {
                "environment": self.config_manager.get_environment(),
                "config_dir": str(self.config_manager.config_dir),
                "loaded": self.config_manager.is_loaded()
            }
        }
        
        # 添加游戏状态 - 通过游戏引擎管理器
        try:
            engine = self.game_engine_manager.get_engine()
            if engine:
                game_status = engine.interface.get_game_status('campus_life')
                status["game"] = game_status
            else:
                status["game"] = {"error": "游戏引擎未初始化"}
                
        except Exception as e:
            status["game"] = {"error": str(e)}
        
        return status
    
    def run(self):
        """运行CampusWorld系统"""
        try:
            # 启动系统
            if not self.start():
                self.logger.error("CampusWorld系统启动失败")
                return False
            
            # 显示系统状态
            self._display_status()

            # 保持运行
            try:
                while self.is_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.logger.info("收到中断信号，正在关闭...")
            
            return True
            
        except Exception as e:
            self.logger.error(f"运行CampusWorld系统失败: {e}", exc_info=True, extra={
                "error_type": "system_run_error",
                "error_message": str(e)
            })
            return False
        
        finally:
            # 清理资源
            self.stop()
    
    def _display_status(self):
        """显示系统状态"""
        status = self.get_status()
        
        # 记录状态显示到日志
        self.logger.info("显示系统状态")
        
        print("\n" + "=" * 60)
        print("CampusWorld 系统状态")
        print("=" * 60)
        
        # 配置信息
        config = status.get("config", {})
        print(f"环境: {config.get('environment', 'Unknown')}")
        print(f"配置目录: {config.get('config_dir', 'Unknown')}")
        print(f"配置状态: {'已加载' if config.get('loaded') else '未加载'}")
        
        # 游戏状态
        if "game" in status and "error" not in status["game"]:
            game = status["game"]
            print(f"游戏: {game.get('name', 'N/A')}")
            print(f"  版本: {game.get('version', 'N/A')}")
            print(f"  描述: {game.get('description', 'N/A')}")
            print(f"  状态: {'运行中' if game.get('is_running') else '已停止'}")
            print(f"  房间数量: {game.get('rooms_count', 0)}")
            print(f"  物品数量: {game.get('items_count', 0)}")
            print(f"  角色数量: {game.get('characters_count', 0)}")
        
        # SSH服务器状态
        if status["ssh_server"]:
            ssh = status["ssh_server"]
            print(f"SSH服务器: {'运行中' if ssh.get('is_running') else '已停止'}")
            print(f"  地址: {ssh.get('host', 'N/A')}:{ssh.get('port', 'N/A')}")
        
        print(f"系统运行时间: {status['runtime']:.2f}秒")
        print("\n系统已启动，可以通过SSH连接进行交互")
        print("使用 'help' 命令查看可用命令")
        print("使用 'game help' 命令查看游戏管理帮助")
        print("\n按 Ctrl+C 停止系统")
        print("=" * 60)


def signal_handler(signum, frame):
    """信号处理器"""
    # 使用print确保用户能看到中断信息
    print(f"\n收到信号 {signum}，正在关闭CampusWorld系统...")
    
    if hasattr(signal_handler, 'campusworld'):
        # 记录到日志
        campusworld = signal_handler.campusworld
        if hasattr(campusworld, 'logger'):
            campusworld.logger.info(f"收到信号 {signum}，正在关闭系统")
        campusworld.stop()
    
    sys.exit(0)


def main():
    """主函数"""
    # 使用print显示启动信息给用户
    print("=" * 60)
    print("CampusWorld 主程序")
    print("=" * 60)
    
    try:
        # 设置信号处理器
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 创建CampusWorld实例
        campusworld = CampusWorld()
        signal_handler.campusworld = campusworld
        
        # 运行系统
        success = campusworld.run()
        
        return success
        
    except Exception as e:
        # 使用print确保错误信息显示给用户
        print(f"启动CampusWorld系统失败: {e}")
        # 同时记录到日志（如果可能）
        try:
            import logging
            logging.error(f"启动CampusWorld系统失败: {e}", exc_info=True)
        except:
            pass
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
