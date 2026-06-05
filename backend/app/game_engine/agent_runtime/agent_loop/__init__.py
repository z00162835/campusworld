"""Phase-agnostic agent loop continuation and draft completeness policies."""
from app.game_engine.agent_runtime.agent_loop.config import AgentLoopConfig
from app.game_engine.agent_runtime.agent_loop.continuation import (
    build_filtered_tool_continuation_turns,
    build_draft_retry_user_text,
)
from app.game_engine.agent_runtime.agent_loop.draft_gate import assess_draft_completeness, assess_draft_completeness_with_budget, is_draft_streamable
from app.game_engine.agent_runtime.agent_loop.policy import detect_pending_tool_work, should_exit_react_round
from app.game_engine.agent_runtime.agent_loop.signals import DraftCompletenessVerdict, PendingToolWork

__all__ = [
    'AgentLoopConfig',
    'DraftCompletenessVerdict',
    'PendingToolWork',
    'assess_draft_completeness',
    'assess_draft_completeness_with_budget',
    'build_draft_retry_user_text',
    'build_filtered_tool_continuation_turns',
    'detect_pending_tool_work',
    'is_draft_streamable',
    'should_exit_react_round',
]
