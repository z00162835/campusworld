"""Safe str.format for appearance templates (missing keys → empty string)."""

from __future__ import annotations

import re
from typing import Any


def safe_format_template(template: str, **kwargs: Any) -> str:
    keys = set(re.findall(r"\{(\w+)\}", template))
    merged = {k: kwargs[k] if k in kwargs and kwargs[k] is not None else "" for k in keys}
    return template.format(**merged)
