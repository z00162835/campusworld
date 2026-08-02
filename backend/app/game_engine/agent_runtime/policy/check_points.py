"""Check-point identifiers for the PolicyEngine."""
from __future__ import annotations


class CheckPoint:
    BEFORE_SKILL_ACTIVATION = "before_skill_activation"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_OBSERVATION = "after_tool_observation"
    BEFORE_FINAL_ANSWER = "before_final_answer"

    # F18 quality-domain check_points (registered in P1+; evaluators land per phase).
    AFTER_STATE_EXECUTE = "after_state_execute"
    BEFORE_TERMINAL = "before_terminal"
    PER_REACT_ROUND = "per_react_round"

    ALL = (
        BEFORE_SKILL_ACTIVATION,
        BEFORE_TOOL_CALL,
        AFTER_TOOL_OBSERVATION,
        BEFORE_FINAL_ANSWER,
        AFTER_STATE_EXECUTE,
        BEFORE_TERMINAL,
        PER_REACT_ROUND,
    )
