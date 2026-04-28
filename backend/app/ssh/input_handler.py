"""
增强的控制台输入处理模块
支持Tab补全、方向键导航、快捷键等高级功能
"""

import re
import logging
from typing import List, Optional, Dict, Any, Callable
from enum import Enum


class KeyCode(Enum):
    """按键代码枚举"""
    TAB = 9
    ENTER = 13
    ESC = 27
    BACKSPACE = 8
    DELETE = 127
    
    # 方向键
    UP = 65
    DOWN = 66
    RIGHT = 67
    LEFT = 68
    
    # Ctrl组合键
    CTRL_A = 1
    CTRL_C = 3
    CTRL_D = 4
    CTRL_E = 5
    CTRL_K = 11
    CTRL_L = 12
    CTRL_U = 21
    CTRL_W = 23


class InputHandler:
    """增强的输入处理器"""
    
    def __init__(self, console):
        self.console = console
        self.logger = logging.getLogger(__name__)
        
        # 输入状态
        self.current_line = ""
        self.cursor_position = 0
        self.history_index = 0
        self.temp_line = ""  # 临时保存当前行
        
        # 补全相关
        self.completion_index = 0
        self.completion_options = []
        self.last_completion = ""
        
        # 快捷键处理器
        self.shortcut_handlers = self._setup_shortcut_handlers()
    
    def _setup_shortcut_handlers(self) -> Dict[int, Callable]:
        """设置快捷键处理器"""
        return {
            KeyCode.CTRL_A: self._go_to_beginning,
            KeyCode.CTRL_E: self._go_to_end,
            KeyCode.CTRL_K: self._kill_to_end,
            KeyCode.CTRL_U: self._kill_to_beginning,
            KeyCode.CTRL_W: self._kill_word_backward,
            KeyCode.CTRL_L: self._clear_screen,
        }
    
    def read_line(self) -> Optional[str]:
        """读取一行输入，支持高级功能"""
        self.current_line = ""
        self.cursor_position = 0
        self.completion_index = 0
        self.completion_options = []
        
        # 保存当前行到临时变量
        self.temp_line = ""
        
        while True:
            try:
                char = self.console.channel.recv(1)
                if not char:
                    continue
                
                char_code = ord(char)
                
                # 处理特殊按键
                if char_code == KeyCode.ESC:
                    if self._handle_escape_sequence():
                        continue
                
                # 处理Ctrl组合键
                elif char_code < 32 and char_code in self.shortcut_handlers:
                    self.shortcut_handlers[char_code]()
                    continue
                
                # 处理普通字符
                elif char_code >= 32:
                    self._insert_char(char)
                
                # 处理回车
                elif char_code == KeyCode.ENTER:
                    self.console.channel.send('\n')
                    return self.current_line
                
                # 处理退格
                elif char_code == KeyCode.BACKSPACE:
                    self._handle_backspace()
                
                # 处理Tab补全
                elif char_code == KeyCode.TAB:
                    self._handle_tab_completion()
                
            except Exception as e:
                if "timeout" in str(e).lower():
                    continue
                else:
                    self.logger.error(f"Input handling error: {e}")
                    break
        
        return self.current_line
    
    def _handle_escape_sequence(self) -> bool:
        """处理转义序列（方向键等）"""
        try:
            # 读取下一个字符
            char = self.console.channel.recv(1)
            if not char:
                return False
            
            if ord(char) == ord('['):
                # 读取键码
                key_char = self.console.channel.recv(1)
                if not key_char:
                    return False
                
                key_code = ord(key_char)
                
                if key_code == KeyCode.UP:
                    self._navigate_history_up()
                    return True
                elif key_code == KeyCode.DOWN:
                    self._navigate_history_down()
                    return True
                elif key_code == KeyCode.LEFT:
                    self._move_cursor_left()
                    return True
                elif key_code == KeyCode.RIGHT:
                    self._move_cursor_right()
                    return True
                
        except Exception as e:
            self.logger.debug(f"Escape sequence handling error: {e}")
        
        return False
    
    def _insert_char(self, char: str):
        """插入字符"""
        if self.cursor_position == len(self.current_line):
            # 在末尾插入
            self.current_line += char
            self.console.channel.send(char)
        else:
            # 在中间插入
            self.current_line = (self.current_line[:self.cursor_position] + 
                               char + self.current_line[self.cursor_position:])
            self.cursor_position += 1
            
            # 重新显示当前行
            self._redisplay_line()
        
        self.cursor_position += 1
    
    def _handle_backspace(self):
        """处理退格键"""
        if self.cursor_position > 0:
            self.current_line = (self.current_line[:self.cursor_position-1] + 
                               self.current_line[self.cursor_position:])
            self.cursor_position -= 1
            
            # 发送退格序列
            self.console.channel.send('\b \b')
    
    def _handle_tab_completion(self):
        """处理Tab补全"""
        if not self.current_line.strip():
            return
        
        # 获取当前单词
        words = self.current_line.split()
        current_word = words[-1] if words else ""
        
        if not current_word:
            return
        
        # 获取补全选项
        if self.last_completion != current_word:
            self.completion_options = self._get_completion_options(current_word)
            self.completion_index = 0
            self.last_completion = current_word
        
        if not self.completion_options:
            return
        
        # 应用补全
        completion = self.completion_options[self.completion_index]
        
        # 替换当前单词
        if len(words) > 1:
            words[-1] = completion
            new_line = " ".join(words)
        else:
            new_line = completion
        
        # 计算需要删除的字符数
        chars_to_delete = len(self.current_line) - self.cursor_position
        
        # 删除当前行
        for _ in range(chars_to_delete):
            self.console.channel.send('\b')
        
        for _ in range(len(self.current_line)):
            self.console.channel.send('\b \b')
        
        # 显示新行
        self.current_line = new_line
        self.cursor_position = len(new_line)
        self.console.channel.send(new_line)
        
        # 更新补全索引
        self.completion_index = (self.completion_index + 1) % len(self.completion_options)
    
    def _get_completion_options(self, partial: str) -> List[str]:
        """获取补全选项"""
        options = []
        
        # 从命令注册表获取命令名
        if hasattr(self.console, 'command_registry'):
            for cmd_name in self.console.command_registry.commands.keys():
                if cmd_name.startswith(partial):
                    options.append(cmd_name)
        
        # 添加常用命令
        common_commands = ['help', 'system', 'user', 'exit', 'quit', 'clear', 'date']
        for cmd in common_commands:
            if cmd.startswith(partial) and cmd not in options:
                options.append(cmd)
        
        return sorted(options)
    
    def _navigate_history_up(self):
        """向上导航历史记录"""
        if not self.console.command_history:
            return
        
        if self.history_index == 0:
            # 保存当前行
            self.temp_line = self.current_line
        
        if self.history_index < len(self.console.command_history):
            self.history_index += 1
            history_line = self.console.command_history[-(self.history_index)]
            self._replace_current_line(history_line)
    
    def _navigate_history_down(self):
        """向下导航历史记录"""
        if self.history_index > 0:
            self.history_index -= 1
            
            if self.history_index == 0:
                # 恢复临时保存的行
                self._replace_current_line(self.temp_line)
            else:
                history_line = self.console.command_history[-(self.history_index)]
                self._replace_current_line(history_line)
    
    def _replace_current_line(self, new_line: str):
        """替换当前行"""
        # 删除当前行
        for _ in range(len(self.current_line)):
            self.console.channel.send('\b \b')
        
        # 显示新行
        self.current_line = new_line
        self.cursor_position = len(new_line)
        self.console.channel.send(new_line)
    
    def _move_cursor_left(self):
        """向左移动光标"""
        if self.cursor_position > 0:
            self.cursor_position -= 1
            self.console.channel.send('\b')
    
    def _move_cursor_right(self):
        """向右移动光标"""
        if self.cursor_position < len(self.current_line):
            self.cursor_position += 1
            # 发送前进字符
            self.console.channel.send(self.current_line[self.cursor_position - 1])
    
    def _redisplay_line(self):
        """重新显示当前行"""
        # 保存光标位置
        old_position = self.cursor_position
        
        # 移动到行首
        while self.cursor_position > 0:
            self.console.channel.send('\b')
            self.cursor_position -= 1
        
        # 重新显示
        self.console.channel.send(self.current_line)
        
        # 恢复光标位置
        self.cursor_position = old_position
    
    # 快捷键处理方法
    def _go_to_beginning(self):
        """移动到行首 (Ctrl+A)"""
        while self.cursor_position > 0:
            self.console.channel.send('\b')
            self.cursor_position -= 1
    
    def _go_to_end(self):
        """移动到行尾 (Ctrl+E)"""
        while self.cursor_position < len(self.current_line):
            self.console.channel.send(self.current_line[self.cursor_position])
            self.cursor_position += 1
    
    def _kill_to_end(self):
        """删除到行尾 (Ctrl+K)"""
        if self.cursor_position < len(self.current_line):
            chars_to_delete = len(self.current_line) - self.cursor_position
            self.current_line = self.current_line[:self.cursor_position]
            
            # 删除显示的字符
            for _ in range(chars_to_delete):
                self.console.channel.send(' \b')
    
    def _kill_to_beginning(self):
        """删除到行首 (Ctrl+U)"""
        if self.cursor_position > 0:
            chars_to_delete = self.cursor_position
            self.current_line = self.current_line[self.cursor_position:]
            
            # 删除显示的字符
            for _ in range(chars_to_delete):
                self.console.channel.send('\b \b')
            
            self.cursor_position = 0
    
    def _kill_word_backward(self):
        """向后删除单词 (Ctrl+W)"""
        if self.cursor_position > 0:
            # 找到单词边界
            pos = self.cursor_position - 1
            while pos > 0 and self.current_line[pos] == ' ':
                pos -= 1
            while pos > 0 and self.current_line[pos] != ' ':
                pos -= 1
            
            word_start = pos + 1 if pos > 0 else 0
            chars_to_delete = self.cursor_position - word_start
            
            # 删除单词
            self.current_line = (self.current_line[:word_start] + 
                               self.current_line[self.cursor_position:])
            
            # 删除显示的字符
            for _ in range(chars_to_delete):
                self.console.channel.send('\b \b')
            
            self.cursor_position = word_start
    
    def _clear_screen(self):
        """清屏 (Ctrl+L)"""
        self.console.channel.send('\033[2J\033[H')
        # 重新显示提示符和当前行
        self.console._display_prompt()
        if self.current_line:
            self.console.channel.send(self.current_line)
