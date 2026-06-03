"""Synchronous decision-center queries (slash commands and text search)."""
from __future__ import annotations

from typing import Any, Callable, Dict

from sqlalchemy.orm import Session

from app.commands.base import CommandResult

from .types import WorldActor


class CommandQueryService:
    """Handles POST /decision-center/query without mode branching at the HTTP layer."""

    MODE = "command"

    def __init__(
        self,
        *,
        run_command: Callable[[Session, WorldActor, str], CommandResult],
        search: Callable[[Session, WorldActor, str], Dict[str, Any]],
        build_patch: Callable[[Session, WorldActor, CommandResult], Dict[str, Any]],
    ) -> None:
        self._run_command = run_command
        self._search = search
        self._build_patch = build_patch

    def run(self, session: Session, actor: WorldActor, query: str) -> Dict[str, Any]:
        clean = str(query or "").strip()
        if not clean:
            return {"answer": "Enter a query or choose a mode.", "mode": self.MODE, "suggested_actions": []}
        if clean.startswith("/"):
            return self._run_command_line(session, actor, clean[1:])
        if clean.lower().startswith("search "):
            return self._run_text_search(session, actor, clean[7:].strip())
        # Command mode: bare input executes as a shell command (not graph search).
        return self._run_command_line(session, actor, clean)

    def _run_command_line(self, session: Session, actor: WorldActor, command_line: str) -> Dict[str, Any]:
        result = self._run_command(session, actor, command_line)
        patch_payload = self._build_patch(session, actor, result)
        return {
            "answer": result.message or "",
            "mode": self.MODE,
            "command_result": patch_payload["command_result"],
            "suggested_actions": [],
            "state_patch": patch_payload["state_patch"],
        }

    def _run_text_search(self, session: Session, actor: WorldActor, query: str) -> Dict[str, Any]:
        search = self._search(session, actor, query)
        return {
            "answer": search["summary"],
            "mode": self.MODE,
            "results": search["results"],
            "suggested_actions": search["suggested_actions"],
        }
