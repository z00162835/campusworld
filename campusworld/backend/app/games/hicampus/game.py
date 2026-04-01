from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from app.game_engine.base import BaseGame


class Game(BaseGame):
    def __init__(self):
        super().__init__(name="hicampus", version="1.0.0")
        self.description = "HiCampus high-tech R&D and office park world package"
        self.author = "CampusWorld Team"
        self._initialized = False

    def start(self) -> bool:
        if self.is_running:
            return True
        self.start_time = datetime.now()
        self.is_running = True
        return True

    def stop(self) -> bool:
        if not self.is_running:
            return True
        self.is_running = False
        self.start_time = None
        return True

    def get_commands(self) -> Dict[str, Any]:
        return {}

    def initialize_game(self) -> bool:
        self._initialized = True
        return True

    def get_game_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "is_initialized": self._initialized,
            "is_running": self.is_running,
        }

