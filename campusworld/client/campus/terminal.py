"""
终端 UI
使用 prompt_toolkit 实现增强的终端交互体验
Claude Code 风格的 / 命令选择
"""

import asyncio
import sys
import time
from typing import Optional, Callable, List

from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.widgets import TextArea

from .protocol import WSMessage


class CommandCompleter(Completer):
    """命令补全器"""

    def __init__(self, completions: List[str]):
        self.completions = completions

    def get_completions(self, word_before_cursor: str, cursor_position: int,
                        context=None) -> List[Completion]:
        """获取补全选项"""
        word = word_before_cursor.lower()
        for completion in self.completions:
            if completion.lower().startswith(word):
                yield Completion(completion, start_position=-len(word_before_cursor))


class CommandPalette:
    """命令选择面板（用于 / 命令）"""

    def __init__(self, commands: List[tuple]):
        """
        commands: [(name, description), ...]
        """
        self.commands = commands
        self.selected_index = 0

    def move_up(self):
        """选择上一项"""
        if self.commands:
            self.selected_index = (self.selected_index - 1) % len(self.commands)

    def move_down(self):
        """选择下一项"""
        if self.commands:
            self.selected_index = (self.selected_index + 1) % len(self.commands)

    def get_selected(self) -> Optional[str]:
        """获取选中的命令名"""
        if self.commands and 0 <= self.selected_index < len(self.commands):
            return self.commands[self.selected_index][0]

    def render(self) -> List[HTML]:
        """渲染命令列表"""
        lines = []
        for i, (name, desc) in enumerate(self.commands):
            if i == self.selected_index:
                lines.append(HTML(
                    f'<b><style bg="blue" fg="white"> {name} </style></b>  {desc}'
                ))
            else:
                lines.append(HTML(f'  <style fg="white">{name}</style>  {desc}'))
        lines.append(HTML('<style fg="gray">  ↑↓ navigate  Enter select  Esc cancel</style>'))
        return lines


class Terminal:
    """Campus 终端 - 支持 / 命令即时选择（按 / 后 Enter 显示选择列表）"""

    def __init__(self, prompt_format: str = "[{user}@{time}] campusworld> "):
        self.prompt_format = prompt_format
        self.username = "user"
        self._completions: List[str] = []
        self._connection = None

    def set_connection(self, connection):
        """设置连接"""
        self._connection = connection

    def set_completions(self, completions: List[str]):
        """设置补全列表"""
        self._completions = completions

    def _get_prompt(self) -> str:
        """生成提示符"""
        try:
            return self.prompt_format.format(
                user=self.username,
                time=time.strftime("%H:%M:%S")
            )
        except KeyError:
            return "[user@HH:MM:SS] campusworld> "

    def _create_style(self) -> Style:
        """创建终端样式"""
        return Style.from_dict({
            'prompt': '#ansigreen bold',
            'command': '#ansiwhite',
            'error': '#ansired bold',
            'success': '#ansigreen',
        })

    async def run_async(self, on_command: Callable[[str], None]):
        """异步运行终端"""
        session = PromptSession(
            message=self._get_prompt,
            completer=CommandCompleter(self._completions) if self._completions else None,
            enable_history=True,
            mouse_support=False,
            style=self._create_style(),
        )

        # 命令列表
        command_list = [(cmd, cmd) for cmd in self._completions] if self._completions else []

        while True:
            try:
                # 读取用户输入
                text = await session.prompt_async()

                # 检查是否是 / 命令（显示命令选择列表）
                if text.strip() == '/' and command_list:
                    selected = await self._run_palette(session, command_list)
                    if selected:
                        await on_command(selected)
                    continue

                # 处理普通命令
                if text.strip():
                    await on_command(text)

            except KeyboardInterrupt:
                print("\nUse 'quit' or 'exit' to leave campusworld")
                continue
            except EOFError:
                break

    async def _run_palette(self, session: PromptSession, command_list: List[tuple]) -> Optional[str]:
        """运行命令选择面板"""
        palette = CommandPalette(command_list)

        # 创建面板窗口
        palette_control = FormattedTextControl(
            text=palette.render(),
            focusable=True
        )
        palette_window = Window(
            control=palette_control,
            height=min(12, len(command_list) + 3),
            style='class:palette'
        )

        # 输入窗口
        input_buffer = Buffer(multiline=False)
        input_window = TextArea(
            buffer=input_buffer,
            multiline=False,
            get_prompt=lambda: self._get_prompt()
        )

        # 容器
        container = HSplit([palette_window, input_window])
        layout = Layout(container)

        # 按键绑定
        kb = KeyBindings()

        @kb.add('escape', eager=True)
        @kb.add('c-c', eager=True)
        def cancel(event):
            event.app.exit(result=None)

        @kb.add('up', eager=True)
        def up(event):
            palette.move_up()
            palette_control.text = palette.render()
            event.app.invalidate()

        @kb.add('down', eager=True)
        def down(event):
            palette.move_down()
            palette_control.text = palette.render()
            event.app.invalidate()

        @kb.add('enter', eager=True)
        def enter(event):
            selected = palette.get_selected()
            event.app.exit(result=selected)

        # 运行面板应用
        app = Application(
            layout=layout,
            key_bindings=kb,
            style=self._create_style(),
            erase_when_done=True
        )

        return await app.run_async()

    def run(self, on_command: Callable[[str], None]):
        """同步运行终端"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.run_async(on_command))
        except KeyboardInterrupt:
            pass


def format_output(message: str, success: bool = True) -> str:
    """格式化输出"""
    if success:
        return message
    else:
        ESC = chr(27)
        return ESC + "[31mError: " + message + ESC + "[0m"
