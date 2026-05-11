"""
CampusWorld主程序，作为CampusOS系统的实验性项目的主入口
"""
import os
import sys
import signal
import time
from pathlib import Path
from typing import Optional, Dict, Any
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
import threading
import logging
for _logger_name in ['passlib', 'passlib.utils', 'passlib.utils.compat', 'passlib.registry']:
    logging.getLogger(_logger_name).setLevel(logging.WARNING)
from app.ssh.server import CampusWorldSSHServer
from app.core.config_manager import get_setting, get_config
from app.core.log import get_logger, setup_logging, LoggerNames
from app.core.log.manager import get_logging_manager
from app.core.paths import get_logs_dir
from app.game_engine.manager import game_engine_manager
from app.api.server import HTTPServer

class CampusWorld:
    """CampusWorld主程序类"""

    def __init__(self):
        self.config_manager = get_config()
        self._setup_logging()
        self.logger = get_logger(LoggerNames.APP)
        self.is_running = False
        self.start_time = None
        self.ssh_server = None
        self.http_server = None
        self.game_engine_manager = game_engine_manager
        self.logger.info('CampusWorld main program initialization completed')

    def _setup_logging(self):
        """设置日志系统"""
        try:
            setup_logging(level=get_setting('logging.level', 'INFO'), format_str=get_setting('logging.format'), file_path=str(get_logs_dir(self.config_manager) / get_setting('logging.file_name', 'campusworld.log')), console_output=get_setting('logging.console_output', True), file_output=get_setting('logging.file_output', True))
        except Exception as e:
            print(f'Logging system initialization failed: {e}')
            setup_logging()

    def load_config(self) -> bool:
        """加载配置"""
        try:
            if not self.config_manager.validate():
                self.logger.error('Configuration validation failed')
                return False
            config_summary = self.config_manager.get_config_summary()
            self.logger.info(f'Configuration loaded successfully:\n{config_summary}')
            return True
        except Exception as e:
            self.logger.error(f'Failed to load configuration: {e}', exc_info=True, extra={'error_type': 'config_load_error', 'error_message': str(e)})
            return False

    def initialize_games(self) -> bool:
        """通过场景引擎管理器初始化需加载的内容"""
        try:
            if not self.game_engine_manager.initialize_engine():
                self.logger.error('Engine initialization failed')
                return False
            if not self.game_engine_manager.start_engine():
                self.logger.error('Engine start failed')
                return False
            return True
        except Exception as e:
            self.logger.error(f'Failed to initialize content: {e}')
            return False

    def initialize_ssh_server(self) -> bool:
        """初始化SSH服务器"""
        try:
            self.logger.info('Initializing SSH server...')
            ssh_config = self.config_manager.get_ssh_config()
            host = ssh_config.get('host', '0.0.0.0')
            port = ssh_config.get('port', 2222)
            max_connections = ssh_config.get('max_connections', 10)
            worker_threads = ssh_config.get('worker_threads', 2)
            self.logger.info(f'SSH configuration: host={host}, port={port}, max_connections={max_connections}')
            self.ssh_server = CampusWorldSSHServer(host=host, port=port)
            self.logger.info(f'SSH server initialized successfully ({host}:{port})')
            return True
        except Exception as e:
            self.logger.error(f'Failed to initialize SSH server: {e}', exc_info=True, extra={'error_type': 'ssh_init_error', 'error_message': str(e)})
            return False

    def start_ssh_server(self) -> bool:
        """启动SSH服务器"""
        try:
            if not self.ssh_server:
                self.logger.error('SSH server not initialized')
                return False
            self.ssh_server.start()
            self.logger.info('SSH server started successfully')
            return True
        except Exception as e:
            self.logger.error(f'Failed to start SSH server: {e}', exc_info=True, extra={'error_type': 'ssh_start_error', 'error_message': str(e)})
            return False

    def initialize_http_server(self) -> bool:
        """初始化HTTP/WebSocket服务器"""
        try:
            self.logger.info('Initializing HTTP/WebSocket server...')
            server_config = self.config_manager.get_server_config()
            host = server_config.get('host', '0.0.0.0')
            port = server_config.get('port', 8000)
            self.http_server = HTTPServer(host=host, port=port)
            self.logger.info(f'HTTP server initialized: {host}:{port}')
            return True
        except Exception as e:
            self.logger.error(f'Failed to initialize HTTP server: {e}', exc_info=True, extra={'error_type': 'http_init_error', 'error_message': str(e)})
            return False

    def start_http_server(self) -> bool:
        """启动HTTP/WebSocket服务器"""
        if not self.http_server:
            self.logger.error('HTTP server not initialized')
            return False
        return self.http_server.start()

    def start(self) -> bool:
        """启动CampusWorld系统"""
        try:
            if self.is_running:
                self.logger.warning('CampusWorld is already running')
                return True
            self.start_time = time.time()
            self.is_running = True
            self.logger.info('Starting CampusWorld system...')
            if not self.load_config():
                return False
            if not self.game_engine_manager.initialize_engine():
                self.logger.error('Engine initialization failed')
                return False
            if not self.game_engine_manager.start_engine():
                self.logger.error('Engine start failed')
                return False
            if not self.initialize_http_server():
                self.logger.error('HTTP server initialization failed')
                return False
            if not self.start_http_server():
                self.logger.error('HTTP server start failed')
                return False
            ssh_config = self.config_manager.get_ssh_config()
            host = ssh_config.get('host', '0.0.0.0')
            port = ssh_config.get('port', 2222)
            max_connections = ssh_config.get('max_connections', 10)
            self.logger.info(f'SSH configuration: host={host}, port={port}, max_connections={max_connections}')
            self.ssh_server = CampusWorldSSHServer(host=host, port=port)
            self.ssh_server.start()
            self.logger.info('CampusWorld system started successfully')
            return True
        except Exception as e:
            self.logger.error(f'CampusWorld system startup failed: {e}', exc_info=True, extra={'error_type': 'system_start_error', 'error_message': str(e)})
            return False

    def stop(self) -> bool:
        """停止CampusWorld系统"""
        try:
            if getattr(self, '_is_stopping', False):
                return False
            self._is_stopping = True
            if not self.is_running:
                return True
            self.logger.info('Stopping CampusWorld system...')
            if self.ssh_server:
                try:
                    self.ssh_server.stop()
                    self.logger.info('SSH server stopped')
                except Exception as e:
                    self.logger.error(f'Failed to stop SSH server: {e}', exc_info=True, extra={'error_type': 'ssh_stop_error', 'host': self.ssh_server.host, 'port': self.ssh_server.port})
            try:
                engine = self.game_engine_manager.get_engine()
                if engine:
                    engine.stop_engine()
                    self.logger.info('Content engine stopped')
                else:
                    self.logger.warning('Content engine not initialized, cannot stop content')
            except Exception as e:
                self.logger.error(f'Failed to stop content engine: {e}', exc_info=True, extra={'error_type': 'engine_stop_error'})
            self.is_running = False
            runtime = time.time() - self.start_time if self.start_time else 0
            self.logger.info(f'CampusWorld system stopped, runtime: {runtime:.2f} seconds', extra={'runtime_seconds': runtime, 'stop_time': time.time()})
            return True
        except Exception as e:
            self.logger.error(f'Failed to stop CampusWorld system: {e}', exc_info=True, extra={'error_type': 'system_stop_error', 'error_message': str(e)})
            return False

    def get_status(self) -> dict:
        """获取系统状态 - 通过场景引擎管理器"""
        status = {'is_running': self.is_running, 'start_time': self.start_time, 'runtime': time.time() - self.start_time if self.start_time else 0, 'ssh_server': None}
        if self.ssh_server:
            try:
                status['ssh_server'] = {'is_running': self.ssh_server.running if hasattr(self.ssh_server, 'running') else False, 'host': getattr(self.ssh_server, 'host', None), 'port': getattr(self.ssh_server, 'port', None)}
            except Exception:
                status['ssh_server'] = {'is_running': False, 'error': 'shutting_down'}
        status['config'] = {'environment': self.config_manager.get_environment(), 'config_dir': str(self.config_manager.config_dir), 'loaded': self.config_manager.is_loaded()}
        return status

    def run(self):
        """运行CampusWorld系统"""
        try:
            if not self.start():
                self.logger.error('CampusWorld system start failed')
                return False
            self._display_status()
            try:
                while self.is_running:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                self.logger.info('Keyboard interrupt received')
            return True
        except Exception as e:
            self.logger.error(f'Run failed: {e}', exc_info=True)
            return False
        finally:
            self.stop()

    def _display_status(self):
        """显示系统状态"""
        status = self.get_status()
        self.logger.info('Show system status')
        print('\n' + '=' * 60)
        print('CampusWorld System Status')
        print('=' * 60)
        config = status.get('config', {})
        print(f"环境: {config.get('environment', 'Unknown')}")
        print(f"配置目录: {config.get('config_dir', 'Unknown')}")
        print(f"Config status: {('Loaded' if config.get('loaded') else 'Not loaded')}")
        if 'game' in status and 'error' not in status['game']:
            game = status['game']
            print(f"场景: {game.get('name', 'N/A')}")
            print(f"  版本: {game.get('version', 'N/A')}")
            print(f"  描述: {game.get('description', 'N/A')}")
            print(f"  Status: {('Running' if game.get('is_running') else 'Stopped')}")
            print(f"  房间数量: {game.get('rooms_count', 0)}")
            print(f"  物品数量: {game.get('items_count', 0)}")
            print(f"  角色数量: {game.get('characters_count', 0)}")
        if status['ssh_server']:
            ssh = status['ssh_server']
            print(f"SSH server: {('Running' if ssh.get('is_running') else 'Stopped')}")
            print(f"  地址: {ssh.get('host', 'N/A')}:{ssh.get('port', 'N/A')}")
        print(f"系统运行时间: {status['runtime']:.2f}秒")
        print('\nSystem started, you can interact via SSH connection')
        print("使用 'help' 命令查看可用命令")
        print("使用 'game help' 命令查看场景管理帮助")
        print('\nPress Ctrl+C to stop the system')
        print('=' * 60)

def signal_handler(signum, frame):
    """信号处理器"""
    if getattr(signal_handler, '_handling', False):
        return
    signal_handler._handling = True
    if hasattr(signal_handler, 'campusworld'):
        campusworld = signal_handler.campusworld
        if hasattr(campusworld, 'logger'):
            campusworld.logger.info(f'Received signal {signum}, shutting down system')
        campusworld.stop()

def main():
    """主函数"""
    print('=' * 60)
    print('CampusWorld Main Program')
    print('=' * 60)
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        campusworld = CampusWorld()
        signal_handler.campusworld = campusworld
        success = campusworld.run()
        logging_manager = get_logging_manager()
        logging_manager.stop_listener()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0 if success else 1)
    except Exception as e:
        print(f'Failed to start CampusWorld system: {e}')
        try:
            import logging
            logging.error(f'Failed to start CampusWorld system: {e}', exc_info=True)
        except:
            pass
        return False
if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
