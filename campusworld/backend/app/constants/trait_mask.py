"""
Bit semantics for ``trait_mask`` (BIGINT) on graph nodes.

Canonical documentation: ``docs/database/SPEC/features/`` (trait class / mask).
"""

from __future__ import annotations

# --- Single bits (bit0 .. bit9) ---

CONCEPTUAL = 1 << 0  # 1
FACTUAL = 1 << 1  # 2
SPATIAL = 1 << 2  # 4
PERCEPTUAL = 1 << 3  # 8
TEMPORAL = 1 << 4  # 16
CONTROLLABLE = 1 << 5  # 32
EVENT_BASED = 1 << 6  # 64
MOBILE = 1 << 7  # 128
AUTO = 1 << 8  # 256
LOAD_BEARING = 1 << 9  # 512

# --- Common composites (HiCampus / examples) ---

SPATIAL_LOAD_BEARING = SPATIAL | LOAD_BEARING  # 516
DEVICE_TYPICAL_IOT_END = FACTUAL | PERCEPTUAL | TEMPORAL | CONTROLLABLE  # 58
ACCESS_TERMINAL = DEVICE_TYPICAL_IOT_END | SPATIAL | EVENT_BASED  # 126
WORLD_OBJECT_BASE = PERCEPTUAL | LOAD_BEARING  # 520
NPC_AGENT = FACTUAL | TEMPORAL | CONTROLLABLE | EVENT_BASED | MOBILE | AUTO  # 498
LOGICAL_ZONE = CONCEPTUAL | EVENT_BASED  # 65
WORLD_ENTRANCE = CONCEPTUAL | SPATIAL | CONTROLLABLE | EVENT_BASED  # 101
LOCATION_RELATIONSHIP_EDGE = CONCEPTUAL | SPATIAL  # 5 (connects_to / contains / located_in)

MASK_QUERY_ZERO_DESCRIPTION = (
    "trait_mask 过滤：0 表示不按位过滤（全量）。非 0 时使用按位与匹配；"
    "各位含义见数据库 SPEC 与本模块常量说明。"
)
