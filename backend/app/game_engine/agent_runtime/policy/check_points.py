"""Check-point identifiers for the PolicyEngine."""
from __future__ import annotations

class CheckPoint:
    BEFORE_SKILL_ACTIVATION = "before_skill_activation"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_OBSERVATION = "after_tool_observation"
    BEFORE_FINAL_ANSWER = "before_final_answer"

    ALL = (
        BEFORE_SKILL_ACTIVATION,
        BEFORE_TOOL_CALL,
        AFTER_TOOL_OBSERVATION,
        BEFORE_FINAL_ANSWER,
    )
