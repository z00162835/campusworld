"""
优化的SSH控制台模块
基于重构后的命令系统，解决乱码问题
"""

import time
import select
from typing import Optional, Dict, Any
import os

import paramiko

from app.ssh.session import SSHSession
from app.protocols.ssh_handler import SSHHandler
from app.commands.init_commands import initialize_commands
from app.commands.base import CommandContext
from app.commands.registry import command_registry
from app.core.log import get_logger, LoggerNames

class SSHConsole:
    """优化的SSH控制台 - 解决乱码问题"""
    
    def __init__(self, channel, session: Optional[SSHSession] = None):
        """初始化SSH控制台"""
        self.channel = channel
        self.current_session = session
        
        # 设置日志级别
        self.debug_mode = os.getenv('SSH_DEBUG', 'false').lower() == 'true'
        
        # 初始化日志系统
        self.logger = get_logger(LoggerNames.SSH)
        
        # 初始化命令系统
        if not initialize_commands():
            self.logger.error("命令系统初始化失败")
            raise RuntimeError("命令系统初始化失败")
        
        # 初始化SSH协议处理器
        self.ssh_handler = SSHHandler()
        
        # 初始化其他组件
        self.input_buffer = ""
        self.history = []
        self.history_index = 0
        self.running = False
        
        # 设置终端尺寸
        self.terminal_width = self._detect_terminal_width()
        self.terminal_height = self._detect_terminal_height()
    
    
    def _detect_terminal_width(self) -> int:
        """检测终端宽度"""
        try:
            if hasattr(self.channel, 'get_pty'):
                return 80
            else:
                return 80
        except:
            return 80
    
    def _detect_terminal_height(self) -> int:
        """检测终端高度"""
        try:
            if hasattr(self.channel, 'get_pty'):
                return 24
            else:
                return 24
        except:
            return 24
    
    def run(self):
        """运行控制台"""
        try:
            self.running = True
            
            # 显示欢迎信息
            self._display_welcome()
            
            # 显示初始提示符
            self._display_prompt()
            
            # 主循环
            while self.running:
                try:
                    # 处理输入
                    self._process_raw_input()
                    
                    # 短暂休眠，避免CPU占用过高
                    time.sleep(0.01)
                    
                except Exception as e:
                    self.logger.error(f"主循环错误: {e}")
                    break
                    
        except Exception as e:
            self.logger.error(f"控制台运行错误: {e}")
        finally:
            self._cleanup()
    
    def _display_welcome(self):
        """显示欢迎信息 - 简化版本，避免乱码"""
        # 获取用户信息
        if self.current_session:
            username = self.current_session.username
            user_id = str(self.current_session.user_id)
        else:
            username = "Guest"
            user_id = "guest"
        
        # 获取权限信息
        permissions = self.current_session.permissions if self.current_session else ["guest"]

        # 创建命令上下文
        context = CommandContext(
            user_id=user_id,
            username=username,
            session_id=self.current_session.session_id if self.current_session else "guest_session",
            permissions=permissions
        )
    
        # 动态获取可用命令
        available_commands = command_registry.get_available_commands(context)

        # 构建欢迎信息
        welcome_lines = [
            "Welcome to CampusWorld!",
            "",
            "Available Commands:",
        ]
        for cmd in available_commands:
            welcome_lines.append(f"  {cmd.name:<15} - {cmd.description}")
        
        welcome_lines.extend([
            "",
            "Type 'help' for detailed information",
            f"Connected as: {username}",
            f"Terminal: {self.terminal_width}x{self.terminal_height}",
            f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "Ready for adventure!",
            ""
        ])
        
        # 逐行发送欢迎信息
        for line in welcome_lines:
            self._safe_send_output(line)
    
    def _display_prompt(self):
        """显示提示符 - 简化版本"""
        if self.current_session:
            username = self.current_session.username
            # 获取当前场景状态
            current_game = None  # 这里应该从场景状态获取
            prompt = self.ssh_handler.get_prompt(username, current_game)
        else:
            prompt = self.ssh_handler.get_prompt("Guest")
        
        # 发送提示符
        self._send_prompt(prompt)
    
    def _send_prompt(self, prompt: str) -> bool:
        """发送提示符 - 简化版本，避免乱码"""
        try:
            if not self._check_channel_status():
                return False
            
            # 直接发送提示符，不添加换行符
            encoded_prompt = prompt.encode('utf-8')
            self.channel.send(encoded_prompt)
            
            # 短暂等待，确保提示符传输完成
            time.sleep(0.01)
            
            return True
            
        except Exception as e:
            self.logger.error(f"提示符发送失败: {e}")
            return False
    
    def _process_raw_input(self):
        """处理原始输入数据 - 简化版本"""
        try:
            # 使用select进行非阻塞检查
            ready, _, _ = select.select([self.channel], [], [], 0.01)
            if ready:
                # 有数据可读
                data = self.channel.recv(1024)
                if data:
                    # 解码数据
                    text = data.decode('utf-8', errors='ignore')
                    self._process_raw_input_chars(text)
                    
        except Exception as e:
            if "timeout" not in str(e).lower():
                self.logger.debug(f"非阻塞读取错误: {e}")
    
    def _process_raw_input_chars(self, raw_input: str):
        """处理原始输入字符 - 简化版本，避免乱码"""
        
        for char in raw_input:
            
            if char == '\r' or char == '\n':
                # 输入完成，提交命令
                if self.input_buffer.strip():
                    command = self.input_buffer.strip()
                    # 发送换行符，确保命令输入完成
                    self._send_char_echo('\n')
                    # 处理命令
                    self._process_input(command)
                else:
                    # 空命令显示新提示符
                    self._send_newline()
                    self._display_prompt()
            elif char == '\b' or char == '\x7f':  # Backspace
                if self.input_buffer:
                    self.input_buffer = self.input_buffer[:-1]
                    # 发送退格序列
                    self._send_char_echo('\b')
                    self._send_char_echo(' ')
                    self._send_char_echo('\b')
            elif char == '\x03':  # Ctrl+C
                self.input_buffer = ""
                # 发送换行符
                self._send_char_echo('\n')
                # 显示Ctrl+C消息
                ctrl_c_msg = f"Command cancelled (Ctrl+C)\n"
                self._safe_send_output(ctrl_c_msg)
                # 显示新提示符
                self._display_prompt()
            elif char == '\x04':  # Ctrl+D
                self.input_buffer = ""
                # 发送换行符
                self._send_char_echo('\n')
                # 显示Ctrl+D消息
                ctrl_d_msg = f"Disconnecting (Ctrl+D)\n"
                self._safe_send_output(ctrl_d_msg)
                self.running = False
            else:
                self.input_buffer += char
                # 回显字符
                self._send_char_echo(char)
    
    def _process_input(self, input_text: str):
        """处理输入 - 简化版本"""
        try:
            # 添加到历史记录
            if input_text.strip():
                self.history.append(input_text)
                self.history_index = len(self.history)
            
            # 获取用户信息
            if self.current_session:
                user_id = str(self.current_session.user_id)
                username = self.current_session.username
                session_id = self.current_session.session_id
                permissions = self.current_session.permissions
            else:
                user_id = "guest"
                username = "Guest"
                session_id = "guest_session"
                permissions = ["guest"]
            
            # 获取场景状态
            game_state = self._get_game_state()
            
            # 使用SSH处理器处理命令
            result = self.ssh_handler.handle_interactive_command(
                user_id=user_id,
                username=username,
                session_id=session_id,
                permissions=permissions,
                command_line=input_text,
                session=self.current_session,
                game_state=game_state
            )
            
            # 发送结果
            if result:
                self._safe_send_output(result)
            
            # 发送额外的换行符，确保输出格式对齐
            self._send_command_output_newline()
            
            # 检查是否需要退出
            if self._should_exit(input_text):
                self.running = False
                return

            # 显示新提示符
            if self.running:
                self._display_prompt()
            
        except Exception as e:
            self.logger.error(f"输入处理错误: {e}")
            # 发送错误消息
            error_msg = f"Input processing error: {str(e)}\n"
            self._safe_send_output(error_msg)
            
            # 发送额外的换行符，确保输出格式对齐
            self._send_command_output_newline()
            
            # 显示新提示符
            if self.running:
                self._display_prompt()
        finally:
            # 确保输入缓冲区被清空
            self.input_buffer = ""
            
    def _should_exit(self, input_text: str) -> bool:
        """检查是否应该退出"""
        command = input_text.strip().lower()
        exit_commands = ['quit', 'exit', 'q']
        return command in exit_commands

    def _check_channel_status(self) -> bool:
        """检查SSH通道状态"""
        try:
            # 检查通道是否关闭
            if self.channel.closed:
                self.logger.error("SSH通道已关闭")
                return False
            
            # 检查通道是否活跃
            if not hasattr(self.channel, 'get_transport') or not self.channel.get_transport():
                self.logger.error("SSH通道传输层不可用")
                return False
            
            # 检查通道是否可写
            try:
                # 尝试发送一个空字节来测试通道状态
                self.channel.send("")
                self.logger.debug("SSH通道状态检查通过")
                return True
            except Exception as e:
                self.logger.error(f"SSH通道写入测试失败: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"SSH通道状态检查失败: {e}")
            return False
    
    def _safe_send_output(self, message: str) -> bool:
        """安全发送输出 - 修复版本，参考console.py的输出处理"""
        try:
            if not self._check_channel_status():
                self.logger.warning("通道状态检查失败，无法发送输出")
                return False
            
            # 确保消息格式正确
            if not message or not message.strip():
                return True
            
            # 将消息按行分割
            lines = message.strip().split('\n')
            if not lines:
                return True
            
            # 逐行发送，确保光标位置正确
            for i, line in enumerate(lines):
                if line.strip():  # 跳过空行
                    # 确保行首没有前导空格
                    clean_line = line.lstrip()
                    if clean_line:
                        # 强制居左：在行首添加控制字符确保居左
                        if i == 0:  # 第一行特别处理
                            # 发送回车确保光标回到行首
                            self.channel.send(b'\r')
                            time.sleep(0.005)
                        
                        # 发送清理后的行，使用 \r\n 确保光标回到行首
                        output_line = clean_line + '\r\n'
                        encoded_line = output_line.encode('utf-8')
                        self.channel.send(encoded_line)
                        
                        # 短暂等待，确保传输完成
                        time.sleep(0.01)
                        
                        # 额外确保光标回到行首，防止位置累积
                        if i < len(lines) - 1:  # 不是最后一行
                            self.channel.send(b'\r')
                            time.sleep(0.005)
                        
                else:
                    # 发送空行，确保光标回到行首
                    self.channel.send(b'\r\n')
                    time.sleep(0.01)
                    
                    # 额外确保光标回到行首
                    self.channel.send(b'\r')
                    time.sleep(0.005)
            
            return True
            
        except Exception as e:
            self.logger.error(f"输出发送失败: {e}")
            return False
    
    def _send_newline(self) -> bool:
        """发送换行符 - 修复版本，确保光标回到行首"""
        try:
            if not self._check_channel_status():
                return False
            
            # 发送回车+换行，确保光标在行首
            encoded_chars = b'\r\n'
            self.channel.send(encoded_chars)
            
            # 短暂等待，确保传输完成
            time.sleep(0.01)
            
            return True
            
        except Exception as e:
            self.logger.error(f"换行符发送失败: {e}")
            return False
    
    def _send_char_echo(self, char: str) -> bool:
        """发送字符回显 - 修复版本，不添加换行符"""
        try:
            if not self._check_channel_status():
                return False
            
            # 直接发送字符，不添加换行符
            encoded_char = char.encode('utf-8')
            self.channel.send(encoded_char)
            
            # 短暂等待，确保字符传输完成
            time.sleep(0.01)
            
            return True
            
        except Exception as e:
            self.logger.error(f"字符回显失败: {e}")
            return False
    
    def _send_command_output_newline(self) -> bool:
        """发送命令输出后的换行符 - 确保光标回到行首"""
        try:
            if not self._check_channel_status():
                return False
            
            # 发送回车+换行，确保光标回到行首
            encoded_chars = b'\r\n'
            self.channel.send(encoded_chars)
            
            # 短暂等待，确保传输完成
            time.sleep(0.01)
            
            return True
            
        except Exception as e:
            self.logger.error(f"命令输出换行符发送失败: {e}")
            return False
    
    def _cleanup(self):
        """清理资源"""
        try:
            # 设置运行标志为False
            self.running = False
            
            # 清理会话
            if self.current_session:
                try:
                    # 从会话管理器中移除会话
                    if hasattr(self, 'session_manager'):
                        self.session_manager.remove_session(self.current_session.session_id)
                    self.logger.debug(f"会话已清理: {self.current_session.session_id}")
                except Exception as e:
                    self.logger.warning(f"清理会话时出错: {e}")
            
            # 清理输入缓冲区
            self.input_buffer = ""
            self.history.clear()
            
            # 关闭SSH通道（如果可用）
            if hasattr(self, 'channel') and self.channel:
                try:
                    if not self.channel.closed:
                        self.channel.close()
                        self.logger.debug("SSH通道已关闭")
                except Exception as e:
                    self.logger.warning(f"关闭SSH通道时出错: {e}")
        except Exception as e:
            self.logger.error(f"清理SSH控制台资源时出错: {e}")

    def _get_game_state(self) -> Dict[str, Any]:
        """从场景引擎管理器获取场景状态"""
        try:
            from app.game_engine.manager import game_engine_manager
            
            # 获取场景引擎
            engine = game_engine_manager.get_engine()
            if not engine:
                return {
                    'is_running': False,
                    'current_game': None,
                    'game_info': {}
                }
            
            # 通过GameInterface获取场景状态
            game_status = engine.interface.get_game_status('campus_life')
            if game_status:
                return {
                    'is_running': game_status.get('is_running', False),
                    'current_game': 'campus_life',
                    'game_info': game_status
                }
            else:
                return {
                    'is_running': False,
                    'current_game': None,
                    'game_info': {}
                }
                
        except Exception as e:
            self.logger.error(f"从场景引擎获取状态失败: {e}")
            return {
                'is_running': False,
                'current_game': None,
                'game_info': {'error': str(e)}
            }
