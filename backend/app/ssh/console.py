"""
优化的SSH控制台模块
基于重构后的命令系统，解决乱码问题
"""
import time
import select
import unicodedata
from typing import Optional, Dict, Any
import os
import paramiko

def _terminal_text_width(text: str) -> int:
    """终端占位宽度估算（SSH 下块状字符多为 EastAsianWidth A，常按双列渲染）。"""
    n = 0
    for ch in text:
        if unicodedata.east_asian_width(ch) in ('F', 'W', 'A'):
            n += 2
        else:
            n += 1
    return n
from app.ssh.session import SSHSession
from app.protocols.ssh_handler import SSHHandler
from app.commands.init_commands import initialize_commands
from app.ssh.nested_repl.io import SshReplIo
from app.core.log import get_logger, LoggerNames

class SSHConsole:
    """优化的SSH控制台 - 解决乱码问题"""

    def __init__(self, channel, session: Optional[SSHSession]=None, *, session_manager: Optional[Any]=None, game_handler: Optional[Any]=None):
        """初始化SSH控制台"""
        self.channel = channel
        self.current_session = session
        self.session_manager = session_manager
        self.game_handler = game_handler
        self.debug_mode = os.getenv('SSH_DEBUG', 'false').lower() == 'true'
        self.logger = get_logger(LoggerNames.SSH)
        if not initialize_commands():
            self.logger.error('Failed to initialize command system')
            raise RuntimeError('命令系统初始化失败')
        self.ssh_handler = SSHHandler()
        self.input_buffer = ''
        self.history = []
        self.history_index = 0
        self.running = False
        self.terminal_width = self._detect_terminal_width()
        self.terminal_height = self._detect_terminal_height()

    def _detect_terminal_width(self) -> int:
        """检测终端宽度"""
        try:
            if hasattr(self.channel, 'get_pty'):
                return 80
            else:
                return 80
        except Exception as e:
            self.logger.debug(f'Terminal width detection failed: {e}')
            return 80

    def _detect_terminal_height(self) -> int:
        """检测终端高度"""
        try:
            if hasattr(self.channel, 'get_pty'):
                return 24
            else:
                return 24
        except Exception as e:
            self.logger.debug(f'Terminal height detection failed: {e}')
            return 24

    def run(self):
        """运行控制台"""
        try:
            self.running = True
            self._display_welcome()
            self._display_prompt()
            while self.running:
                try:
                    self._process_raw_input()
                    time.sleep(0.01)
                except Exception as e:
                    self.logger.error(f'Main loop error: {e}')
                    break
        except Exception as e:
            self.logger.error(f'Console run error{e}')
        finally:
            self._cleanup()

    def _display_welcome(self):
        """显示欢迎信息：块状猫头鹰（风格对齐 Claude Code 终端吉祥物）与版本号。"""
        from app.version import get_version
        version_str = get_version()
        owl_lines = ['                 ▝▘   ▝▘', '                 ▐▛███▜▌', '                 ▜██ ██▛', '                  ▘▘ ▝▝']
        for line in owl_lines:
            self._safe_send_output(line, strip_leading_whitespace=False)
        self._send_newline()
        max_banner_w = max((_terminal_text_width(line) for line in owl_lines))
        version_text = f'CampusWorld OS v{version_str}'
        version_pad = max(0, (max_banner_w - _terminal_text_width(version_text)) // 2)
        self._safe_send_output(f"{' ' * version_pad}{version_text}", strip_leading_whitespace=False)
        self._send_newline()

    def _display_prompt(self):
        """显示提示符 - 简化版本"""
        if self.current_session:
            username = self.current_session.username
            current_game = None
            prompt = self.ssh_handler.get_prompt(username, current_game)
        else:
            prompt = self.ssh_handler.get_prompt('Guest')
        self._send_prompt(prompt)

    def _send_prompt(self, prompt: str) -> bool:
        """发送提示符 - 简化版本，避免乱码"""
        try:
            if not self._check_channel_status():
                return False
            encoded_prompt = prompt.encode('utf-8')
            self.channel.send(encoded_prompt)
            time.sleep(0.01)
            return True
        except Exception as e:
            self.logger.error(f'Failed to send prompt: {e}')
            return False

    def _process_raw_input(self):
        """处理原始输入数据 - 简化版本"""
        try:
            (ready, _, _) = select.select([self.channel], [], [], 0.01)
            if ready:
                data = self.channel.recv(1024)
                if data:
                    text = data.decode('utf-8', errors='ignore')
                    self._process_raw_input_chars(text)
        except Exception as e:
            if 'timeout' not in str(e).lower():
                self.logger.debug(f'Non-blocking read error: {e}')

    def _process_raw_input_chars(self, raw_input: str):
        """处理原始输入字符 - 简化版本，避免乱码"""
        for char in raw_input:
            if char == '\r' or char == '\n':
                if self.input_buffer.strip():
                    command = self.input_buffer.strip()
                    self._send_char_echo('\n')
                    self._process_input(command)
                else:
                    self._send_newline()
                    self._display_prompt()
            elif char == '\x08' or char == '\x7f':
                if self.input_buffer:
                    self.input_buffer = self.input_buffer[:-1]
                    self._send_char_echo('\x08')
                    self._send_char_echo(' ')
                    self._send_char_echo('\x08')
            elif char == '\x03':
                self.input_buffer = ''
                self._send_char_echo('\n')
                ctrl_c_msg = f'Command cancelled (Ctrl+C)\n'
                self._safe_send_output(ctrl_c_msg)
                self._display_prompt()
            elif char == '\x04':
                self.input_buffer = ''
                self._send_char_echo('\n')
                ctrl_d_msg = f'Disconnecting (Ctrl+D)\n'
                self._safe_send_output(ctrl_d_msg)
                self.running = False
            else:
                self.input_buffer += char
                self._send_char_echo(char)

    def _process_input(self, input_text: str):
        """处理输入 - 简化版本"""
        try:
            if input_text.strip():
                self.history.append(input_text)
                self.history_index = len(self.history)
            if self.current_session:
                user_id = str(self.current_session.user_id)
                username = self.current_session.username
                session_id = self.current_session.session_id
                permissions = self.current_session.permissions
            else:
                user_id = 'guest'
                username = 'Guest'
                session_id = 'guest_session'
                permissions = ['guest']
            game_state = self._get_game_state()
            context_metadata: Dict[str, Any] = {}
            if self.session_manager is not None:
                context_metadata['session_manager'] = self.session_manager
            if self.game_handler is not None:
                context_metadata['game_handler'] = self.game_handler
            result = self.ssh_handler.handle_interactive_command(user_id=user_id, username=username, session_id=session_id, permissions=permissions, command_line=input_text, session=self.current_session, game_state=game_state, metadata=context_metadata or None)
            if result:
                self._safe_send_output(result)
            self._send_command_output_newline()
            if self._should_exit(input_text):
                self.running = False
                return
            if self.running and self.current_session:
                nr = getattr(self.current_session, 'nested_repl', None)
                if nr is not None:
                    nr.run(SshReplIo(self))
            if self.running:
                self._display_prompt()
        except Exception as e:
            self.logger.error(f'Input handling error{e}')
            error_msg = f'Input processing error: {str(e)}\n'
            self._safe_send_output(error_msg)
            self._send_command_output_newline()
            if self.running:
                self._display_prompt()
        finally:
            self.input_buffer = ''

    def _should_exit(self, input_text: str) -> bool:
        """检查是否应该退出"""
        command = input_text.strip().lower()
        exit_commands = ['quit', 'exit', 'q']
        return command in exit_commands

    def _check_channel_status(self) -> bool:
        """检查SSH通道状态"""
        try:
            if self.channel.closed:
                self.logger.error('SSH channel closed')
                return False
            if not hasattr(self.channel, 'get_transport') or not self.channel.get_transport():
                self.logger.error('SSH channel transport not available')
                return False
            try:
                self.channel.send('')
                self.logger.debug('SSH channel state check passed')
                return True
            except Exception as e:
                self.logger.error(f'SSH channel write test failed: {e}')
                return False
        except Exception as e:
            self.logger.error(f'SSH channel state check failed: {e}')
            return False

    def _safe_send_output(self, message: str, *, strip_leading_whitespace: bool=True) -> bool:
        """安全发送输出 - 修复版本，参考console.py的输出处理"""
        try:
            if not self._check_channel_status():
                self.logger.warning('Channel state check failed, cannot send output')
                return False
            if not message:
                return True
            if strip_leading_whitespace and (not message.strip()):
                return True
            lines = message.strip().split('\n') if strip_leading_whitespace else message.split('\n')
            if not lines:
                return True
            for (i, line) in enumerate(lines):
                raw = line.rstrip('\r\n')
                segment = raw.lstrip() if strip_leading_whitespace else raw
                if segment.strip():
                    clean_line = segment
                    if clean_line:
                        if i == 0:
                            self.channel.send(b'\r')
                            time.sleep(0.005)
                        output_line = clean_line + '\r\n'
                        encoded_line = output_line.encode('utf-8')
                        self.channel.send(encoded_line)
                        time.sleep(0.01)
                        if i < len(lines) - 1:
                            self.channel.send(b'\r')
                            time.sleep(0.005)
                else:
                    self.channel.send(b'\r\n')
                    time.sleep(0.01)
                    self.channel.send(b'\r')
                    time.sleep(0.005)
            return True
        except Exception as e:
            self.logger.error(f'Failed to send output: {e}')
            return False

    def _send_newline(self) -> bool:
        """发送换行符 - 修复版本，确保光标回到行首"""
        try:
            if not self._check_channel_status():
                return False
            encoded_chars = b'\r\n'
            self.channel.send(encoded_chars)
            time.sleep(0.01)
            return True
        except Exception as e:
            self.logger.error(f'Failed to send newline: {e}')
            return False

    def _send_char_echo(self, char: str) -> bool:
        """发送字符回显 - 修复版本，不添加换行符"""
        try:
            if not self._check_channel_status():
                return False
            encoded_char = char.encode('utf-8')
            self.channel.send(encoded_char)
            time.sleep(0.01)
            return True
        except Exception as e:
            self.logger.error(f'Failed to echo character: {e}')
            return False

    def _send_command_output_newline(self) -> bool:
        """发送命令输出后的换行符 - 确保光标回到行首"""
        try:
            if not self._check_channel_status():
                return False
            encoded_chars = b'\r\n'
            self.channel.send(encoded_chars)
            time.sleep(0.01)
            return True
        except Exception as e:
            self.logger.error(f'Failed to send newline after command output: {e}')
            return False

    def _cleanup(self):
        """清理资源"""
        try:
            self.running = False
            if self.current_session:
                try:
                    if hasattr(self, 'session_manager'):
                        self.session_manager.remove_session(self.current_session.session_id)
                    self.logger.debug(f'Session cleaned up: {self.current_session.session_id}')
                except Exception as e:
                    self.logger.warning(f'Error cleaning up session: {e}')
            self.input_buffer = ''
            self.history.clear()
            if hasattr(self, 'channel') and self.channel:
                try:
                    if not self.channel.closed:
                        self.channel.close()
                        self.logger.debug('SSH channel closed')
                except Exception as e:
                    self.logger.warning(f'Error closing SSH channel: {e}')
        except Exception as e:
            self.logger.error(f'Error cleaning up SSH console resources: {e}')

    def _get_game_state(self) -> Dict[str, Any]:
        """从场景引擎管理器获取场景状态"""
        try:
            from app.game_engine.manager import game_engine_manager
            engine = game_engine_manager.get_engine()
            if not engine:
                return {'is_running': False, 'current_game': None, 'game_info': {}}
            game_status = engine.interface.get_game_status('campus_life')
            if game_status:
                return {'is_running': game_status.get('is_running', False), 'current_game': 'campus_life', 'game_info': game_status}
            else:
                return {'is_running': False, 'current_game': None, 'game_info': {}}
        except Exception as e:
            self.logger.error(f'Failed to get state from World Engine: {e}')
            return {'is_running': False, 'current_game': None, 'game_info': {'error': str(e)}}
