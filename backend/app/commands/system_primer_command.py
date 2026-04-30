"""``primer`` — surface the CampusWorld system primer as a first-class command.

The underlying text is the maintainer-reviewed markdown at
``docs/models/SPEC/CAMPUSWORLD_SYSTEM_PRIMER.md``. It is shared by all agents,
not a single service.

Usage:

    primer <section>       # preferred: one of identity/structure/ontology/world/
                           #           actions/interaction/memory/invariants/commands
    primer                 # full document (minus maintainer banner); large
    primer --toc           # list available sections
    primer --raw           # markdown with placeholders intact (admin.doc.read)
    primer --for <id>      # render for a different service_id (admin.agent.read)
"""

from __future__ import annotations

from typing import List

from app.commands.base import CommandContext, CommandResult, SystemCommand


class PrimerCommand(SystemCommand):
    """Expose the CampusWorld system primer to users and agents."""

    def __init__(self):
        super().__init__(
            "primer",
    "CampusWorld system primer — prefer `primer <section>` (e.g. primer ontology) "
            "to save tokens; bare `primer` returns the full nine-section document.",
            aliases=["manual"],
        )

    def get_usage(self) -> str:
        return "primer [<section> | --toc | --raw | --for <service_id>]  (prefer <section> over full doc)"

    def _get_specific_help(self) -> str:
        from app.game_engine.agent_runtime.system_primer_context import primer_toc

        lines = ["", "Sections:"]
        for key, title in primer_toc():
            lines.append(f"  {key:12} — {title}")
        lines.append("")
        lines.append("Prefer a single section to reduce output size.")
        lines.append("Examples:")
        lines.append("  primer ontology")
        lines.append("  primer invariants")
        lines.append("  primer")
        lines.append("  primer --toc")
        return "\n".join(lines)

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        from app.game_engine.agent_runtime.system_primer_context import (
            build_ontology_primer,
            primer_toc,
        )

        parsed = _parse_args(args)
        if parsed.error:
            return CommandResult.error_result(parsed.error, is_usage=True)

        if parsed.toc:
            lines = ["Primer sections:"]
            for key, title in primer_toc():
                lines.append(f"  {key:12} — {title}")
            return CommandResult.success_result("\n".join(lines))

        if parsed.raw and "admin.doc.read" not in (context.permissions or []):
            return CommandResult.error_result(
                "primer --raw requires permission 'admin.doc.read'"
            )
        if parsed.for_agent and "admin.agent.read" not in (context.permissions or []):
            return CommandResult.error_result(
                "primer --for requires permission 'admin.agent.read'"
            )

        try:
            text = build_ontology_primer(
                section=parsed.section,
                for_agent=parsed.for_agent,
                raw=parsed.raw,
                session=getattr(context, "db_session", None),
                primer_command_context=context,
            )
        except ValueError as e:
            return CommandResult.error_result(str(e))
        except FileNotFoundError as e:
            return CommandResult.error_result(str(e))
        return CommandResult.success_result(text)


class _ParsedArgs:
    __slots__ = ("section", "toc", "raw", "for_agent", "error")

    def __init__(self):
        self.section: str | None = None
        self.toc: bool = False
        self.raw: bool = False
        self.for_agent: str | None = None
        self.error: str | None = None


def _parse_args(args: List[str]) -> _ParsedArgs:
    out = _ParsedArgs()
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--toc":
            out.toc = True
        elif a == "--raw":
            out.raw = True
        elif a == "--for":
            if i + 1 >= len(args):
                out.error = "--for requires a service_id"
                return out
            out.for_agent = args[i + 1]
            i += 1
        elif a.startswith("--"):
            out.error = f"unknown flag: {a}"
            return out
        else:
            if out.section is not None:
                out.error = f"unexpected argument: {a!r} (already have section {out.section!r})"
                return out
            out.section = a
        i += 1
    return out


PRIMER_COMMANDS: List[PrimerCommand] = [PrimerCommand()]
