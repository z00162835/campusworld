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

import paramiko

from app.ssh.session import SSHSession
from app.ssh.commands import SSHCommandRegistry, SSHCommand, register_builtin_commands
from app.ssh.progress import StatusDisplay
from app.core.permissions import permission_checker


class SSHConsole:
    """SSH控制台 - 事件驱动模式，支持自适应终端"""
    
    def __init__(self, channel, session=None):
        self.channel = channel
        self.current_session = session
        self.command_registry = SSHCommandRegistry()
        self.status_display = StatusDisplay(channel)  # 传递channel参数
        self.logger = logging.getLogger(__name__)
        
        # 注册内置命令
        register_builtin_commands(self.command_registry)
        
        # 调试：验证命令注册
        self.logger.info(f"命令注册完成，注册表包含 {len(self.command_registry.get_all_commands())} 个命令")
        for cmd in self.command_registry.get_all_commands():
            self.logger.info(f"已注册命令: {cmd.name} - {cmd.description}")
        
        # 输入输出队列
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        
        # 事件处理线程
        self.event_thread = None
        
        # 输入缓冲和历史
        self.input_buffer = ""
        self.command_history = []
        self.history_index = 0
        
        # 终端信息
        self.terminal_width = self._detect_terminal_width()
        self.terminal_height = self._detect_terminal_height()
        
        # 运行状态
        self.running = False
        self.prompt = "campusworld> "
        
        # 设置非阻塞模式
        self.channel.settimeout(0)
        
        self.logger.info("SSH Console initialized in DEBUG mode (Event-Driven + Adaptive Terminal)")
        self.logger.info(f"Terminal size: {self.terminal_width}x{self.terminal_height}")
        self.logger.info(f"Command registry contains {len(self.command_registry.get_all_commands())} commands")
    
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
    
    def _get_compatible_chars(self) -> dict:
        """获取兼容的Unicode字符集"""
        return {
            'top_left': '┌',
            'top_right': '┐',
            'bottom_left': '└',
            'bottom_right': '┘',
            'horizontal': '─',
            'vertical': '│',
            'cross': '┼',
            't_down': '┬',
            't_up': '┴',
            't_right': '├',
            't_left': '┤',
            'arrow': '→',
            'bullet': '•',
            'check': '✓',
            'cross_mark': '✗',
            'warning': '⚠',
            'info': 'ℹ',
            'game': '🎮',
            'star': '★',
            'book': '📚',
            'user': '👤',
            'system': '🖥',
            'status': '📊',
            'error': '❌',
            'success': '✅',
            'lightbulb': '💡',
            'door': '🚪',
            'link': '🔗',
            'clock': '🕐'
        }
    
    def _get_ascii_fallback(self) -> dict:
        """获取ASCII回退字符集"""
        return {
            'top_left': '+',
            'top_right': '+',
            'bottom_left': '+',
            'bottom_right': '+',
            'horizontal': '-',
            'vertical': '|',
            'cross': '+',
            't_down': '+',
            't_up': '+',
            't_right': '+',
            't_left': '+',
            'arrow': '->',
            'bullet': '*',
            'check': 'OK',
            'cross_mark': 'X',
            'warning': '!',
            'info': 'i',
            'game': '[G]',
            'star': '*',
            'book': '[B]',
            'user': '[U]',
            'system': '[S]',
            'status': '[T]',
            'error': '[E]',
            'success': '[OK]',
            'lightbulb': '[I]',
            'door': '[D]',
            'link': '[L]',
            'clock': '[T]'
        }
    
    def _should_use_unicode(self) -> bool:
        """判断是否应该使用Unicode字符"""
        # 简单的兼容性检测
        try:
            # 尝试发送一个Unicode字符
            test_char = '★'
            self.channel.send(test_char.encode('utf-8'))
            return True
        except:
            return False
    
    def _get_charset(self) -> dict:
        """获取当前应该使用的字符集"""
        if self._should_use_unicode():
            return self._get_compatible_chars()
        else:
            return self._get_ascii_fallback()
    
    def get_session(self):
        """获取当前会话"""
        return self.current_session
    
    def _create_box(self, title: str, content: str, width: int = None) -> str:
        """创建自适应边框框"""
        if width is None:
            width = min(self.terminal_width - 4, 76)  # 留出边距
        
        chars = self._get_charset()
        
        # 创建边框
        top_border = chars['top_left'] + chars['horizontal'] * (width - 2) + chars['top_right']
        bottom_border = chars['bottom_left'] + chars['horizontal'] * (width - 2) + chars['bottom_right']
        
        # 创建标题行
        title_line = chars['vertical'] + ' ' + title.center(width - 2) + ' ' + chars['vertical']
        
        # 创建内容行
        content_lines = []
        for line in content.split('\n'):
            if line.strip():
                # 处理长行
                while len(line) > width - 4:
                    content_lines.append(chars['vertical'] + ' ' + line[:width-4] + ' ' + chars['vertical'])
                    line = line[width-4:]
                if line:
                    content_lines.append(chars['vertical'] + ' ' + line.ljust(width-4) + ' ' + chars['vertical'])
            else:
                content_lines.append(chars['vertical'] + ' ' * width + chars['vertical'])
        
        # 组装结果
        result = [top_border, title_line]
        result.extend(content_lines)
        result.append(bottom_border)
        
        return '\n'.join(result)
    
    def _create_table(self, headers: List[str], rows: List[List[str]], title: str = None) -> str:
        """创建自适应表格"""
        if not headers or not rows:
            return ""
        
        chars = self._get_charset()
        
        # 计算列宽
        col_widths = []
        for i, header in enumerate(headers):
            max_width = len(header)
            for row in rows:
                if i < len(row):
                    max_width = max(max_width, len(str(row[i])))
            col_widths.append(max_width)
        
        # 调整总宽度以适应终端
        total_width = sum(col_widths) + len(headers) + 1
        if total_width > self.terminal_width - 4:
            # 需要压缩
            excess = total_width - (self.terminal_width - 4)
            # 按比例压缩各列
            for i in range(len(col_widths)):
                if col_widths[i] > 10:  # 最小列宽
                    reduce = min(excess, col_widths[i] - 10)
                    col_widths[i] -= reduce
                    excess -= reduce
                    if excess <= 0:
                        break
        
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
        
        # 数据行
        for row in rows:
            row_line = chars['vertical']
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    cell_str = str(cell)[:col_widths[i]]
                    row_line += ' ' + cell_str.ljust(col_widths[i]) + ' ' + chars['vertical']
            table.append(row_line)
        
        # 底部边框
        bottom_line = chars['t_up']
        for i in range(len(headers)):
            bottom_line += chars['horizontal'] * (col_widths[i] + 2) + chars['t_up']
        bottom_line = bottom_line[:-1] + chars['t_left']
        table.append(bottom_line)
        
        return '\n'.join(table)
    
    def run(self):
        """运行控制台 - 事件驱动模式"""
        self.running = True
        
        try:
            # 显示欢迎信息
            self._display_welcome()
            
            # 启动事件处理线程
            self._start_event_thread()
            
            # 显示初始提示符
            self._display_prompt()
            
            # 主循环 - 非阻塞模式
            while self.running and not self.channel.closed:
                try:
                    # 处理输入事件
                    input_processed = self._process_input_events()
                    
                    # 处理输出事件
                    output_processed = self._process_output_events()
                    
                    # 如果没有任何事件处理，短暂休眠
                    if not input_processed and not output_processed:
                        time.sleep(0.01)
                    
                except Exception as e:
                    self.logger.error(f"Console error: {e}")
                    self.status_display.show_error(f"Console error: {e}")
                    
        except Exception as e:
            self.logger.error(f"Console run error: {e}")
        finally:
            self._cleanup()
    
    def _start_event_thread(self):
        """启动事件处理线程"""
        self.event_thread = threading.Thread(target=self._event_worker, daemon=True)
        self.event_thread.start()
        self.logger.info("事件处理线程已启动")
    
    def _event_worker(self):
        """事件处理工作线程"""
        self.logger.info("事件处理工作线程启动")
        
        while self.running:
            try:
                # 非阻塞读取输入
                self._non_blocking_read()
                
                # 短暂休眠，避免CPU占用过高
                time.sleep(0.01)
                
            except Exception as e:
                self.logger.error(f"事件处理线程错误: {e}")
                time.sleep(0.1)
        
        self.logger.info("事件处理工作线程退出")
    
    def _non_blocking_read(self):
        """非阻塞读取输入"""
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
                    self._process_raw_input(text)
                    
        except Exception as e:
            if "timeout" not in str(e).lower():
                self.logger.debug(f"非阻塞读取错误: {e}")
    
    def _process_raw_input(self, raw_input: str):
        """处理原始输入数据"""
        self.logger.info(f"处理原始输入: {repr(raw_input)}")
        
        for char in raw_input:
            self.logger.debug(f"处理字符: {repr(char)}")
            
            if char == '\r' or char == '\n':  # 同时处理回车符和换行符
                # 输入完成，提交命令
                if self.input_buffer.strip():
                    command = self.input_buffer.strip()
                    self.logger.info(f"检测到行结束符({repr(char)})，提交命令: '{command}'")
                    self.input_queue.put(command)
                    self.logger.info(f"命令已提交到队列: '{command}'")
                else:
                    self.logger.debug(f"检测到行结束符({repr(char)})，但输入缓冲为空")
                self.input_buffer = ""
            elif char == '\b' or char == '\x7f':  # Backspace
                if self.input_buffer:
                    self.input_buffer = self.input_buffer[:-1]
                    self.logger.debug(f"退格处理，当前缓冲: '{self.input_buffer}'")
                    # 发送退格序列
                    self.output_queue.put('\b \b')
                else:
                    self.logger.debug("退格处理，但缓冲已空")
            elif char == '\x03':  # Ctrl+C
                self.logger.info("检测到Ctrl+C，清空输入缓冲")
                self.input_buffer = ""
                # 美化Ctrl+C显示
                chars = self._get_charset()
                ctrl_c_msg = f"\n{chars['warning']} Command cancelled (Ctrl+C)\n"
                self.output_queue.put(ctrl_c_msg)
            elif char == '\x04':  # Ctrl+D
                self.logger.info("检测到Ctrl+D，退出控制台")
                self.input_buffer = ""
                # 美化Ctrl+D显示
                chars = self._get_charset()
                ctrl_d_msg = f"\n{chars['door']} Disconnecting (Ctrl+D)\n"
                self.output_queue.put(ctrl_d_msg)
                self.running = False
            else:
                self.input_buffer += char
                self.logger.debug(f"添加字符到缓冲，当前缓冲: '{self.input_buffer}'")
                # 回显字符
                self.output_queue.put(char)
        
        self.logger.debug(f"输入处理完成，当前缓冲: '{self.input_buffer}'")
    
    def _process_input_events(self):
        """处理输入事件"""
        processed_count = 0
        
        try:
            while not self.input_queue.empty():
                command_line = self.input_queue.get_nowait()
                self.logger.info(f"处理输入事件: '{command_line}'")
                self._process_input(command_line)
                
                # 命令处理完成后，重新显示提示符
                self._display_prompt()
                
                processed_count += 1
                
        except queue.Empty:
            pass
        except Exception as e:
            self.logger.error(f"输入事件处理错误: {e}")
        
        if processed_count > 0:
            self.logger.info(f"处理了 {processed_count} 个输入事件")
        
        return processed_count > 0
    
    def _process_output_events(self):
        """处理输出事件"""
        processed_count = 0
        
        try:
            while not self.output_queue.empty():
                output = self.output_queue.get_nowait()
                if self._safe_send_output(output):
                    self.logger.debug(f"输出事件处理成功: {repr(output[:50])}")
                    processed_count += 1
                else:
                    self.logger.error(f"输出事件处理失败: {repr(output[:50])}")
                    
        except queue.Empty:
            pass
        except Exception as e:
            self.logger.error(f"输出事件处理错误: {e}")
        
        if processed_count > 0:
            self.logger.debug(f"处理了 {processed_count} 个输出事件")
        
        return processed_count > 0
    
    def _display_welcome(self):
        """显示欢迎信息 - 自适应版本"""
        chars = self._get_charset()
        
        # 创建欢迎内容
        welcome_content = f"""
{chars['star']} Welcome to the CampusWorld Interactive Gaming Platform!

{chars['book']} Available Commands:
{chars['bullet']} help     - Show available commands and help information
{chars['bullet']} system   - Display system information and status
{chars['bullet']} user     - Show current user information and permissions
{chars['bullet']} status   - Display game world status and statistics
{chars['bullet']} exit     - Disconnect from the console

{chars['lightbulb']} Type 'help' for detailed command information
{chars['door']} Type 'exit' or 'quit' to disconnect

{chars['link']} Connected as: {self.current_session.username if self.current_session else 'Guest'}
{chars['clock']} Session started: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        # 创建自适应边框
        welcome_box = self._create_box("🎮 CampusWorld SSH Console 🎮", welcome_content)
        
        # 将欢迎信息加入输出队列
        self.output_queue.put(welcome_box)
        
        # 验证命令注册表状态
        self.logger.info(f"Console initialized with {len(self.command_registry.get_all_commands())} commands")
        help_cmd = self.command_registry.get_command("help")
        if help_cmd:
            self.logger.info(f"Help command available: {help_cmd.name}")
        else:
            self.logger.error("Help command not found in registry!")
    
    def _display_prompt(self):
        """显示提示符 - 自适应版本"""
        chars = self._get_charset()
        
        if self.current_session:
            username = self.current_session.username
            timestamp = time.strftime('%H:%M:%S')
            prompt = f"{chars['game']} [{username}@{timestamp}] campusworld> "
        else:
            timestamp = time.strftime('%H:%M:%S')
            prompt = f"{chars['game']} [Guest@{timestamp}] campusworld> "
        
        # 将提示符加入输出队列
        self.output_queue.put(prompt)
    
    def _process_input(self, line: str):
        """处理输入行 - 事件驱动版本"""
        if not line:
            return
        
        # 详细记录输入处理过程
        self.logger.info(f"=== 开始处理输入: '{line}' ===")
        
        # 添加到历史记录
        self.command_history.append(line)
        self.history_index = len(self.command_history)
        self.logger.info(f"输入已添加到历史记录，当前历史长度: {len(self.command_history)}")
        
        # 解析命令
        try:
            self.logger.info("开始解析命令...")
            command_parts = self._parse_command(line)
            if command_parts:
                command_name = command_parts[0]
                args = command_parts[1:]
                
                self.logger.info(f"命令解析成功: 名称='{command_name}', 参数={args}")
                
                # 执行命令
                self.logger.info("开始执行命令...")
                self._execute_command(command_name, args)
                
                self.logger.info(f"命令 '{command_name}' 处理完成")
                    
                # 强制刷新输出 - 确保命令结果被发送
                try:
                    self.logger.info("开始强制刷新输出...")
                    # 发送一个换行符，确保输出完整
                    if self._safe_send_output("\n"):
                        self.logger.info("输出刷新完成")
                    else:
                        self.logger.error("输出刷新失败")
                except Exception as flush_error:
                    self.logger.error(f"输出刷新失败: {flush_error}")
                        
            else:
                self.logger.warning("命令格式无效")
                chars = self._get_charset()
                invalid_msg = f"\n{chars['warning']} Invalid command format\n"
                invalid_msg += f"{chars['lightbulb']} Please enter a valid command or type 'help' for assistance\n"
                if self._safe_send_output(invalid_msg):
                    self.logger.info("格式无效消息已发送")
                else:
                    self.logger.error("格式无效消息发送失败")
                
        except Exception as e:
            self.logger.error(f"命令处理过程中发生错误: {e}")
            self.status_display.show_error(f"Command processing error: {e}")
            
            # 美化错误消息
            chars = self._get_charset()
            error_msg = f"\n{chars['cross_mark']} Command Processing Error\n"
            error_msg += f"{chars['horizontal'] * 50}\n"
            error_msg += f"Error: {e}\n"
            error_msg += f"{chars['horizontal'] * 50}\n"
            error_msg += f"{chars['lightbulb']} Please try again or contact support if the problem persists\n"
            
            if self._safe_send_output(error_msg):
                self.logger.info("处理错误消息已发送")
            else:
                self.logger.error("处理错误消息发送失败")
            
            # 记录详细错误信息
            import traceback
            self.logger.error(f"完整错误堆栈: {traceback.format_exc()}")
        
        self.logger.info(f"=== 输入处理完成: '{line}' ===")
    
    def _parse_command(self, line: str) -> Optional[List[str]]:
        """解析命令字符串"""
        # 简单的命令解析，支持引号
        parts = []
        current = ""
        in_quotes = False
        quote_char = None
        
        for char in line:
            if char in ['"', "'"] and not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
            elif char == ' ' and not in_quotes:
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += char
        
        if current:
            parts.append(current)
        
        return parts if parts else None
    
    def _execute_command(self, command_name: str, args: List[str]):
        """执行命令 - 增强日志记录和美化输出"""
        self.logger.info(f"=== 开始执行命令: {command_name} ===")
        
        try:
            self.logger.info(f"查找命令: {command_name}")
            
            # 查找命令
            command = self.command_registry.get_command(command_name)
            if command:
                self.logger.info(f"命令查找成功: {command.name}")
                
                # 检查权限
                self.logger.info("开始权限检查...")
                if self._check_command_permission(command, args):
                    self.logger.info("权限检查通过，开始执行命令...")
                    
                    try:
                        # 执行命令
                        self.logger.info("调用命令的execute方法...")
                        result = command.execute(self, args)
                        
                        self.logger.info(f"命令执行完成，结果类型: {type(result)}")
                        if result:
                            self.logger.info(f"命令执行成功，结果长度: {len(result)}")
                            self.logger.info(f"命令结果内容: {repr(result[:200])}...")  # 只记录前200字符
                            
                            # 美化输出格式
                            output = self._beautify_command_output(command_name, result)
                            self.logger.info(f"美化输出完成，长度: {len(output)}")
                            
                            # 将输出加入输出队列
                            self.output_queue.put(output)
                            self.logger.info("命令输出已加入输出队列")
                            
                        else:
                            self.logger.info("命令执行成功，但没有输出")
                            # 即使没有输出，也发送确认消息
                            chars = self._get_charset()
                            success_msg = f"\n{chars['success']} Command '{command_name}' executed successfully.\n"
                            self.output_queue.put(success_msg)
                            self.logger.info("成功消息已加入输出队列")
                            
                    except Exception as cmd_error:
                        self.logger.error(f"命令执行过程中发生错误: {cmd_error}")
                        # 发送错误信息到客户端
                        error_msg = self._beautify_error_output(command_name, cmd_error)
                        self.output_queue.put(error_msg)
                        self.logger.info(f"错误信息已加入输出队列: {error_msg}")
                        
                else:
                    self.logger.warning(f"权限检查失败: {command_name}")
                    self.status_display.show_error("Permission denied")
                    chars = self._get_charset()
                    error_msg = f"\n{chars['error']} Permission denied for command '{command_name}'.\n"
                    self.output_queue.put(error_msg)
                    self.logger.info("权限拒绝消息已加入输出队列")
            else:
                self.logger.warning(f"命令未找到: {command_name}")
                self.status_display.show_warning(f"Command not found: {command_name}")
                self.status_display.show_info("Type 'help' for available commands")
                
                # 美化命令未找到的输出
                not_found_msg = self._beautify_command_not_found(command_name)
                self.output_queue.put(not_found_msg)
                self.logger.info("命令未找到消息已加入输出队列")
                
        except Exception as e:
            self.logger.error(f"命令执行过程中发生系统错误: {e}")
            self.status_display.show_error(f"Command execution error: {e}")
            # 确保错误信息发送到客户端
            error_msg = self._beautify_system_error(e)
            self.output_queue.put(error_msg)
            self.logger.info(f"系统错误信息已加入输出队列: {error_msg}")
            
            # 记录详细错误信息
            import traceback
            self.logger.error(f"完整错误堆栈: {traceback.format_exc()}")
        
        self.logger.info(f"=== 命令执行完成: {command_name} ===")
    
    def _beautify_command_output(self, command_name: str, result: str) -> str:
        """美化命令输出格式 - 自适应版本"""
        if command_name == "help":
            return self._beautify_help_output(result)
        elif command_name == "system":
            return self._beautify_system_output(result)
        elif command_name == "user":
            return self._beautify_user_output(result)
        elif command_name == "status":
            return self._beautify_status_output(result)
        else:
            # 默认美化格式
            chars = self._get_charset()
            return self._create_box(f"{chars['book']} Command Output: {command_name}", result)
    
    def _beautify_help_output(self, result: str) -> str:
        """美化帮助命令输出 - 自适应版本"""
        lines = result.split('\n')
        headers = ["Command", "Description"]
        rows = []
        
        for line in lines:
            if line.strip() and ' - ' in line:
                parts = line.split(' - ', 1)
                if len(parts) == 2:
                    cmd, desc = parts
                    rows.append([cmd.strip(), desc.strip()])
        
        if rows:
            return self._create_table(headers, rows, "📚 Available Commands")
        else:
            # 如果没有解析到命令，返回原始格式
            chars = self._get_charset()
            return self._create_box("📚 Available Commands", result)
    
    def _beautify_system_output(self, result: str) -> str:
        """美化系统信息输出 - 自适应版本"""
        chars = self._get_charset()
        return self._create_box(f"{chars['system']} System Information", result)
    
    def _beautify_user_output(self, result: str) -> str:
        """美化用户信息输出 - 自适应版本"""
        chars = self._get_charset()
        return self._create_box(f"{chars['user']} User Information", result)
    
    def _beautify_status_output(self, result: str) -> str:
        """美化状态信息输出 - 自适应版本"""
        chars = self._get_charset()
        return self._create_box(f"{chars['status']} System Status", result)
    
    def _beautify_error_output(self, command_name: str, error: Exception) -> str:
        """美化错误输出 - 自适应版本"""
        chars = self._get_charset()
        error_content = f"Error: {str(error)}\n\n{chars['lightbulb']} Please check the command syntax and try again."
        return self._create_box(f"{chars['error']} Error executing command '{command_name}'", error_content)
    
    def _beautify_command_not_found(self, command_name: str) -> str:
        """美化命令未找到输出 - 自适应版本"""
        chars = self._get_charset()
        not_found_content = f"Command '{command_name}' was not found.\n\n{chars['lightbulb']} Type 'help' for available commands"
        return self._create_box(f"{chars['warning']} Command Not Found", not_found_content)
    
    def _beautify_system_error(self, error: Exception) -> str:
        """美化系统错误输出 - 自适应版本"""
        chars = self._get_charset()
        error_content = f"System Error: {str(error)}\n\n{chars['lightbulb']} Please contact support if the problem persists."
        return self._create_box(f"{chars['cross_mark']} System Error", error_content)
    
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
        """安全发送输出，包含状态检查"""
        try:
            # 检查通道状态
            if not self._check_channel_status():
                self.logger.error("SSH通道状态异常，无法发送输出")
                return False
            
            # 发送输出
            self.logger.info(f"准备发送输出: {repr(message[:100])}...")
            self.channel.send(message)
            self.logger.info(f"输出发送成功: {len(message)} 字符")
            return True
            
        except Exception as e:
            self.logger.error(f"输出发送失败: {e}")
            return False
    
    def _clear_input_buffer(self):
        """清理输入缓冲区 - 参考Evennia框架"""
        try:
            # 清空任何剩余的输入数据
            while True:
                try:
                    self.channel.settimeout(0.01)  # 非常短的超时
                    data = self.channel.recv(1024)
                    if not data:
                        break
                except:
                    break
        except Exception as e:
            if self.debug_mode:
                self.logger.debug(f"Input buffer clear error: {e}")
    
    def _cleanup(self):
        """清理资源"""
        try:
            self.running = False
            
            # 等待事件线程结束
            if self.event_thread and self.event_thread.is_alive():
                self.event_thread.join(timeout=2)
            
            # 清空队列
            while not self.input_queue.empty():
                try:
                    self.input_queue.get_nowait()
                except:
                    pass
            
            while not self.output_queue.empty():
                try:
                    self.output_queue.get_nowait()
                except:
                    pass
            
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
