from __future__ import annotations

from typing import Any, Dict, List, Sequence


def extract_entity_spans_gliner(
    text: str,
    *,
    model_id: str,
    labels: Sequence[str],
) -> List[Dict[str, Any]]:
    """Optional GLiNER path; returns [] when dependency or model is unavailable."""
    if not model_id.strip():
        return []
    try:
        from gliner import GLiNER  # type: ignore
    except ImportError:
        return []
    try:
        model = GLiNER.from_pretrained(model_id)
        labels_list = list(labels) if labels else ["person", "organization", "location"]
        out = model.predict_entities(text or "", labels_list, threshold=0.35)
        return list(out) if isinstance(out, list) else []
    except Exception:
        return []
