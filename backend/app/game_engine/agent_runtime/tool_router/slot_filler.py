from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonschema

from app.game_engine.agent_runtime.model_backends.protocols import ChatGenerativeBackend
from app.game_engine.agent_runtime.tool_router.paths import backend_root


def schema_path() -> Path:
    return (
        backend_root()
        / "app"
        / "models"
        / "agent_model"
        / "tool_router"
        / "schemas"
        / "tool_router_slot_output.schema.json"
    )


def repair_prompt_path_v1() -> Path:
    return (
        backend_root()
        / "app"
        / "models"
        / "agent_model"
        / "tool_router"
        / "prompts"
        / "slot_repair_v1.en.txt"
    )


def repair_prompt_text_v1() -> str:
    p = repair_prompt_path_v1()
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return (
            "Return one JSON object only, fixing syntax: target_hint, named_spans, "
            "entities, mandatory_tools. No prose outside the JSON."
        )


@lru_cache(maxsize=1)
def _slot_output_validator() -> jsonschema.Draft202012Validator:
    raw = json.loads(schema_path().read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(raw)


def validate_slot_against_schema(obj: Dict[str, Any]) -> bool:
    try:
        _slot_output_validator().validate(obj)
    except jsonschema.ValidationError:
        return False
    return True


def parse_slot_json(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


class SlotFiller:
    """Thin adapter: chat backend → JSON slot object → mandatory tool names."""

    def __init__(self, backend: ChatGenerativeBackend):
        self._backend = backend

    def extract(
        self,
        *,
        user_message: str,
        enrich_query: str,
        repair: bool = False,
    ) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        mandatory: List[str] = []
        sys_prompt = (
            "Output a single JSON object only. Keys: target_hint (string|null); "
            "named_spans (array of {text,type}); entities (array of "
            "{normalized_text,entity_type}); mandatory_tools (array of command names, may be empty)."
        )
        user_block = f"EnrichQuery:\n{enrich_query}\n\nUser:\n{user_message}"
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_block},
        ]
        res = self._backend.complete_chat(messages, max_new_tokens=256, temperature=0.0)
        obj = parse_slot_json(res.text)
        if (obj is None or not validate_slot_against_schema(obj)) and repair:
            repair_messages = messages + [
                {"role": "assistant", "content": res.text or ""},
                {"role": "user", "content": repair_prompt_text_v1()},
            ]
            res2 = self._backend.complete_chat(repair_messages, max_new_tokens=256, temperature=0.0)
            obj = parse_slot_json(res2.text)
        if obj is None or not validate_slot_against_schema(obj):
            return obj, []
        raw_mt = obj.get("mandatory_tools")
        if isinstance(raw_mt, list):
            mandatory = [str(x).strip() for x in raw_mt if str(x).strip()]
        return obj, sorted(set(mandatory))
