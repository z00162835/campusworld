"""
命令补全器
"""

from typing import List
from prompt_toolkit.completion import Completer, Completion


class CommandCompleter(Completer):
    """命令补全器"""

    def __init__(self, commands: List[str]):
        self.commands = commands

    def get_completions(self, word_before_cursor: str, cursor_position: int,
                        context=None) -> List[Completion]:
        """获取补全选项"""
        word = word_before_cursor.lower()
        for command in self.commands:
            if command.lower().startswith(word):
                yield Completion(
                    command,
                    start_position=-len(word_before_cursor),
                    display=command,
                    display_meta="command"
                )
