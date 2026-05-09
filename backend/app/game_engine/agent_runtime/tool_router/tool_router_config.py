from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.game_engine.agent_runtime.tool_router.router_result import EnforcementLevel


@dataclass
class ToolRouterConfig:
    enabled: bool = False
    slot_slm_enabled: bool = False
    enforcement_level: EnforcementLevel = EnforcementLevel.hint_only
    k_default: int = 24
    k_info: int = 8
    # Opaque label for logs/replay; pairs with clarify_* numeric thresholds.
    threshold_revision: str = ""
    # If (top−second) margin <= this, signal clarify (see router_thresholds.router_should_clarify).
    clarify_margin_max: float = 0.05
    # Optional: also clarify when top score < this (joint rule).
    clarify_min_top_score: Optional[float] = None
    rules_path: str = "config/tool_router_rules.yaml"
    gliner_model_id: str = ""
    stage_b_disabled: bool = False


def parse_tool_router_config(extra: Optional[Dict[str, Any]]) -> ToolRouterConfig:
    raw = {}
    if isinstance(extra, dict):
        tr = extra.get("tool_router")
        if isinstance(tr, dict):
            raw = tr
    cfg = ToolRouterConfig()
    if raw.get("enabled") is True:
        cfg.enabled = True
    if raw.get("slot_slm_enabled") is True:
        cfg.slot_slm_enabled = True
    el = raw.get("enforcement_level")
    if isinstance(el, str) and el.strip():
        try:
            cfg.enforcement_level = EnforcementLevel(el.strip())
        except ValueError:
            cfg.enforcement_level = EnforcementLevel.hint_only
    for key, attr in (
        ("k_default", "k_default"),
        ("k_info", "k_info"),
    ):
        v = raw.get(key)
        if isinstance(v, int) and v > 0:
            setattr(cfg, attr, v)
    tr_rev = raw.get("threshold_revision")
    if isinstance(tr_rev, str) and tr_rev.strip():
        cfg.threshold_revision = tr_rev.strip()

    th = raw.get("router_thresholds")
    if isinstance(th, dict):
        cm = th.get("clarify_margin_max")
        if isinstance(cm, (int, float)) and cm >= 0:
            cfg.clarify_margin_max = float(cm)
        cts = th.get("clarify_min_top_score")
        if isinstance(cts, (int, float)):
            cfg.clarify_min_top_score = float(cts)

    cm_flat = raw.get("clarify_margin_max")
    if isinstance(cm_flat, (int, float)) and cm_flat >= 0:
        cfg.clarify_margin_max = float(cm_flat)
    cts_flat = raw.get("clarify_min_top_score")
    if isinstance(cts_flat, (int, float)):
        cfg.clarify_min_top_score = float(cts_flat)
    rp = raw.get("rules_path")
    if isinstance(rp, str) and rp.strip():
        cfg.rules_path = rp.strip()
    gid = raw.get("gliner_model_id")
    if isinstance(gid, str) and gid.strip():
        cfg.gliner_model_id = gid.strip()
    if raw.get("stage_b_disabled") is True:
        cfg.stage_b_disabled = True
    return cfg
