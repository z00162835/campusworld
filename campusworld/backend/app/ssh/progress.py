"""
进度显示模块
支持命令执行进度显示和状态更新
"""

import time
import threading
from typing import Optional, Callable


class ProgressBar:
    """进度条显示"""
    
    def __init__(self, total: int, description: str = "", width: int = 50):
        self.total = total
        self.current = 0
        self.description = description
        self.width = width
        self.start_time = time.time()
        self.lock = threading.Lock()
    
    def update(self, value: int):
        """更新进度"""
        with self.lock:
            self.current = min(value, self.total)
    
    def increment(self, value: int = 1):
        """增加进度"""
        with self.lock:
            self.current = min(self.current + value, self.total)
    
    def display(self, channel) -> str:
        """显示进度条"""
        with self.lock:
            if self.total == 0:
                return ""
            
            percentage = (self.current / self.total) * 100
            filled_width = int((self.current / self.total) * self.width)
            
            bar = "█" * filled_width + "░" * (self.width - filled_width)
            
            elapsed_time = time.time() - self.start_time
            if self.current > 0:
                eta = (elapsed_time / self.current) * (self.total - self.current)
            else:
                eta = 0
            
            progress_text = f"\r{self.description} [{bar}] {percentage:5.1f}% "
            progress_text += f"({self.current}/{self.total}) "
            progress_text += f"ETA: {eta:.1f}s"
            
            channel.send(progress_text)
            return progress_text
    
    def finish(self, channel):
        """完成进度条"""
        self.current = self.total
        self.display(channel)
        channel.send("\n")


class Spinner:
    """旋转指示器"""
    
    def __init__(self, description: str = ""):
        self.description = description
        self.spinning = False
        self.spinner_thread = None
        self.spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.current_char = 0
    
    def start(self, channel):
        """开始旋转"""
        if self.spinning:
            return
        
        self.spinning = True
        self.spinner_thread = threading.Thread(target=self._spin, args=(channel,))
        self.spinner_thread.daemon = True
        self.spinner_thread.start()
    
    def stop(self, channel):
        """停止旋转"""
        self.spinning = False
        if self.spinner_thread:
            self.spinner_thread.join(timeout=1)
        
        # 清除旋转指示器
        channel.send("\r" + " " * (len(self.description) + 3) + "\r")
    
    def _spin(self, channel):
        """旋转逻辑"""
        while self.spinning:
            spinner_text = f"\r{self.description} {self.spinner_chars[self.current_char]}"
            channel.send(spinner_text)
            
            self.current_char = (self.current_char + 1) % len(self.spinner_chars)
            time.sleep(0.1)


class StatusDisplay:
    """状态显示管理器"""
    
    def __init__(self, channel):
        self.channel = channel
        self.current_progress: Optional[ProgressBar] = None
        self.current_spinner: Optional[Spinner] = None
    
    def show_progress(self, total: int, description: str = "") -> ProgressBar:
        """显示进度条"""
        if self.current_progress:
            self.current_progress.finish(self.channel)
        
        self.current_progress = ProgressBar(total, description)
        return self.current_progress
    
    def show_spinner(self, description: str = "") -> Spinner:
        """显示旋转指示器"""
        if self.current_spinner:
            self.current_spinner.stop(self.channel)
        
        self.current_spinner = Spinner(description)
        self.current_spinner.start(self.channel)
        return self.current_spinner
    
    def update_status(self, message: str):
        """更新状态消息"""
        # 清除当前行
        self.channel.send("\r" + " " * 80 + "\r")
        # 显示新状态
        self.channel.send(f"\r{message}")
    
    def clear_status(self):
        """清除状态显示"""
        self.channel.send("\r" + " " * 80 + "\r")
    
    def show_success(self, message: str):
        """显示成功消息"""
        self.channel.send(f"\r✅ {message}\n")
    
    def show_error(self, message: str):
        """显示错误消息"""
        self.channel.send(f"\r❌ {message}\n")
    
    def show_warning(self, message: str):
        """显示警告消息"""
        self.channel.send(f"\r⚠️  {message}\n")
    
    def show_info(self, message: str):
        """显示信息消息"""
        self.channel.send(f"\rℹ️  {message}\n")


def with_progress(description: str = ""):
    """进度显示装饰器"""
    def decorator(func):
        def wrapper(console, *args, **kwargs):
            status_display = StatusDisplay(console.channel)
            
            try:
                # 显示开始状态
                status_display.show_info(f"Starting: {description}")
                
                # 执行函数
                result = func(console, *args, **kwargs)
                
                # 显示成功状态
                status_display.show_success(f"Completed: {description}")
                
                return result
                
            except Exception as e:
                # 显示错误状态
                status_display.show_error(f"Failed: {description} - {str(e)}")
                raise
        
        return wrapper
    return decorator
