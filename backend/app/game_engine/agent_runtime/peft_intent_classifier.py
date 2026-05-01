"""Lazy-loaded Peft intent classifier for Plan-phase routing hints."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.log import LoggerNames, get_logger
from app.game_engine.agent_runtime.intent_classifier_interface import IntentClassification, IntentClassifier
from app.models.agent_model.intent_classifier.runtime.inference import (
    greedy_decode_intent_json,
    intent_classifier_torch_device_dtype,
    validate_intent_payload,
)

_LOG = get_logger(LoggerNames.GAME)

_CACHE_LOCK = threading.Lock()
_BUNDLE_CACHE: Dict[str, "_LoadedPeftBundle"] = {}


@dataclass
class _LoadedPeftBundle:
    tokenizer: Any
    model: Any
    device: Any


def _training_base_model_id(artifact_root: Path) -> str:
    cfg_path = artifact_root / "training_config.json"
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    bid = str(raw.get("base_model_id") or "").strip()
    if not bid:
        raise ValueError("training_config.json missing base_model_id")
    return bid


def _load_bundle(artifact_root: Path) -> _LoadedPeftBundle:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    adapter_dir = artifact_root / "lora_adapter"
    base_model_id = _training_base_model_id(artifact_root)
    tokenizer = AutoTokenizer.from_pretrained(str(adapter_dir), trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    device, torch_dtype = intent_classifier_torch_device_dtype()
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        trust_remote_code=True,
        torch_dtype=torch_dtype,
    )
    model = PeftModel.from_pretrained(base_model, str(adapter_dir))
    model.to(device)
    model.eval()
    return _LoadedPeftBundle(tokenizer=tokenizer, model=model, device=device)


def _get_bundle(artifact_root: Path) -> _LoadedPeftBundle:
    key = str(artifact_root.resolve())
    with _CACHE_LOCK:
        if key in _BUNDLE_CACHE:
            return _BUNDLE_CACHE[key]
        bundle = _load_bundle(artifact_root)
        _BUNDLE_CACHE[key] = bundle
        _LOG.info("intent_slm_bundle_loaded", extra={"artifact_root": key})
        return bundle


class PeftIntentClassifier(IntentClassifier):
    """Greedy JSON intent classifier; raises on failure so chained fallback runs."""

    def __init__(
        self,
        *,
        artifact_root: Path,
        max_new_tokens: int,
        system_prompt: str,
    ):
        self._root = artifact_root.resolve()
        self._max_new_tokens = int(max_new_tokens)
        self._system_prompt = system_prompt

    def classify_intent(
        self,
        user_message: str,
        *,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> IntentClassification:
        _ = agent_id
        _ = metadata
        text = (user_message or "").strip()
        if not text:
            raise ValueError("empty_user_message")

        t0 = time.perf_counter()
        bundle = _get_bundle(self._root)
        try:
            obj = greedy_decode_intent_json(
                model=bundle.model,
                tokenizer=bundle.tokenizer,
                device=bundle.device,
                system_prompt=self._system_prompt,
                user_message=text,
                max_new_tokens=self._max_new_tokens,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            _LOG.warning(
                "intent_slm_inference_failed",
                extra={"error": str(exc), "intent_slm_latency_ms": round(elapsed_ms, 3)},
            )
            raise

        intent, confidence, reason_tokens = validate_intent_payload(obj)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        _LOG.info(
            "intent_slm_ok",
            extra={
                "intent": intent,
                "intent_confidence": confidence,
                "intent_slm_latency_ms": round(elapsed_ms, 3),
                "intent_source": "small_model",
            },
        )
        return IntentClassification(
            intent=intent,
            confidence=confidence,
            reason_tokens=reason_tokens,
            source="small_model",
            latency_ms=round(elapsed_ms, 3),
        )
