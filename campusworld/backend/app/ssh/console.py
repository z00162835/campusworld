"""
SSH控制台模块
提供命令行交互界面，集成现有命令系统
"""

import re
import logging
import threading
import time
import select
import queue
from typing import Optional, List, Dict, Any
from datetime import datetime
import os

import paramiko

from app.ssh.session import SSHSession
from app.ssh.commands import SSHCommandRegistry, SSHCommand, register_builtin_commands
from app.ssh.progress import StatusDisplay
from app.core.permissions import permission_checker


class SSHConsole:
    """SSH控制台 - 事件驱动模式，支持自适应终端"""
    
    def __init__(self, channel, session: Optional[SSHSession] = None):
        """初始化SSH控制台"""
        self.channel = channel
        self.current_session = session
        self.running = True
        self.debug_mode = os.getenv('SSH_DEBUG', 'false').lower() == 'true'
        
        # 配置日志系统
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        # 初始化命令注册表
        self.command_registry = SSHCommandRegistry()
        register_builtin_commands(self.command_registry)
        
        # 初始化其他组件
        self.input_buffer = ""
        self.command_history = []
        self.history_index = 0
        self.terminal_width = 80
        self.terminal_height = 24
        
        # 初始化状态显示
        self.status_display = StatusDisplay(channel)
        
        self.logger.info("SSH Console initialized in DEBUG mode (Event-Driven + Adaptive Terminal)")
        self.logger.info(f"Terminal size: {self.terminal_width}x{self.terminal_height}")
        self.logger.info(f"Command registry contains {len(self.command_registry.get_all_commands())} commands")
    
    def _setup_logging(self):
        """配置日志系统 - 减少冗余日志"""
        if self.debug_mode:
            # DEBUG模式：详细日志
            self.logger.setLevel(logging.DEBUG)
        else:
            # 生产模式：只记录重要信息
            self.logger.setLevel(logging.INFO)
            # 过滤掉DEBUG级别的日志
            self.logger.addFilter(lambda record: record.levelno >= logging.INFO)
    
    def _detect_terminal_width(self) -> int:
        """检测终端宽度"""
        try:
            # 尝试获取终端大小
            if hasattr(self.channel, 'get_pty'):
                # 如果有PTY，尝试获取大小
                return 80  # 默认宽度
            else:
                # 没有PTY，使用默认值
                return 80
        except:
            return 80  # 出错时使用默认值
    
    def _detect_terminal_height(self) -> int:
        """检测终端高度"""
        try:
            if hasattr(self.channel, 'get_pty'):
                return 24  # 默认高度
            else:
                return 24
        except:
            return 24
    
    def _should_use_unicode(self) -> bool:
        """判断是否应该使用Unicode字符 - 优化版本"""
        try:
            # 更全面的兼容性检测
            test_chars = ['★', '┌', '─', '│', '┐']
            for char in test_chars:
                self.channel.send(char.encode('utf-8'))
            return True
        except Exception as e:
            self.logger.debug(f"Unicode检测失败: {e}")
            return False
    
    def _get_charset(self):
        """获取字符集 - 简化版本"""
        if self._should_use_unicode():
            return self._get_compatible_chars()
        else:
            return self._get_ascii_fallback()
    
    def _get_compatible_chars(self) -> dict:
        """获取兼容的Unicode字符集 - 完整版本"""
        return {
            # 基础符号
            'sparkles': '✨',
            'book': '📚',
            'lightbulb': '💡',
            'link': '🔗',
            'clock': '🕐',
            'gear': '⚙️',
            'rocket': '🚀',
            'game': '🎮',
            'user': '👤',
            'system': '🖥',
            'status': '📊',
            'error': '❌',
            'warning': '⚠️',
            'success': '✅',
            'cross_mark': '✗',
            'eyes': '👀',
            'fire': '🔥',
            'door': '🚪',
            'wave': '👋',
            'bullet': '•',
            
            # 边框字符
            'top_left': '┌',
            'top_right': '┐',
            'bottom_left': '└',
            'bottom_right': '┘',
            'horizontal': '─',
            'vertical': '│',
            't_down': '┬',
            't_up': '┴',
            't_left': '├',
            't_right': '┤',
            'cross': '┼'
        }
    
    def _get_ascii_fallback(self) -> dict:
        """获取ASCII回退字符集 - 完整版本"""
        return {
            # 基础符号
            'sparkles': '***',
            'book': '[B]',
            'lightbulb': '[I]',
            'link': '[L]',
            'clock': '[T]',
            'gear': '[G]',
            'rocket': '[R]',
            'game': '[G]',
            'user': '[U]',
            'system': '[S]',
            'status': '[T]',
            'error': '[E]',
            'warning': '[W]',
            'success': '[OK]',
            'cross_mark': '[X]',
            'eyes': '[E]',
            'fire': '[F]',
            'door': '[D]',
            'wave': '[W]',
            'bullet': '*',
            
            # 边框字符
            'top_left': '+',
            'top_right': '+',
            'bottom_left': '+',
            'bottom_right': '+',
            'horizontal': '-',
            'vertical': '|',
            't_down': '+',
            't_up': '+',
            't_left': '+',
            't_right': '+',
            'cross': '+'
        }
    
    def get_session(self):
        """获取当前会话"""
        return self.current_session
    
    def _create_box(self, title: str, content: str, width: int = None) -> str:
        """创建自适应边框框 - 优化版本"""
        if width is None:
            width = min(self.terminal_width - 4, 76)  # 留出边距
        
        chars = self._get_charset()
        
        # 智能边框宽度调整
        if width < 20:
            width = 20  # 最小宽度
        elif width > 120:
            width = 120  # 最大宽度
        
        # 创建边框
        top_border = chars['top_left'] + chars['horizontal'] * (width - 2) + chars['top_right']
        bottom_border = chars['bottom_left'] + chars['horizontal'] * (width - 2) + chars['bottom_right']
        
        # 创建标题行 - 智能截断
        title_display = title[:width-4] if len(title) > width-4 else title
        title_line = chars['vertical'] + ' ' + title_display.center(width - 2) + ' ' + chars['vertical']
        
        # 创建内容行 - 智能换行
        content_lines = []
        for line in content.split('\n'):
            if line.strip():
                # 智能换行处理
                remaining_line = line.strip()
                while len(remaining_line) > width - 4:
                    # 尝试在空格处换行
                    split_pos = width - 4
                    for i in range(width - 4, max(0, width - 20), -1):
                        if remaining_line[i] == ' ':
                            split_pos = i
                            break
                    
                    content_lines.append(chars['vertical'] + ' ' + remaining_line[:split_pos].ljust(width-4) + ' ' + chars['vertical'])
                    remaining_line = remaining_line[split_pos:].strip()
                
                if remaining_line:
                    content_lines.append(chars['vertical'] + ' ' + remaining_line.ljust(width-4) + ' ' + chars['vertical'])
            else:
                content_lines.append(chars['vertical'] + ' ' * width + chars['vertical'])
        
        # 组装结果
        result = [top_border, title_line]
        result.extend(content_lines)
        result.append(bottom_border)
        
        return '\n'.join(result)
    
    def _create_table(self, headers: List[str], rows: List[List[str]], title: str = None) -> str:
        """创建自适应表格 - 优化版本"""
        if not headers or not rows:
            return ""
        
        chars = self._get_charset()
        
        # 计算列宽 - 智能分配
        col_widths = []
        for i, header in enumerate(headers):
            max_width = len(header)
            for row in rows:
                if i < len(row):
                    max_width = max(max_width, len(str(row[i])))
            col_widths.append(max_width)
        
        # 智能调整总宽度以适应终端
        total_width = sum(col_widths) + len(headers) + 1
        if total_width > self.terminal_width - 4:
            # 需要压缩 - 按比例分配
            available_width = self.terminal_width - 4 - len(headers) - 1
            if available_width < len(headers) * 5:  # 最小列宽
                available_width = len(headers) * 5
            
            # 按比例压缩各列
            total_current = sum(col_widths)
            for i in range(len(col_widths)):
                col_widths[i] = max(5, int(col_widths[i] * available_width / total_current))
        
        # 创建表格
        table = []
        if title:
            table.append(title)
            table.append('')
        
        # 表头
        header_line = chars['t_right']
        for i, header in enumerate(headers):
            header_line += chars['horizontal'] * (col_widths[i] + 2) + chars['t_down']
        table.append(header_line)
        
        # 表头内容
        header_content = chars['vertical']
        for i, header in enumerate(headers):
            header_content += ' ' + header.center(col_widths[i]) + ' ' + chars['vertical']
        table.append(header_content)
        
        # 分隔线
        separator = chars['t_right']
        for i in range(len(headers)):
            separator += chars['horizontal'] * (col_widths[i] + 2) + chars['cross']
        separator = separator[:-1] + chars['t_left']
        table.append(separator)
        
        # 数据行 - 智能换行
        for row in rows:
            # 计算行高（考虑换行）
            max_lines = 1
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    cell_str = str(cell)
                    lines_needed = (len(cell_str) + col_widths[i] - 1) // col_widths[i]
                    max_lines = max(max_lines, lines_needed)
            
            # 创建多行数据
            for line_num in range(max_lines):
                row_line = chars['vertical']
                for i, cell in enumerate(row):
                    if i < len(col_widths):
                        cell_str = str(cell)
                        start_pos = line_num * col_widths[i]
                        end_pos = start_pos + col_widths[i]
                        cell_line = cell_str[start_pos:end_pos]
                        row_line += ' ' + cell_line.ljust(col_widths[i]) + ' ' + chars['vertical']
                table.append(row_line)
        
        # 底部边框
        bottom_line = chars['t_up']
        for i in range(len(headers)):
            bottom_line += chars['horizontal'] * (col_widths[i] + 2) + chars['t_up']
        bottom_line = bottom_line[:-1] + chars['t_left']
        table.append(bottom_line)
        
        return '\n'.join(table)
    
    def run(self):
        """运行控制台 - 简化版本"""
        try:
            self.logger.info("开始运行SSH控制台")
            self.running = True
            
            # 显示欢迎信息
            self._display_welcome()
            
            # 显示初始提示符
            self._display_prompt()
            
            # 主循环 - 简化版本
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
            self.logger.info("控制台运行结束")
            self._cleanup()
    
    def _display_welcome(self):
        """显示欢迎信息 - 简化版本"""
        # 创建简单的欢迎信息，避免复杂字符
        welcome_lines = [
            "Welcome to CampusWorld!",
            "",
            "Available Commands:",
            "  help     - Show available commands",
            "  system   - Show system information", 
            "  user     - Show user information",
            "  status   - Show system status",
            "  exit     - Disconnect from console",
            "",
            "Type 'help' for detailed information",
            f"Connected as: {self.current_session.username if self.current_session else 'Guest'}",
            f"Session started: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Terminal: {self.terminal_width}x{self.terminal_height}",
            "Ready for adventure!",
            ""
        ]
        
        # 逐行发送欢迎信息
        for line in welcome_lines:
            self._safe_send_output(line)
        
        # 验证命令注册表状态
        self.logger.info(f"Console initialized with {len(self.command_registry.get_all_commands())} commands")
        help_cmd = self.command_registry.get_command("help")
        if help_cmd:
            self.logger.info(f"Help command available: {help_cmd.name}")
        else:
            self.logger.error("Help command not found in registry!")
    
    def _display_prompt(self):
        """显示提示符 - 简化版本"""
        if self.current_session:
            username = self.current_session.username
            timestamp = time.strftime('%H:%M:%S')
            prompt = f"[{username}@{timestamp}] campusworld> "
        else:
            timestamp = time.strftime('%H:%M:%S')
            prompt = f"[Guest@{timestamp}] campusworld> "
        
        # 发送提示符 - 使用专门的提示符发送方法
        self._send_prompt(prompt)
    
    def _send_prompt(self, prompt: str) -> bool:
        """发送提示符 - 不添加换行符"""
        try:
            if not self._check_channel_status():
                return False
            
            # 直接发送提示符，不添加换行符
            encoded_prompt = prompt.encode('utf-8')
            self.channel.send(encoded_prompt)
            
            # 短暂等待，确保提示符传输完成
            time.sleep(0.01)
            
            self.logger.debug(f"提示符发送成功: {repr(prompt)}")
            return True
            
        except Exception as e:
            self.logger.error(f"提示符发送失败: {e}")
            return False
    
    def _start_event_thread(self):
        """启动事件处理线程 - 简化版本"""
        # 不再需要复杂的线程管理
        self.logger.info("事件处理线程已简化，使用同步处理")
    
    def _process_output_events(self):
        """处理输出事件 - 修复版本"""
        try:
            while self.running:
                try:
                    # 获取输出消息
                    message = self.output_queue.get(timeout=0.1)
                    if message is None:
                        continue
                    
                    # 发送输出
                    if self._safe_send_output(message):
                        self.logger.debug(f"输出事件处理成功: {len(message)} 字符")
                    else:
                        self.logger.warning(f"输出事件处理失败: {len(message)} 字符")
                        
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"输出事件处理错误: {e}")
                    
        except Exception as e:
            self.logger.error(f"输出事件处理线程错误: {e}")
        finally:
            self.logger.info("输出事件处理线程退出")
    
    def _process_raw_input(self):
        """处理原始输入数据 - 简化版本"""
        try:
            # 使用select进行非阻塞检查
            ready, _, _ = select.select([self.channel], [], [], 0.01)
            if ready:
                # 有数据可读
                data = self.channel.recv(1024)
                if data:
                    self.logger.info(f"接收到数据: {repr(data)}")
                    # 解码数据
                    text = data.decode('utf-8', errors='ignore')
                    self.logger.info(f"解码后文本: {repr(text)}")
                    self._process_raw_input_chars(text)
                    
        except Exception as e:
            if "timeout" not in str(e).lower():
                self.logger.debug(f"非阻塞读取错误: {e}")
    
    def _process_raw_input_chars(self, raw_input: str):
        """处理原始输入字符 - 优化日志版本"""
        if self.debug_mode:
            self.logger.debug(f"处理原始输入: {repr(raw_input)}")
        
        for char in raw_input:
            if self.debug_mode:
                self.logger.debug(f"处理字符: {repr(char)}")
            
            if char == '\r' or char == '\n':  # 同时处理回车符和换行符
                # 输入完成，提交命令
                if self.input_buffer.strip():
                    command = self.input_buffer.strip()
                    self.logger.info(f"提交命令: '{command}'")
                    # 发送换行符，确保命令输入完成
                    self._send_char_echo('\n')
                    # 直接处理命令，不使用队列
                    self._process_input(command)
                else:
                    self.logger.debug("空命令，忽略")
                    # 空命令使用专门的换行方法，确保光标正确定位
                    self._send_newline()
                    # 显示新提示符
                    self._display_prompt()
            elif char == '\b' or char == '\x7f':  # Backspace
                if self.input_buffer:
                    self.input_buffer = self.input_buffer[:-1]
                    if self.debug_mode:
                        self.logger.debug(f"退格处理，当前缓冲: '{self.input_buffer}'")
                    # 发送退格序列 - 使用字符回显方法
                    self._send_char_echo('\b')
                    self._send_char_echo(' ')
                    self._send_char_echo('\b')
                else:
                    if self.debug_mode:
                        self.logger.debug("退格处理，但缓冲已空")
            elif char == '\x03':  # Ctrl+C
                self.logger.info("检测到Ctrl+C，清空输入缓冲")
                self.input_buffer = ""
                # 发送换行符
                self._send_char_echo('\n')
                # 显示Ctrl+C消息
                ctrl_c_msg = f"Command cancelled (Ctrl+C)\n"
                self._safe_send_output(ctrl_c_msg)
                # 显示新提示符
                self._display_prompt()
            elif char == '\x04':  # Ctrl+D
                self.logger.info("检测到Ctrl+D，退出控制台")
                self.input_buffer = ""
                # 发送换行符
                self._send_char_echo('\n')
                # 显示Ctrl+D消息
                ctrl_d_msg = f"Disconnecting (Ctrl+D)\n"
                self._safe_send_output(ctrl_d_msg)
                self.running = False
            else:
                self.input_buffer += char
                if self.debug_mode:
                    self.logger.debug(f"添加字符到缓冲，当前缓冲: '{self.input_buffer}'")
                # 回显字符 - 使用专门的字符回显方法
                self._send_char_echo(char)
        
        if self.debug_mode:
            self.logger.debug(f"输入处理完成，当前缓冲: '{self.input_buffer}'")
        
        # 额外的安全检查：确保输入缓冲区状态一致
        if not self.input_buffer and hasattr(self, '_last_command_time'):
            # 如果缓冲区为空但之前有命令执行，记录状态
            if self.debug_mode:
                self.logger.debug("输入缓冲区状态检查：缓冲区为空，状态正常")
        elif self.input_buffer and len(self.input_buffer) > 100:
            # 如果缓冲区过大，可能是异常状态，强制清理
            self.logger.warning(f"输入缓冲区异常过大({len(self.input_buffer)})，强制清理")
            self.input_buffer = ""
    
    def _process_input(self, input_text: str):
        """处理输入 - 优化日志版本"""
        try:
            if self.debug_mode:
                self.logger.debug(f"开始处理输入: '{input_text}'")
            
            # 添加到历史记录
            if input_text.strip():
                self.command_history.append(input_text)
                self.history_index = len(self.command_history)
                if self.debug_mode:
                    self.logger.debug(f"输入已添加到历史记录，当前历史长度: {len(self.command_history)}")
            
            # 解析命令
            parts = input_text.strip().split()
            if not parts:
                self.logger.warning("空命令输入")
                return
            
            command_name = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            if self.debug_mode:
                self.logger.debug(f"命令解析: 名称='{command_name}', 参数={args}")
            
            # 执行命令
            self._execute_command(command_name, args)
            
            if self.debug_mode:
                self.logger.debug(f"输入处理完成: '{input_text}'")
            
        except Exception as e:
            self.logger.error(f"输入处理错误: {e}")
            # 发送错误消息
            error_msg = f"Input processing error: {str(e)}\n"
            self._safe_send_output(error_msg)
            # 显示新提示符 - 只在需要时显示
            if self.running:
                self._display_prompt()
        finally:
            # 确保输入缓冲区被清空，防止命令拼接问题
            self.input_buffer = ""
            if self.debug_mode:
                self.logger.debug(f"输入缓冲区已清空，当前状态: '{self.input_buffer}'")
    
    def _execute_command(self, command_name: str, args: List[str]):
        """执行命令 - 优化日志版本"""
        try:
            if self.debug_mode:
                self.logger.debug(f"开始执行命令: {command_name}")
            
            # 查找命令
            command = self.command_registry.get_command(command_name)
            
            if not command:
                self.logger.warning(f"命令未找到: {command_name}")
                # 发送命令未找到消息
                not_found_msg = self._beautify_command_not_found(command_name)
                self._safe_send_output(not_found_msg)
                if self.debug_mode:
                    self.logger.debug("命令未找到消息已发送")
                # 显示新提示符 - 只在需要时显示
                if self.running:
                    self._display_prompt()
                return
            
            if self.debug_mode:
                self.logger.debug(f"命令查找成功: {command_name}")
            
            # 权限检查
            if not self._check_command_permission(command, args):
                self.logger.warning(f"权限检查失败: {command_name}")
                # 发送权限拒绝消息
                permission_msg = f"Permission denied for command '{command_name}'.\n"
                self._safe_send_output(permission_msg)
                if self.debug_mode:
                    self.logger.debug("权限拒绝消息已发送")
                # 显示新提示符 - 只在需要时显示
                if self.running:
                    self._display_prompt()
                return
            
            if self.debug_mode:
                self.logger.debug("权限检查通过，开始执行命令")
            
            # 执行命令
            result = command.execute(self, args)
            
            if result:
                if self.debug_mode:
                    self.logger.debug(f"命令执行完成，结果长度: {len(str(result))}")
                
                # 美化输出
                beautified_result = self._beautify_command_output(command_name, result)
                # 发送命令输出
                self._safe_send_output(beautified_result)
                if self.debug_mode:
                    self.logger.debug("命令输出已发送")
            else:
                if self.debug_mode:
                    self.logger.debug("命令执行成功，但没有输出")
                # 即使没有输出，也发送确认消息
                success_msg = f"Command '{command_name}' executed successfully.\n"
                self._safe_send_output(success_msg)
                if self.debug_mode:
                    self.logger.debug("成功消息已发送")
            
            if self.debug_mode:
                self.logger.debug(f"命令执行完成: {command_name}")
            
            # 命令执行成功后显示提示符
            if self.running:
                self._display_prompt()
            
            # 确保输入缓冲区被清理
            self._clear_input_buffer()
        
        except Exception as e:
            self.logger.error(f"命令执行错误: {e}")
            # 发送错误消息
            error_msg = self._beautify_error_output(command_name, e)
            self._safe_send_output(error_msg)
            if self.debug_mode:
                self.logger.debug("错误消息已发送")
            
            # 命令执行错误后显示提示符
            if self.running:
                self._display_prompt()
            
            # 确保输入缓冲区被清理
            self._clear_input_buffer()
        
        finally:
            # 确保在所有情况下都显示提示符（如果还没有显示的话）
            # 这里作为最后的保障，避免提示符丢失
            # 同时确保输入缓冲区被清空，防止命令拼接问题
            self.input_buffer = ""
            if self.debug_mode:
                self.logger.debug(f"命令执行完成，输入缓冲区已清空: '{self.input_buffer}'")
    
    def _normalize_output_format(self, result: str) -> str:
        """标准化输出格式 - 确保第一行居左对齐"""
        try:
            if not result or not result.strip():
                return result
            
            # 按行分割
            lines = result.strip().split('\n')
            if not lines:
                return result
            
            # 处理第一行，确保居左对齐
            first_line = lines[0].strip()
            if first_line:
                lines[0] = first_line
            
            # 处理后续行，保持原有格式
            normalized_lines = []
            for i, line in enumerate(lines):
                if i == 0:
                    # 第一行居左对齐
                    normalized_lines.append(line)
                else:
                    # 后续行保持原有格式
                    normalized_lines.append(line)
            
            # 重新组合
            normalized_result = '\n'.join(normalized_lines)
            
            # 确保结果以换行符结尾
            if not normalized_result.endswith('\n'):
                normalized_result += '\n'
            
            return normalized_result
            
        except Exception as e:
            self.logger.error(f"输出格式标准化失败: {e}")
            return result
    
    def _get_beautify_strategy(self, command_name: str):
        """获取美化策略 - 策略模式实现"""
        # 定义美化策略映射
        strategies = {
            'help': self._beautify_help_output_simple,
            'system': self._beautify_system_output_simple,
            'user': self._beautify_user_output_simple,
            'status': self._beautify_status_output_simple,
            'who': self._beautify_who_output_simple,
            'history': self._beautify_history_output_simple,
            'date': self._beautify_date_output_simple,
            'version': self._beautify_version_output_simple,
            'config': self._beautify_config_output_simple,
            'permission': self._beautify_permission_output_simple,
            'sessions': self._beautify_sessions_output_simple,
            'alias': self._beautify_alias_output_simple,
        }
        
        # 返回对应的策略函数，如果没有找到则返回默认策略
        return strategies.get(command_name, self._beautify_default_output)
    
    def _beautify_default_output(self, result: str) -> str:
        """默认美化策略 - 直接标准化输出"""
        return self._normalize_output_format(result)
    
    def _beautify_command_output(self, command_name: str, result: str) -> str:
        """美化命令输出格式 - 策略模式版本"""
        # 获取对应的美化策略
        strategy = self._get_beautify_strategy(command_name)
        
        # 执行美化策略
        try:
            beautified_result = strategy(result)
            if self.debug_mode:
                self.logger.debug(f"命令 '{command_name}' 使用策略 '{strategy.__name__}' 美化完成")
            return beautified_result
        except Exception as e:
            self.logger.error(f"美化策略执行失败: {e}")
            # 降级到默认策略
            return self._beautify_default_output(result)
    
    def _beautify_with_title(self, result: str, title: str, check_start: str = None) -> str:
        """通用标题美化方法 - 减少重复代码"""
        # 检查结果是否已经包含标题，避免重复
        if check_start and result.strip().startswith(check_start):
            return self._normalize_output_format(result)
        
        # 确保第一行居左对齐
        formatted_result = f"{title}\n{result}"
        return self._normalize_output_format(formatted_result)
    
    def _beautify_help_output_simple(self, result: str) -> str:
        """美化帮助命令输出 - 简化版本"""
        # 检查结果是否已经包含标题，避免重复
        if result.strip().startswith("Available Commands:"):
            return self._normalize_output_format(result)
        
        lines = result.split('\n')
        output_lines = []
        
        # 第一行居左对齐
        output_lines.append("Available Commands:")
        output_lines.append("")
        
        for line in lines:
            if line.strip() and ' - ' in line:
                parts = line.split(' - ', 1)
                if len(parts) == 2:
                    cmd, desc = parts
                    output_lines.append(f"  {cmd.strip():<15} - {desc.strip()}")
        
        result = '\n'.join(output_lines)
        return self._normalize_output_format(result)
    
    def _beautify_system_output_simple(self, result: str) -> str:
        """美化系统信息输出 - 简化版本"""
        return self._beautify_with_title(result, "System Information:", "System Information:")
    
    def _beautify_user_output_simple(self, result: str) -> str:
        """美化用户信息输出 - 简化版本"""
        return self._beautify_with_title(result, "User Information:", "User Information:")
    
    def _beautify_status_output_simple(self, result: str) -> str:
        """美化状态信息输出 - 简化版本"""
        return self._beautify_with_title(result, "System Status:", "System Status:")
    
    def _beautify_who_output_simple(self, result: str) -> str:
        """美化who命令输出 - 确保第一行居左对齐"""
        return self._normalize_output_format(result)
    
    def _beautify_history_output_simple(self, result: str) -> str:
        """美化历史记录输出 - 确保第一行居左对齐"""
        return self._normalize_output_format(result)
    
    def _beautify_date_output_simple(self, result: str) -> str:
        """美化日期时间输出 - 确保第一行居左对齐"""
        return self._normalize_output_format(result)
    
    def _beautify_version_output_simple(self, result: str) -> str:
        """美化版本信息输出 - 确保第一行居左对齐"""
        return self._normalize_output_format(result)
    
    def _beautify_config_output_simple(self, result: str) -> str:
        """美化配置信息输出 - 确保第一行居左对齐"""
        return self._normalize_output_format(result)
    
    def _beautify_permission_output_simple(self, result: str) -> str:
        """美化权限检查输出 - 确保第一行居左对齐"""
        return self._normalize_output_format(result)
    
    def _beautify_sessions_output_simple(self, result: str) -> str:
        """美化会话信息输出 - 确保第一行居左对齐"""
        return self._normalize_output_format(result)
    
    def _beautify_alias_output_simple(self, result: str) -> str:
        """美化别名管理输出 - 确保第一行居左对齐"""
        return self._normalize_output_format(result)
    
    def _beautify_error_output(self, command_name: str, error: Exception) -> str:
        """美化错误输出 - 确保第一行居左对齐"""
        result = f"Error executing command '{command_name}': {str(error)}"
        return self._normalize_output_format(result)
    
    def _beautify_command_not_found(self, command_name: str) -> str:
        """美化命令未找到输出 - 确保第一行居左对齐"""
        result = f"Command '{command_name}' was not found. Type 'help' for available commands."
        return self._normalize_output_format(result)
    
    def _beautify_system_error(self, error: Exception) -> str:
        """美化系统错误输出 - 确保第一行居左对齐"""
        result = f"System Error: {str(error)}"
        return self._normalize_output_format(result)
    
    def _check_command_permission(self, command: 'SSHCommand', args: List[str]) -> bool:
        """检查命令权限 - 参考Evennia框架简化设计"""
        # 简化权限检查：所有基本命令都允许执行
        # 参考Evennia：基本命令不需要复杂权限验证
        
        # 如果没有会话，允许执行基本命令
        if not self.current_session:
            # 允许所有基本命令
            return True
        
        # 如果有会话，检查命令是否需要特定权限
        if command.required_permission:
            try:
                return permission_checker.check_permission(
                    self.current_session.roles, 
                    command.required_permission
                )
            except Exception as e:
                self.logger.warning(f"Permission check error: {e}")
                # 权限检查失败时，默认允许执行
                return True
        
        # 检查命令是否需要特定角色
        if command.required_role:
            try:
                return permission_checker.check_role(
                    self.current_session.roles, 
                    command.required_role
                )
            except Exception as e:
                self.logger.warning(f"Role check error: {e}")
                # 角色检查失败时，默认允许执行
                return True
        
        # 检查命令是否需要特定访问级别
        if command.required_access_level:
            try:
                return permission_checker.check_access_level(
                    self.current_session.access_level, 
                    command.required_access_level
                )
            except Exception as e:
                self.logger.warning(f"Access level check error: {e}")
                # 访问级别检查失败时，默认允许执行
                return True
        
        # 默认允许执行
        return True
    
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
        """安全发送输出 - 单行输出版本"""
        try:
            if not self._check_channel_status():
                self.logger.warning("通道状态检查失败，无法发送输出")
                return False
            
            # 将消息按行分割
            lines = message.split('\n')
            
            # 逐行发送，确保每行都是完整的
            for i, line in enumerate(lines):
                if line.strip():  # 跳过空行
                    # 确保每行以换行符结尾
                    if not line.endswith('\r\n') and not line.endswith('\n'):
                        line += '\r\n'
                    else:
                        line += '\r\n'  # 统一使用 \r\n
                    
                    # 编码并发送单行
                    encoded_line = line.encode('utf-8')
                    self.channel.send(encoded_line)
                    
                    # 等待输出完成
                    time.sleep(0.02)
                    
                    if self.debug_mode:
                        self.logger.debug(f"行 {i+1} 发送成功: {len(encoded_line)} 字节")
            
            return True
            
        except Exception as e:
            self.logger.error(f"输出发送失败: {e}")
            return False
    
    def _send_newline(self) -> bool:
        """发送换行符并重置光标位置 - 确保prompt居左对齐"""
        try:
            if not self._check_channel_status():
                return False
            
            # 发送回车+换行，确保光标在行首
            encoded_chars = b'\r\n'
            self.channel.send(encoded_chars)
            
            # 短暂等待，确保传输完成
            time.sleep(0.01)
            
            if self.debug_mode:
                self.logger.debug("换行符发送成功，光标位置已重置")
            return True
            
        except Exception as e:
            self.logger.error(f"换行符发送失败: {e}")
            return False
    
    def _clear_input_buffer(self):
        """清理输入缓冲区 - 防止命令拼接问题"""
        try:
            old_buffer = self.input_buffer
            self.input_buffer = ""
            if self.debug_mode:
                self.logger.debug(f"输入缓冲区已清理，原内容: '{old_buffer}'")
            return True
        except Exception as e:
            self.logger.error(f"输入缓冲区清理失败: {e}")
            return False
    
    def _send_char_echo(self, char: str) -> bool:
        """发送字符回显 - 不添加换行符"""
        try:
            if not self._check_channel_status():
                return False
            
            # 直接发送字符，不添加换行符
            encoded_char = char.encode('utf-8')
            self.channel.send(encoded_char)
            
            # 短暂等待，确保字符传输完成
            time.sleep(0.01)
            
            if self.debug_mode:
                self.logger.debug(f"字符回显成功: {repr(char)}")
            return True
            
        except Exception as e:
            self.logger.error(f"字符回显失败: {e}")
            return False
    
    def _cleanup(self):
        """清理资源"""
        try:
            self.running = False
            self.logger.info("Console cleanup completed")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def set_session(self, session: SSHSession):
        """设置会话"""
        self.current_session = session
        if session:
            self.logger.info(f"Session set for user: {session.username}")
        else:
            self.logger.info("Session cleared")
