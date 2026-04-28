"""
CampusWorld 终端 - 基于 Textual 框架
提供 Claude Code 风格的命令面板体验
"""

import asyncio
from difflib import SequenceMatcher
from typing import Optional, Callable, List, AsyncIterator
from textual.app import App, ComposeResult
from textual.command import CommandPalette, Provider, Hit, Hits, DiscoveryHit
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Input, Static, Log
from textual.binding import Binding
from textual.suggester import Suggester
from textual.style import Style
from textual import on

from .protocol import WSMessage


class CommandSuggester(Suggester):
    """命令补全建议器"""

    def __init__(self, completions: List[str]):
        super().__init__()
        self._completions = completions

    async def get_suggestion(self, value: str) -> Optional[str]:
        """获取建议（返回字符串或None）"""
        if not value or not self._completions:
            return None

        value_lower = value.lower().strip()
        if not value_lower:
            return None

        # 前缀匹配优先
        for cmd in self._completions:
            if cmd.lower().startswith(value_lower):
                return cmd

        # 模糊匹配
        best_match = None
        best_ratio = 0.6
        for cmd in self._completions:
            ratio = SequenceMatcher(None, value_lower, cmd.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = cmd

        return best_match

    def update_completions(self, completions: List[str]):
        """更新补全列表"""
        self._completions = completions


class CampusCommandProvider(Provider):
    """命令提供者 - 从服务器获取命令列表（Textual 8.x API）"""

    def __init__(self, screen: Screen, match_style: Style | None = None) -> None:
        super().__init__(screen, match_style)

    async def discover(self) -> Hits:
        """Textual 8.x：打开命令面板时查询串为空，走 discover() 而非 search('')。"""
        app = self.screen.app
        all_commands = list(app._completions)
        agent_commands = [f"/{a}" for a in app._agents]
        for cmd in all_commands:
            yield DiscoveryHit(
                display=cmd,
                command=lambda c=cmd: app.call_later(app.execute_from_provider, c),
                text=cmd,
                help=f"执行命令: {cmd}",
            )
        for agent_cmd in agent_commands:
            agent_name = agent_cmd[1:]
            yield DiscoveryHit(
                display=agent_cmd,
                command=lambda a=agent_name: app.call_later(app.enter_agent, a),
                text=agent_cmd,
                help=f"进入 {agent_name} 环境",
            )

    async def search(self, query: str) -> AsyncIterator[Hit]:
        """搜索命令

        Args:
            query: 用户输入的搜索文本

        Yields:
            匹配的 Hit 对象
        """
        # 获取 CampusTerminal 实例
        app = self.screen.app

        # 获取所有候选命令
        all_commands = list(app._completions)
        agent_commands = [f"/{a}" for a in app._agents]

        if not query:
            # 无搜索词时，列出所有命令
            for cmd in all_commands:
                yield Hit(
                    score=1.0,
                    match_display=cmd,
                    command=lambda c=cmd: app.call_later(app.execute_from_provider, c),
                    text=cmd,
                    help=f"执行命令: {cmd}",
                )
            for agent_cmd in agent_commands:
                agent_name = agent_cmd[1:]
                yield Hit(
                    score=1.0,
                    match_display=agent_cmd,
                    command=lambda a=agent_name: app.call_later(app.enter_agent, a),
                    text=agent_cmd,
                    help=f"进入 {agent_name} 环境",
                )
        else:
            # 模糊匹配 + 前缀/子串兜底（fuzzy 分数为 0 时 `if matcher.match` 会误判为无匹配）
            q = (query or "").strip().lower()
            matcher = self.matcher((query or "").strip())
            for cmd in all_commands:
                cl = cmd.lower()
                fuzzy = matcher.match(cmd)
                if fuzzy > 0 or (q and (cl.startswith(q) or q in cl)):
                    yield Hit(
                        score=fuzzy if fuzzy > 0 else 0.75,
                        match_display=cmd,
                        command=lambda c=cmd: app.call_later(app.execute_from_provider, c),
                        text=cmd,
                        help=f"执行命令: {cmd}",
                    )
            for agent_cmd in agent_commands:
                agent_name = agent_cmd[1:]
                al = agent_cmd.lower()
                fuzzy_a = matcher.match(agent_cmd)
                if fuzzy_a > 0 or (q and (al.startswith(q) or q in al)):
                    yield Hit(
                        score=fuzzy_a if fuzzy_a > 0 else 0.75,
                        match_display=agent_cmd,
                        command=lambda a=agent_name: app.call_later(app.enter_agent, a),
                        text=agent_cmd,
                        help=f"进入 {agent_name} 环境",
                    )


class CampusTerminal(App):
    """CampusWorld 终端应用"""

    # 只使用自定义命令提供者，不包含默认 Textual 命令
    COMMANDS = {CampusCommandProvider}

    # CSS 样式文件
    CSS_PATH = "terminal.css"

    BINDINGS = [
        Binding("/", "open_command_palette", "Commands", show=False),
        Binding("escape", "cancel_input", "Cancel", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("tab", "complete_command", "Complete", show=False),
        Binding("up", "history_up", show=False),
        Binding("down", "history_down", show=False),
    ]

    def __init__(self, completions: List[str], on_command: Optional[Callable] = None):
        super().__init__()
        self._completions = completions
        self._agents: List[str] = []
        self._on_command = on_command
        self._command_palette: Optional[CommandPalette] = None
        self._current_agent: Optional[str] = None
        self._suggester = CommandSuggester(completions)
        self._history: List[str] = []
        self._history_index: int = -1
        self._connection = None
        self._completion_index: int = -1
        self._current_matches: List[str] = []

    def compose(self) -> ComposeResult:
        """构建 UI"""
        with Container(id="chat-container"):
            yield Log(id="output")
        with Horizontal(id="input-line"):
            yield Static(">>> ", id="prompt")
            yield Input(
                placeholder="输入命令",
                id="command-input",
                suggester=self._suggester,
            )

    @on(Input.Changed)
    async def on_input_changed(self, event: Input.Changed) -> None:
        """监听输入变化，当输入 / 时打开命令面板"""
        if event.value == "/":
            # 清空输入并打开命令面板
            event.input.value = ""
            self.push_screen(CommandPalette())

    async def on_mount(self) -> None:
        """应用挂载"""
        self.title = "CampusWorld CLI"
        self.sub_title = "CampusWorld Terminal"

        # 显示欢迎信息 - 使用纯字符串，Log 会自动处理显示
        output = self.query_one("#output", Log)
        output.write_line("========================================")
        output.write_line("  Welcome to CampusWorld CLI")
        output.write_line("  Type / to select commands or enter agent mode")
        output.write_line("  Type @<id> to interact with agent instance")
        output.write_line("========================================")
        output.write_line("")
        if not self._completions:
            output.write_line(
                "Warning: server returned no command names for completion. "
                "Check backend logs (command init) and reconnect."
            )
            output.write_line("")
        # 聚焦输入框
        self.query_one("#command-input", Input).focus()

    @on(Input.Submitted)
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理输入提交"""
        command = event.value.strip()
        if command:
            # 添加到历史记录
            if command not in self._history:
                self._history.insert(0, command)
                if len(self._history) > 100:
                    self._history.pop()
            self._history_index = -1
            await self.execute_command(command)
            # 清空输入
            self.query_one("#command-input", Input).value = ""

    async def execute_command(self, command: str) -> None:
        """执行命令"""
        output = self.query_one("#output", Log)

        # 检查是否是 Agent 命令
        if command.startswith("/"):
            agent_name = command[1:].strip()
            if agent_name:
                await self.enter_agent(agent_name)
                return
            else:
                # 只输入 / 时，显示可用 agents
                if self._agents:
                    output.write_line("可用 Agent:")
                    for agent in self._agents:
                        output.write_line(f"  /{agent}")
                else:
                    output.write_line("暂无可用 Agent")
                return
        elif command.startswith("@"):
            agent_id = command[1:].strip()
            if agent_id and self._current_agent:
                await self.enter_agent_instance(agent_id)
                return

        # 添加命令到输出
        prompt = ">>>"
        if self._current_agent:
            prompt = f"[{self._current_agent}]>>>"
        output.write_line(f"{prompt} {command}")

        # 调用命令回调
        if self._on_command:
            await self._on_command(command)

    async def execute_from_provider(self, command: str) -> None:
        """从命令面板执行命令"""
        input_widget = self.query_one("#command-input", Input)
        input_widget.value = command
        await self.execute_command(command)
        input_widget.value = ""

    async def enter_agent(self, agent_name: str) -> None:
        """进入 Agent 环境"""
        output = self.query_one("#output", Log)

        # 尝试与服务端通信
        if self._connection:
            success = await self._connection.agent_enter(agent_name)
            if success:
                self._current_agent = agent_name
                self.update_status()
                return

        # 回退到本地模式（服务端不支持时）
        output.write_line(f"进入 {agent_name} 环境 (本地模式)")
        output.write_line("可用命令:")
        output.write_line("  ls      - 列出所有 agent 实例")
        output.write_line("  @<id>   - 进入指定的 agent 实例")
        output.write_line("  exit    - 退出 agent 环境")
        self._current_agent = agent_name
        self.update_status()

    async def enter_agent_instance(self, instance_id: str) -> None:
        """进入特定的 Agent 实例"""
        output = self.query_one("#output", Log)
        output.write_line(f"进入 agent 实例 {instance_id}")
        output.write_line("提示：此 agent 提供 check 命令可用")

    async def exit_agent(self) -> None:
        """退出 Agent 环境"""
        if self._current_agent:
            if self._connection:
                await self._connection.agent_exit()
            output = self.query_one("#output", Log)
            output.write_line(f"退出 {self._current_agent} 环境")
            self._current_agent = None
            self.update_status()

    def action_focus_next(self) -> None:
        """Override Screen's Tab binding so Tab triggers command completion."""
        self.action_complete_command()

    def action_complete_command(self) -> None:
        """Tab 补全：单匹配直接填充，多匹配循环填充"""
        input_widget = self.query_one("#command-input", Input)
        value = input_widget.value

        if not self._completions:
            return

        # 查找匹配的命令
        value_lower = value.lower().strip()
        matches = [cmd for cmd in self._completions if cmd.lower().startswith(value_lower)]

        if not matches:
            return

        if len(matches) == 1:
            # 唯一匹配，直接填充
            self._completion_index = -1
            self._current_matches = []
            input_widget.value = matches[0]
        else:
            # 多个匹配：循环填充下一个
            self._current_matches = matches
            self._completion_index = (self._completion_index + 1) % len(matches)
            input_widget.value = matches[self._completion_index]

    def action_open_command_palette(self) -> None:
        """打开命令面板"""
        self.push_screen(CommandPalette())

    def action_cancel_input(self) -> None:
        """取消输入 / 退出 Agent 环境"""
        if self._current_agent:
            # 在 Agent 环境中，ESC 退出 Agent 环境
            asyncio.create_task(self.exit_agent())
        else:
            # 普通模式下清空输入
            input_widget = self.query_one("#command-input", Input)
            input_widget.value = ""
            self.set_focus(self.query_one("#command-input", Input))

    def action_history_up(self) -> None:
        """历史上一条命令"""
        if not self._history:
            return
        input_widget = self.query_one("#command-input", Input)
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            input_widget.value = self._history[self._history_index]

    def action_history_down(self) -> None:
        """历史下一条命令"""
        input_widget = self.query_one("#command-input", Input)
        if self._history_index > 0:
            self._history_index -= 1
            input_widget.value = self._history[self._history_index]
        elif self._history_index == 0:
            self._history_index = -1
            input_widget.value = ""

    def append_output(self, text: str, style: str = "") -> None:
        """追加输出"""
        output = self.query_one("#output", Log)
        output.write_line(text)

    def update_status(self) -> None:
        """更新提示符 - 不再使用状态栏"""
        pass

    def update_completions(self, completions: List[str]) -> None:
        """更新命令列表"""
        self._completions = completions
        self._suggester.update_completions(completions)

    def update_agents(self, agents: List[str]) -> None:
        """更新 Agent 列表"""
        self._agents = agents


class Terminal:
    """Terminal 包装器 - 兼容原有接口"""

    def __init__(self, prompt_format: str = "[{user}@{time}] campusworld> "):
        self.prompt_format = prompt_format
        self.username = "user"
        self._completions: List[str] = []
        self._connection = None
        self._on_command_callback: Optional[Callable] = None
        self._app: Optional[CampusTerminal] = None

    def set_connection(self, connection):
        """设置连接"""
        self._connection = connection

    def set_completions(self, completions: List[str]):
        """设置补全列表"""
        self._completions = completions
        if self._app:
            self._app.update_completions(completions)

    async def _handle_command(self, command: str):
        """处理命令"""
        if self._connection:
            await self._connection.send_command(command)
            response = await self._connection.receive_command_result()
            if response:
                if WSMessage.is_result(response):
                    msg = response.get("message", "")
                    success = response.get("success", True)
                    if self._app:
                        style = "green" if success else "red bold"
                        self._app.append_output(msg, style)
                elif WSMessage.is_error(response):
                    if self._app:
                        self._app.append_output(response.get("message", "Unknown error"), "red bold")

    async def run_async(self, on_command: Callable[[str], None] = None):
        """异步运行终端"""
        self._on_command_callback = on_command
        app = CampusTerminal(self._completions, self._handle_command)
        app._connection = self._connection
        self._app = app
        await app.run_async()


def format_output(message: str, success: bool = True) -> str:
    """格式化输出"""
    if success:
        return message
    else:
        return f"[red]Error: {message}[/red]"
