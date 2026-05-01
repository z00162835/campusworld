"""Shared greedy-decode inference for runtime and eval (keep one implementation)."""

from __future__ import annotations

import inspect
import json
from typing import Any, Dict, List, Mapping, Tuple

from app.models.agent_model.intent_classifier.train.dataset_builder import VALID_LABELS

# Upper bound for greedy decode budget (misconfiguration guardrail).
MAX_INTENT_CLASSIFIER_NEW_TOKENS = 256
MIN_INTENT_CLASSIFIER_NEW_TOKENS = 8


def clamp_intent_max_new_tokens(raw: Any) -> int:
    """Clamp configured decode budget to a safe range."""

    try:
        n = int(raw) if raw is not None else 96
    except (TypeError, ValueError):
        n = 96
    if n < MIN_INTENT_CLASSIFIER_NEW_TOKENS:
        n = MIN_INTENT_CLASSIFIER_NEW_TOKENS
    if n > MAX_INTENT_CLASSIFIER_NEW_TOKENS:
        n = MAX_INTENT_CLASSIFIER_NEW_TOKENS
    return n


def extract_json_object_for_intent(raw: str) -> str:
    """Strip markdown fences and take the first JSON object via ``JSONDecoder.raw_decode``."""

    text = (raw or "").strip()
    if not text:
        raise ValueError("empty model output")
    if text.startswith("```"):
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1 :].strip()
        if text.lower().startswith("json"):
            nl2 = text.find("\n")
            if nl2 != -1:
                text = text[nl2 + 1 :].strip()
        fence = text.rfind("```")
        if fence != -1:
            text = text[:fence].strip()
    dec = json.JSONDecoder()
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in model output")
    _, end = dec.raw_decode(text, start)
    return text[start:end]


def intent_classifier_torch_device_dtype():
    """cuda > mps > cpu with dtype aligned to eval script."""

    import torch

    if torch.cuda.is_available():
        return torch.device("cuda"), torch.float16
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return torch.device("mps"), torch.float16
    return torch.device("cpu"), torch.float32


def chat_template_kwargs_for_intent(tokenizer) -> Dict[str, Any]:
    """Pass enable_thinking=False when the tokenizer template supports it (Qwen3)."""

    try:
        sig = inspect.signature(tokenizer.apply_chat_template)
        if "enable_thinking" in sig.parameters:
            return {"enable_thinking": False}
    except (TypeError, ValueError):
        pass
    return {}


def greedy_decode_intent_json(
    *,
    model,
    tokenizer,
    device,
    system_prompt: str,
    user_message: str,
    max_new_tokens: int,
) -> Dict[str, Any]:
    """Single-turn chat prompt → strict JSON object with intent label."""

    import torch

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_message},
    ]
    tmpl_kw = chat_template_kwargs_for_intent(tokenizer)
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        **tmpl_kw,
    )
    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    nt = clamp_intent_max_new_tokens(max_new_tokens)
    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=int(nt),
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    generated = output_ids[0][inputs["input_ids"].shape[-1] :]
    text = tokenizer.decode(generated, skip_special_tokens=True).strip()
    payload = extract_json_object_for_intent(text)
    return json.loads(payload)


def validate_intent_payload(obj: Mapping[str, Any]) -> Tuple[str, float, List[str]]:
    intent = str(obj.get("intent") or "").strip()
    if intent not in VALID_LABELS:
        raise ValueError(f"invalid intent {intent!r}")
    conf_raw = obj.get("confidence", 0.0)
    try:
        confidence = float(conf_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    rt = obj.get("reason_tokens") or []
    reason_tokens = [str(x) for x in rt] if isinstance(rt, list) else []
    return intent, confidence, reason_tokens
