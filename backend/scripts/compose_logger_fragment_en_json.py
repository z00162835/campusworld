#!/usr/bin/env python3
"""Build logger_fragment_en.json from _logger_zh_fragments.json + logger_fragment_en_lines.txt."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    zh = json.loads((root / "_logger_zh_fragments.json").read_text(encoding="utf-8"))
    lines = (root / "logger_fragment_en_lines.txt").read_text(encoding="utf-8").splitlines()
    if len(zh) != len(lines):
        raise SystemExit(f"length mismatch zh={len(zh)} lines={len(lines)}")
    mapping = dict(zip(zh, lines))
    mapping["配置加载成功:\n"] = "Configuration loaded successfully:\n"
    out = root / "logger_fragment_en.json"
    out.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} entries={len(mapping)}")


if __name__ == "__main__":
    main()
