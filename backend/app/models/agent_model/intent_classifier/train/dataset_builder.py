"""JSONL labeled intents → chat messages for causal LM supervised fine-tuning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableSequence, Optional, Sequence, Tuple


VALID_LABELS = frozenset({"informational", "verify_state", "execute"})


@dataclass(frozen=True)
class IntentTrainSample:
    text: str
    label: str
    sample_id: Optional[str] = None
    language: Optional[str] = None
    reason_tokens: Tuple[str, ...] = ()
    has_execute_confirmation: Optional[bool] = None
    conflict_case: Optional[bool] = None


def load_jsonl(path: Path) -> List[IntentTrainSample]:
    rows: List[IntentTrainSample] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        obj: Mapping[str, Any] = json.loads(line)
        text = str(obj.get("text") or "").strip()
        label = str(obj.get("label") or "").strip()
        if label not in VALID_LABELS:
            raise ValueError(f"{path}:{line_no}: invalid label {label!r}, expected one of {sorted(VALID_LABELS)}")
        if not text:
            raise ValueError(f"{path}:{line_no}: empty text")
        rt = obj.get("reason_tokens")
        reason_tokens: Tuple[str, ...] = ()
        if isinstance(rt, list):
            reason_tokens = tuple(str(x) for x in rt if x is not None)
        rows.append(
            IntentTrainSample(
                text=text,
                label=label,
                sample_id=obj.get("id") if obj.get("id") is not None else None,
                language=str(obj["language"]) if obj.get("language") is not None else None,
                reason_tokens=reason_tokens,
                has_execute_confirmation=obj.get("has_execute_confirmation")
                if "has_execute_confirmation" in obj
                else None,
                conflict_case=obj.get("conflict_case") if "conflict_case" in obj else None,
            )
        )
    return rows


def build_classifier_payload(sample: IntentTrainSample) -> Dict[str, object]:
    """Target JSON aligned with runtime/schema.json (training teaches exact keys)."""

    confidence = 0.92
    if sample.conflict_case is True:
        confidence = 0.78
    if sample.label == "informational":
        confidence = min(confidence, 0.88)
    reason_tokens = list(sample.reason_tokens) if sample.reason_tokens else []
    return {
        "intent": sample.label,
        "confidence": confidence,
        "reason_tokens": reason_tokens,
        "source": "small_model",
    }


def build_chat_turns(system_prompt: str, sample: IntentTrainSample) -> List[Dict[str, str]]:
    assistant_text = json.dumps(build_classifier_payload(sample), ensure_ascii=False)
    return [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": sample.text},
        {"role": "assistant", "content": assistant_text},
    ]


def train_val_indices(n: int, val_ratio: float, seed: int) -> Tuple[List[int], List[int]]:
    if n <= 0:
        return [], []
    if val_ratio <= 0 or n < 2:
        return list(range(n)), []
    cap_val = max(1, int(round(n * val_ratio)))
    cap_val = min(cap_val, n - 1)
    order = list(range(n))
    rnd = seed
    for i in range(n - 1, 0, -1):
        rnd = (1103515245 * rnd + 12345) & 0x7FFFFFFF
        j = rnd % (i + 1)
        order[i], order[j] = order[j], order[i]
    val_idx = sorted(order[:cap_val])
    train_idx = sorted(order[cap_val:])
    return train_idx, val_idx


def split_samples(samples: Sequence[IntentTrainSample], val_ratio: float, seed: int) -> Tuple[List[int], List[int]]:
    return train_val_indices(len(samples), val_ratio=val_ratio, seed=seed)
