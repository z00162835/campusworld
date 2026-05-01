"""Resolve per-agent intent classifier settings (YAML extra + npc_agent.attributes)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.core.log import LoggerNames, get_logger
from app.game_engine.agent_runtime.agent_llm_extra import parse_bool_extra
from app.models.agent_model.intent_classifier.runtime.inference import clamp_intent_max_new_tokens

_LOG = get_logger(LoggerNames.GAME)

_INTENT_KEYS = frozenset(
    {
        "use_intent_slm",
        "artifact_dir",
        "intent_classifier_allowed_path_prefixes",
        "max_new_tokens",
        "system_prompt_file",
    }
)


def backend_root() -> Path:
    """Directory containing ``campusworld.py`` (the ``backend/`` folder)."""

    return Path(__file__).resolve().parent.parent.parent.parent


def default_intent_classifier_allow_prefixes(root: Path) -> List[Path]:
    """Built-in allowlist: packaged intent classifier artifacts tree."""

    return [
        (root / "app/models/agent_model/intent_classifier/artifacts").resolve(),
    ]


def _pick_from_mapping(m: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in _INTENT_KEYS:
        if k in m and m[k] is not None:
            out[k] = m[k]
    return out


def merge_intent_classifier_settings(
    extra: Optional[Mapping[str, Any]],
    node_attributes: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Merge ``agents.llm.*.extra`` slice with ``npc_agent.attributes.intent_classifier``."""

    base = _pick_from_mapping(extra or {})
    raw_ic = (node_attributes or {}).get("intent_classifier")
    if isinstance(raw_ic, dict):
        base.update(_pick_from_mapping(raw_ic))
    return base


def _resolve_path_entry(raw: str, backend: Path) -> Path:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p
    return (backend / raw).expanduser()


def _normalize_prefix_list(
    raw: Any,
    backend: Path,
) -> List[Path]:
    if isinstance(raw, str) and raw.strip():
        raw_list: Sequence[Any] = [raw.strip()]
    elif isinstance(raw, list):
        raw_list = raw
    else:
        raw_list = []
    out: List[Path] = []
    for item in raw_list:
        if item is None:
            continue
        s = str(item).strip()
        if not s:
            continue
        out.append(_resolve_path_entry(s, backend).resolve())
    if not out:
        out = default_intent_classifier_allow_prefixes(backend)
    return out


def _is_under_allowed(target: Path, prefixes: Sequence[Path]) -> bool:
    tr = target.resolve()
    for pref in prefixes:
        pr = pref.resolve()
        try:
            tr.relative_to(pr)
            return True
        except ValueError:
            continue
    return False


def _prompt_file_allowed(path: Path, artifact_prefixes: Sequence[Path], backend: Path) -> bool:
    """Allow packaged intent_classifier tree or the same prefixes as ``artifact_dir``."""

    pkg = (backend / "app/models/agent_model/intent_classifier").resolve()
    try:
        resolved = path.resolve()
    except OSError:
        return False
    if _is_under_allowed(resolved, [pkg]):
        return True
    return _is_under_allowed(resolved, artifact_prefixes)


def _validate_artifact_layout(root: Path) -> Optional[str]:
    adapter = root / "lora_adapter"
    cfg = root / "training_config.json"
    if not adapter.is_dir():
        return "missing_lora_adapter_directory"
    if not cfg.is_file():
        return "missing_training_config_json"
    return None


def _load_default_system_prompt() -> str:
    pkg = (
        backend_root()
        / "app/models/agent_model/intent_classifier/prompts/intent_classifier_system_prompt.txt"
    )
    return pkg.read_text(encoding="utf-8")


@dataclass(frozen=True)
class IntentClassifierRuntimeConfig:
    """Resolved intent SLM settings for one npc_agent tick worker."""

    use_intent_slm: bool
    artifact_root: Optional[Path]
    max_new_tokens: int
    system_prompt_text: str
    resolve_error: Optional[str] = None


