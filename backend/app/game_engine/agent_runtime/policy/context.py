"""PolicyContext — the payload carried into a check-point evaluation.

PolicyContext is a plain data carrier; detectors read only the fields they
need. Keeping it a single object avoids ad-hoc keyword arguments drifting
between check_points.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PolicyContext:
    check_point: str

    # --- before_tool_call -------------------------------------------------
    command_name: Optional[str] = None
    command_args: Tuple[str, ...] = field(default_factory=tuple)
    interaction_profile: str = "read"
    side_effect_level: str = "none"
    data_classification: Optional[str] = None
    tool_groups: Tuple[str, ...] = field(default_factory=tuple)
    user_message: str = ""
    caller_profile: str = "read"
    active_skill_context: Optional[Dict[str, Any]] = None

    # --- before_skill_activation -----------------------------------------
    skill_id: Optional[str] = None
    skill_allowed_tool_groups: Tuple[str, ...] = field(default_factory=tuple)
    skill_activation_mode: str = "prompt"
    skill_allowed_in_react_states: Tuple[str, ...] = field(default_factory=tuple)
    current_react_state: Optional[str] = None

    # --- generic ----------------------------------------------------------
    extra: Dict[str, Any] = field(default_factory=dict)
