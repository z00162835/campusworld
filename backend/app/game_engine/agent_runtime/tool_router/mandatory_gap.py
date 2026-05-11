"""Detect gaps between F14 mandatory_tool_names and Plan-phase ToolObservation results (F14 §3.4 D6 hint)."""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence, Tuple
from app.commands.registry import command_registry
from app.game_engine.agent_runtime.tool_calling import ToolResult

def normalize_command_name(name: str) -> str:
    raw = (name or '').strip()
    if not raw:
        return ''
    cmd = command_registry.get_command(raw)
    return (cmd.name if cmd is not None else raw).strip().lower()

def _plan_phase_entries(trace: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not trace:
        return []
    return [e for e in trace if isinstance(e, dict) and e.get('phase') == 'plan']

def _gather_budget_pressure(plan_entries: Sequence[Dict[str, Any]]) -> bool:
    """True if Plan phase hit gather caps or skip-before-execute."""
    for e in plan_entries:
        step = str(e.get('step') or '')
        if step == 'tool_gather_skip' or step.endswith('_cap'):
            return True
    return False

def _error_suggests_permission_denied(err: str) -> bool:
    s = (err or '').lower()
    needles = ('permission', 'denied', 'forbidden', 'guard_blocked', 'not_on_resolved_surface', 'world_forbidden', 'execution_gate', 'not allowed')
    return any((n in s for n in needles))

def mandatory_observation_gap(mandatory_tool_names: List[str], plan_tool_results: List[ToolResult], *, plan_trace: Optional[Sequence[Dict[str, Any]]]=None) -> Tuple[bool, Dict[str, Any]]:
    """Return (has_gap, detail) with missing / failed tools, reason_codes, and trace-derived hints."""
    by_primary: Dict[str, List[bool]] = {}
    for tr in plan_tool_results:
        k = normalize_command_name(tr.name)
        if not k:
            continue
        by_primary.setdefault(k, []).append(bool(tr.ok))
    missing: List[str] = []
    failed: List[str] = []
    seen_m = set()
    for m in mandatory_tool_names:
        raw = (m or '').strip()
        if not raw or raw in seen_m:
            continue
        seen_m.add(raw)
        k = normalize_command_name(raw)
        if not k:
            continue
        if k not in by_primary:
            missing.append(raw)
        elif not any(by_primary[k]):
            failed.append(raw)
    codes: List[str] = []
    if missing:
        codes.append('mandatory_not_invoked')
    if failed:
        codes.append('mandatory_failed')
    detail: Dict[str, Any] = {'missing': missing, 'failed': failed, 'reason_codes': codes, 'permission_denied_tools': [], 'gather_budget_limited': False}
    has_gap = bool(missing or failed)
    plan_entries = _plan_phase_entries(plan_trace)
    mandatory_keys = {normalize_command_name(m) for m in mandatory_tool_names if normalize_command_name(m)}
    permission_tools: List[str] = []
    for e in plan_entries:
        if e.get('step') != 'tool_exec':
            continue
        if e.get('success') is True:
            continue
        cmd_k = normalize_command_name(str(e.get('command_name') or ''))
        if not cmd_k or cmd_k not in mandatory_keys:
            continue
        err = str(e.get('error') or '')
        if _error_suggests_permission_denied(err):
            for m in mandatory_tool_names:
                if normalize_command_name(m) == cmd_k and m not in permission_tools:
                    permission_tools.append(m)
                    break
    detail['permission_denied_tools'] = permission_tools
    if permission_tools and 'permission_denied' not in codes:
        codes.append('permission_denied')
    budget_hit = _gather_budget_pressure(plan_entries)
    detail['gather_budget_limited'] = bool(has_gap and budget_hit)
    if detail['gather_budget_limited'] and 'gather_budget_limited' not in codes:
        codes.append('gather_budget_limited')
    return (has_gap, detail)

def format_mandatory_gap_user_notice(detail: Dict[str, Any]) -> str:
    """Short user-visible appendix when mandatory tools lacked successful observations."""
    missing = detail.get('missing') or []
    failed = detail.get('failed') or []
    if not missing and (not failed):
        return ''
    parts: List[str] = []
    if missing:
        parts.append(f"未形成观测的工具：{', '.join(missing)}")
    if failed:
        parts.append(f"调用未成功的工具：{', '.join(failed)}")
    tail = ''
    codes = detail.get('reason_codes') or []
    hints: List[str] = []
    if 'permission_denied' in codes:
        hints.append('部分失败可能与权限或命令门禁有关')
    if 'gather_budget_limited' in codes:
        hints.append('本轮工具调用次数或观测长度可能已达上限')
    if hints:
        tail = '（' + '；'.join(hints) + '）'
    return '\n\n【系统提示】' + '；'.join(parts) + tail + '。请稍后重试或联系管理员。'