def resolve_intent_classifier_runtime(
    extra: Optional[Mapping[str, Any]],
    node_attributes: Optional[Mapping[str, Any]],
    *,
    backend: Optional[Path] = None,
) -> IntentClassifierRuntimeConfig:
    merged = merge_intent_classifier_settings(extra, node_attributes)
    root = backend or backend_root()
    use_slm = parse_bool_extra(merged, "use_intent_slm", default=False)
    max_new_tokens = clamp_intent_max_new_tokens(merged.get("max_new_tokens"))
    prefixes = _normalize_prefix_list(merged.get("intent_classifier_allowed_path_prefixes"), root)

    sp_file = merged.get("system_prompt_file")
    if isinstance(sp_file, str) and sp_file.strip():
        sp_path = _resolve_path_entry(sp_file.strip(), root)
        try:
            spr = sp_path.resolve()
        except OSError:
            spr = None
        if spr is None:
            system_prompt_text = _load_default_system_prompt()
            _LOG.warning("intent_classifier_system_prompt_file_unreadable", extra={"path": str(sp_path)})
        elif not _prompt_file_allowed(spr, prefixes, root):
            system_prompt_text = _load_default_system_prompt()
            _LOG.warning("intent_classifier_system_prompt_path_denied", extra={"path": str(spr)})
        else:
            try:
                system_prompt_text = spr.read_text(encoding="utf-8")
            except OSError:
                system_prompt_text = _load_default_system_prompt()
                _LOG.warning("intent_classifier_system_prompt_file_unreadable", extra={"path": str(spr)})
    else:
        system_prompt_text = _load_default_system_prompt()

    if not use_slm:
        return IntentClassifierRuntimeConfig(
            use_intent_slm=False,
            artifact_root=None,
            max_new_tokens=max_new_tokens,
            system_prompt_text=system_prompt_text,
            resolve_error=None,
        )

    raw_ad = merged.get("artifact_dir")
    if not isinstance(raw_ad, str) or not raw_ad.strip():
        return IntentClassifierRuntimeConfig(
            use_intent_slm=True,
            artifact_root=None,
            max_new_tokens=max_new_tokens,
            system_prompt_text=system_prompt_text,
            resolve_error="missing_artifact_dir",
        )

    try:
        candidate = _resolve_path_entry(raw_ad.strip(), root)
        resolved_root = candidate.resolve()
    except OSError as exc:
        return IntentClassifierRuntimeConfig(
            use_intent_slm=True,
            artifact_root=None,
            max_new_tokens=max_new_tokens,
            system_prompt_text=system_prompt_text,
            resolve_error=f"path_resolve_error:{exc}",
        )

    if not _is_under_allowed(resolved_root, prefixes):
        _LOG.warning(
            "intent_classifier_artifact_path_denied",
            extra={"artifact_dir": str(resolved_root), "allowed_prefixes": [str(p) for p in prefixes]},
        )
        return IntentClassifierRuntimeConfig(
            use_intent_slm=True,
            artifact_root=None,
            max_new_tokens=max_new_tokens,
            system_prompt_text=system_prompt_text,
            resolve_error="artifact_dir_not_allowlisted",
        )

    layout_err = _validate_artifact_layout(resolved_root)
    if layout_err:
        _LOG.warning(
            "intent_classifier_artifact_layout_invalid",
            extra={"artifact_dir": str(resolved_root), "reason": layout_err},
        )
        return IntentClassifierRuntimeConfig(
            use_intent_slm=True,
            artifact_root=None,
            max_new_tokens=max_new_tokens,
            system_prompt_text=system_prompt_text,
            resolve_error=layout_err,
        )

    return IntentClassifierRuntimeConfig(
        use_intent_slm=True,
        artifact_root=resolved_root,
        max_new_tokens=max_new_tokens,
        system_prompt_text=system_prompt_text,
        resolve_error=None,
    )


def build_intent_classifier_for_tick(cfg: IntentClassifierRuntimeConfig):
    """Return chained SLM→rule classifier, or None to use plain rule path in classify_intent."""

    from app.game_engine.agent_runtime.intent_classifier_interface import (
        ChainedIntentClassifier,
        RuleFallbackIntentClassifier,
    )
    from app.game_engine.agent_runtime.peft_intent_classifier import PeftIntentClassifier

    if not cfg.use_intent_slm or cfg.artifact_root is None:
        if cfg.use_intent_slm and cfg.resolve_error:
            _LOG.warning(
                "intent_classifier_slm_disabled",
                extra={"reason": cfg.resolve_error},
            )
        return None
    try:
        import peft  # noqa: F401
    except ImportError:
        _LOG.warning("intent_classifier_peft_import_unavailable", extra={})
        return None
    primary = PeftIntentClassifier(
        artifact_root=cfg.artifact_root,
        max_new_tokens=cfg.max_new_tokens,
        system_prompt=cfg.system_prompt_text,
    )
    return ChainedIntentClassifier(primary=primary, fallback=RuleFallbackIntentClassifier())
