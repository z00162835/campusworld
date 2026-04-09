"""
Layered validator (L1–L5) for HiCampus declarative world data package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import yaml

from .contracts import (
    DataPackageError,
    ERROR_WORLD_DATA_BASELINE_MISMATCH,
    ERROR_WORLD_DATA_INVALID,
    ERROR_WORLD_DATA_REFERENCE_BROKEN,
    ERROR_WORLD_DATA_SCHEMA_UNSUPPORTED,
    ERROR_WORLD_DATA_SEMANTIC_CONFLICT,
    ERROR_WORLD_DATA_UNAVAILABLE,
)
from .content_merge import merge_description_sidecars, normalize_spatial_rows, validate_spatial_p0
from .graph_profile import _PACKAGE_TO_DB_NODE_TYPE
from db.ontology.load import load_graph_seed_node_type_overrides

# Schema versions supported by this validator (see package_meta.schema_version).
SUPPORTED_SCHEMA_VERSIONS = frozenset({2})

ALLOWED_REL_TYPE_CODES = frozenset(
    {
        "contains",
        "connects_to",
        "located_in",
        "has_entry",
        "served_by",
        "adjacent_to",
        "governs",
        "applies_to",
        "enables",
        "requires",
        "executes",
        "located_in_zone",
    }
)

ALLOWED_CONCEPT_SCOPES = frozenset(
    {"world", "room", "zone", "npc", "building", "floor", "global"}
)

ALLOWED_CONCEPT_TYPES = frozenset({"goal", "process", "rule", "behavior", "skill"})

_BASELINE_PROFILE_PATH = Path(__file__).resolve().parent / "baseline_profile.yaml"
_WORLD_ENTRY_ROOM_ID = "hicampus_gate"


def _load_l4_baseline() -> tuple[Dict[str, int], Set[str]]:
    """L4 HiCampus spatial baseline: floors per building_code and required room ids."""
    default_floors: Dict[str, int] = {
        "F1": 23,
        "F2": 3,
        "F3": 6,
        "F4": 7,
        "F5": 3,
        "F6": 9,
    }
    default_rooms: Set[str] = {"hicampus_gate", "hicampus_bridge", "hicampus_plaza"}
    if not _BASELINE_PROFILE_PATH.is_file():
        return default_floors, default_rooms
    raw = yaml.safe_load(_BASELINE_PROFILE_PATH.read_text(encoding="utf-8")) or {}
    fe = raw.get("floor_expect") or {}
    if not isinstance(fe, dict):
        fe = {}
    floor_expect: Dict[str, int] = {}
    for k, v in fe.items():
        try:
            floor_expect[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    if not floor_expect:
        floor_expect = default_floors
    rr = raw.get("required_rooms") or []
    if isinstance(rr, list) and rr:
        required_rooms = {str(x) for x in rr}
    else:
        required_rooms = default_rooms
    return floor_expect, required_rooms


def _build_connects_to_adjacency(relationships: List[Dict[str, Any]], room_ids: Set[str]) -> Dict[str, List[str]]:
    adj: Dict[str, List[str]] = {rid: [] for rid in room_ids}
    for rel in relationships:
        if not isinstance(rel, dict):
            continue
        if str(rel.get("rel_type_code") or "") != "connects_to":
            continue
        src = str(rel.get("source_id") or "")
        tgt = str(rel.get("target_id") or "")
        if src in room_ids and tgt in room_ids:
            adj.setdefault(src, []).append(tgt)
    return adj


def _reachable_from(start: str, adj: Dict[str, List[str]]) -> Set[str]:
    if start not in adj:
        return set()
    seen: Set[str] = {start}
    q: List[str] = [start]
    while q:
        cur = q.pop(0)
        for nxt in adj.get(cur, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            q.append(nxt)
    return seen


def _find_building_entry_hubs(
    *,
    buildings: List[Dict[str, Any]],
    floors: List[Dict[str, Any]],
    rooms: List[Dict[str, Any]],
) -> Dict[str, str]:
    """
    Return {building_code: entry_room_id}.

    Convention: entry hub is the building's lowest floor_number/floor_no room whose id endswith
    '_circulation_01'. This matches the topology generator contract.
    """
    building_by_id: Dict[str, Dict[str, Any]] = {str(b.get("id")): b for b in buildings if b.get("id")}
    floors_by_building: Dict[str, List[Dict[str, Any]]] = {}
    for f in floors:
        bid = str(f.get("building_id") or "")
        if bid and bid in building_by_id:
            floors_by_building.setdefault(bid, []).append(f)

    # Choose the "entry floor" as the lowest numeric floor.
    entry_floor_by_building: Dict[str, str] = {}
    for bid, flist in floors_by_building.items():
        def floor_no(row: Dict[str, Any]) -> int:
            try:
                return int(row.get("floor_number") or row.get("floor_no") or 1)
            except (TypeError, ValueError):
                return 1

        flist = sorted(flist, key=floor_no)
        fid = str(flist[0].get("id") or "")
        if fid:
            entry_floor_by_building[bid] = fid

    # Find circulation hub on entry floor.
    hub_by_building_code: Dict[str, str] = {}
    for r in rooms:
        if not isinstance(r, dict):
            continue
        rid = str(r.get("id") or "")
        if not rid or not rid.endswith("_circulation_01"):
            continue
        fid = str(r.get("floor_id") or "")
        if not fid:
            continue
        for bid, entry_fid in entry_floor_by_building.items():
            if fid != entry_fid:
                continue
            b = building_by_id.get(bid) or {}
            code = str(b.get("building_code") or bid).strip().upper()
            # Prefer deterministic pick; if duplicates exist, keep first seen.
            hub_by_building_code.setdefault(code, rid)
    return hub_by_building_code


def _validate_world_entry_reachability(
    *,
    rooms: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    entry_room_id: str,
    required_entry_hubs: Dict[str, str],
) -> None:
    room_ids: Set[str] = {str(r.get("id")) for r in rooms if isinstance(r, dict) and r.get("id")}
    adj = _build_connects_to_adjacency(relationships, room_ids)
    reachable = _reachable_from(entry_room_id, adj)
    missing: List[Tuple[str, str]] = [
        (bcode, hub) for bcode, hub in sorted(required_entry_hubs.items()) if hub not in reachable
    ]
    if not missing:
        return
    missing_str = ", ".join([f"{bcode}:{hub}" for bcode, hub in missing])
    raise DataPackageError(
        ERROR_WORLD_DATA_SEMANTIC_CONFLICT,
        (
            f"world entry reachability broken: from {entry_room_id} cannot reach building entry hubs "
            f"({missing_str}). Hint: run topology generator "
            f"'python -m app.games.hicampus.package.topology_connect_generate --write' to regenerate connects_to."
        ),
    )


def _validate_connects_to_direction_conflicts(relationships: List[Dict[str, Any]], room_ids: Set[str]) -> None:
    """
    Hard rule: one source+direction must map to exactly one target.
    """
    buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for rel in relationships:
        if not isinstance(rel, dict):
            continue
        if str(rel.get("rel_type_code") or "") != "connects_to":
            continue
        src = str(rel.get("source_id") or "")
        if src not in room_ids:
            continue
        attrs = rel.get("attributes") if isinstance(rel.get("attributes"), dict) else {}
        direction = str(attrs.get("direction") or "").strip().lower()
        if not direction:
            continue
        buckets.setdefault((src, direction), []).append(rel)

    for (src, direction), rels in buckets.items():
        if len(rels) <= 1:
            continue
        rel_ids: List[str] = []
        for rel in rels:
            rel_ids.append(str(rel.get("id") or "?"))
        raise DataPackageError(
            ERROR_WORLD_DATA_SEMANTIC_CONFLICT,
            (
                f"direction conflict: source={src} direction={direction} has multiple connects_to "
                f"(rels={','.join(rel_ids)}). Rule: one room cannot reach more than one room on the same direction."
            ),
        )


REQUIRED_FILES = [
    "world.yaml",
    "buildings.yaml",
    "floors.yaml",
    "rooms.yaml",
    "relationships.yaml",
    "package_meta.yaml",
    "entities/npcs.yaml",
    "entities/items.yaml",
    "entities/zones.yaml",
    "concepts/goals.yaml",
    "concepts/processes.yaml",
    "concepts/rules.yaml",
    "concepts/behaviors.yaml",
    "concepts/skills.yaml",
]


def _read_yaml(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
        return yaml.safe_load(text) or {}
    except Exception as exc:
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"invalid yaml: {path.name} ({exc})") from exc


def _require_list(doc: Dict[str, Any], key: str, file_name: str) -> List[Dict[str, Any]]:
    value = doc.get(key, [])
    if not isinstance(value, list):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"{file_name}.{key} must be list")
    return value


def _parse_schema_version(raw: Any) -> int:
    if raw is None:
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, "package_meta.schema_version is required")
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, "package_meta.schema_version must be int") from exc


def _validate_entity_row(row: Dict[str, Any], bucket: str) -> None:
    rid = row.get("id")
    if not rid:
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"entity id required in {bucket}")
    if not row.get("type_code"):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"entity.type_code required: {rid}")
    if not row.get("entity_kind"):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"entity.entity_kind required: {rid}")
    if not row.get("display_name"):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"entity.display_name required: {rid}")
    if not row.get("location_ref") and not row.get("zone_ref"):
        raise DataPackageError(ERROR_WORLD_DATA_SEMANTIC_CONFLICT, f"entity must be locatable: {rid}")
    tags = row.get("tags", [])
    if not isinstance(tags, list):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"entity.tags must be list: {rid}")
    attrs = row.get("attributes", {})
    if attrs is None:
        attrs = {}
    if not isinstance(attrs, dict):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"entity.attributes must be dict: {rid}")
    pd = row.get("presentation_domains")
    if not isinstance(pd, list) or not pd:
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"entity.presentation_domains required: {rid}")
    locks = row.get("access_locks")
    if not isinstance(locks, dict):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"entity.access_locks must be dict: {rid}")
    if not row.get("source_ref"):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"entity.source_ref required: {rid}")


def _validate_concept_row(row: Dict[str, Any], family: str) -> None:
    cid = row.get("id")
    if not cid:
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"concept id required in {family}")
    ct = str(row.get("concept_type", "") or "").lower()
    if ct not in ALLOWED_CONCEPT_TYPES:
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"concept.concept_type invalid: {cid}")
    if not row.get("name"):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"concept.name required: {cid}")
    scope = str(row.get("scope", "") or "").lower()
    if scope not in ALLOWED_CONCEPT_SCOPES:
        raise DataPackageError(ERROR_WORLD_DATA_SEMANTIC_CONFLICT, f"concept.scope invalid: {cid}")
    if row.get("version") is None:
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"concept.version required: {cid}")
    definition = row.get("definition")
    if not isinstance(definition, dict):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"concept.definition must be dict: {cid}")
    bindings = row.get("bindings", [])
    if not isinstance(bindings, list):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"concept.bindings must be list: {cid}")
    tags = row.get("tags", [])
    if not isinstance(tags, list):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"concept.tags must be list: {cid}")
    attrs = row.get("attributes", {})
    if attrs is None:
        attrs = {}
    if not isinstance(attrs, dict):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"concept.attributes must be dict: {cid}")
    if not row.get("source_ref"):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"concept.source_ref required: {cid}")


def validate_data_package(data_root: Path) -> Dict[str, Any]:
    # L1: existence
    if not data_root.exists():
        raise DataPackageError(ERROR_WORLD_DATA_UNAVAILABLE, f"data directory not found: {data_root}")
    missing = [f for f in REQUIRED_FILES if not (data_root / f).exists()]
    if missing:
        raise DataPackageError(ERROR_WORLD_DATA_UNAVAILABLE, f"required files missing: {missing}")

    # L2: structure
    world_doc = _read_yaml(data_root / "world.yaml")
    buildings_doc = _read_yaml(data_root / "buildings.yaml")
    floors_doc = _read_yaml(data_root / "floors.yaml")
    rooms_doc = _read_yaml(data_root / "rooms.yaml")
    rels_doc = _read_yaml(data_root / "relationships.yaml")
    meta_doc = _read_yaml(data_root / "package_meta.yaml")
    npcs_doc = _read_yaml(data_root / "entities/npcs.yaml")
    items_doc = _read_yaml(data_root / "entities/items.yaml")
    zones_doc = _read_yaml(data_root / "entities/zones.yaml")
    goals_doc = _read_yaml(data_root / "concepts/goals.yaml")
    processes_doc = _read_yaml(data_root / "concepts/processes.yaml")
    rules_doc = _read_yaml(data_root / "concepts/rules.yaml")
    behaviors_doc = _read_yaml(data_root / "concepts/behaviors.yaml")
    skills_doc = _read_yaml(data_root / "concepts/skills.yaml")

    world = world_doc.get("world", {})
    if not isinstance(world, dict) or not world.get("id") or not world.get("world_id"):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, "world.yaml.world requires id/world_id")

    buildings = _require_list(buildings_doc, "buildings", "buildings.yaml")
    floors = _require_list(floors_doc, "floors", "floors.yaml")
    rooms = _require_list(rooms_doc, "rooms", "rooms.yaml")
    relationships = _require_list(rels_doc, "relationships", "relationships.yaml")

    entities = {
        "npcs": _require_list(npcs_doc, "npcs", "entities/npcs.yaml"),
        "items": _require_list(items_doc, "items", "entities/items.yaml"),
        "zones": _require_list(zones_doc, "zones", "entities/zones.yaml"),
    }
    concepts = {
        "goals": _require_list(goals_doc, "goals", "concepts/goals.yaml"),
        "processes": _require_list(processes_doc, "processes", "concepts/processes.yaml"),
        "rules": _require_list(rules_doc, "rules", "concepts/rules.yaml"),
        "behaviors": _require_list(behaviors_doc, "behaviors", "concepts/behaviors.yaml"),
        "skills": _require_list(skills_doc, "skills", "concepts/skills.yaml"),
    }

    if not isinstance(meta_doc, dict) or not meta_doc.get("package_version"):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, "package_meta.yaml requires package_version")

    schema_ver = _parse_schema_version(meta_doc.get("schema_version"))
    if schema_ver not in SUPPORTED_SCHEMA_VERSIONS:
        raise DataPackageError(
            ERROR_WORLD_DATA_SCHEMA_UNSUPPORTED,
            f"schema_version {schema_ver} not in supported {sorted(SUPPORTED_SCHEMA_VERSIONS)}",
        )

    # Entity / concept row contracts (L2 + L5 prep)
    for bucket, arr in entities.items():
        for row in arr:
            if not isinstance(row, dict):
                raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"entity row must be object in {bucket}")
            _validate_entity_row(row, bucket)

    all_concept_ids: Set[str] = set()
    for family, arr in concepts.items():
        for row in arr:
            if not isinstance(row, dict):
                raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"concept row must be object in {family}")
            _validate_concept_row(row, family)
            all_concept_ids.add(str(row["id"]))

    # L3: references
    building_ids: Set[str] = {str(x.get("id")) for x in buildings if x.get("id")}
    floor_ids: Set[str] = {str(x.get("id")) for x in floors if x.get("id")}
    room_ids: Set[str] = {str(x.get("id")) for x in rooms if x.get("id")}
    zone_ids: Set[str] = {str(x.get("id")) for x in entities["zones"] if x.get("id")}
    npc_ids: Set[str] = {str(x.get("id")) for x in entities["npcs"] if x.get("id")}
    item_ids: Set[str] = {str(x.get("id")) for x in entities["items"] if x.get("id")}
    all_entity_ids: Set[str] = set().union(zone_ids, npc_ids, item_ids)

    for floor in floors:
        if str(floor.get("building_id")) not in building_ids:
            raise DataPackageError(ERROR_WORLD_DATA_REFERENCE_BROKEN, f"broken floor.building_id: {floor.get('id')}")
    for room in rooms:
        if str(room.get("floor_id")) not in floor_ids:
            raise DataPackageError(ERROR_WORLD_DATA_REFERENCE_BROKEN, f"broken room.floor_id: {room.get('id')}")

    allowed_pkg_types = frozenset(_PACKAGE_TO_DB_NODE_TYPE.keys())
    for bucket, arr in entities.items():
        for row in arr:
            eid = row.get("id")
            tc = str(row.get("type_code", "") or "")
            if tc not in allowed_pkg_types:
                raise DataPackageError(
                    ERROR_WORLD_DATA_REFERENCE_BROKEN,
                    f"entity type_code not mapped for graph profile: {bucket} {eid} ({tc})",
                )
            loc = row.get("location_ref")
            if loc and str(loc) not in room_ids:
                raise DataPackageError(
                    ERROR_WORLD_DATA_REFERENCE_BROKEN,
                    f"entity location_ref not a room id: {bucket} {eid} -> {loc}",
                )
            zref = row.get("zone_ref")
            if not zref:
                continue
            # Zones use zone_ref as their spatial anchor (often a room id).
            if bucket == "zones":
                if str(zref) not in room_ids:
                    raise DataPackageError(
                        ERROR_WORLD_DATA_REFERENCE_BROKEN,
                        f"zone.zone_ref not a room id: {eid} -> {zref}",
                    )
            else:
                if str(zref) not in zone_ids:
                    raise DataPackageError(
                        ERROR_WORLD_DATA_REFERENCE_BROKEN,
                        f"entity zone_ref not a zone id: {bucket} {eid} -> {zref}",
                    )

    spatial_object_ids: Set[str] = {str(world["id"])} | building_ids | floor_ids | room_ids | zone_ids
    relationship_endpoint_ids: Set[str] = spatial_object_ids | npc_ids | item_ids | all_concept_ids

    for rel in relationships:
        if not isinstance(rel, dict):
            raise DataPackageError(ERROR_WORLD_DATA_INVALID, "relationship row must be object")
        rid = rel.get("id")
        rtc = str(rel.get("rel_type_code", "") or "")
        if not rtc:
            raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"relationship.rel_type_code required: {rid}")
        if rtc not in ALLOWED_REL_TYPE_CODES:
            raise DataPackageError(
                ERROR_WORLD_DATA_SEMANTIC_CONFLICT,
                f"relationship.rel_type_code not allowed: {rid} ({rtc})",
            )
        src = str(rel.get("source_id", ""))
        tgt = str(rel.get("target_id", ""))
        if src not in relationship_endpoint_ids or tgt not in relationship_endpoint_ids:
            raise DataPackageError(ERROR_WORLD_DATA_REFERENCE_BROKEN, f"broken relationship endpoints: {rid}")

    # L4: spatial baseline (HiCampus — package/baseline_profile.yaml)
    floor_expect, required_rooms = _load_l4_baseline()
    for b in buildings:
        code = str(b.get("building_code", ""))
        if code in floor_expect and int(b.get("floors_total", 0)) != floor_expect[code]:
            raise DataPackageError(ERROR_WORLD_DATA_BASELINE_MISMATCH, f"floors mismatch: {code}")
    if not required_rooms.issubset(room_ids):
        raise DataPackageError(ERROR_WORLD_DATA_BASELINE_MISMATCH, "missing gate/bridge/plaza")

    # L5a: optional description sidecars + row normalization + spatial P0 (F07)
    spatial_pre = {"buildings": buildings, "floors": floors, "rooms": rooms}
    merge_description_sidecars(data_root, spatial_pre)
    normalize_spatial_rows(spatial_pre)
    validate_spatial_p0(spatial_pre, required_room_ids=required_rooms)

    # L5a.1: topology reachability (hard constraint for walkable campus)
    entry_hubs = _find_building_entry_hubs(buildings=buildings, floors=floors, rooms=rooms)
    if entry_hubs:
        _validate_world_entry_reachability(
            rooms=rooms,
            relationships=relationships,
            entry_room_id=_WORLD_ENTRY_ROOM_ID,
            required_entry_hubs=entry_hubs,
        )
    _validate_connects_to_direction_conflicts(relationships, room_ids)

    # L5b: concept bindings (including concept-to-concept) and scope hints
    bindable_ids = spatial_object_ids | all_entity_ids | all_concept_ids
    for family, arr in concepts.items():
        for row in arr:
            cid = str(row["id"])
            bindings = row.get("bindings", [])
            for target in bindings:
                if str(target) not in bindable_ids:
                    raise DataPackageError(ERROR_WORLD_DATA_REFERENCE_BROKEN, f"broken concept binding: {cid}->{target}")
            scope = str(row.get("scope", "") or "").lower()
            if scope == "zone":
                if zone_ids and not any(str(t) in zone_ids for t in bindings):
                    raise DataPackageError(
                        ERROR_WORLD_DATA_SEMANTIC_CONFLICT,
                        f"concept.scope=zone should bind at least one zone id: {cid}",
                    )

    # L5c: trait profile completeness for HiCampus mapped DB node types.
    overlays = load_graph_seed_node_type_overrides()
    missing_trait: List[str] = []
    for db_type_code in sorted(set(_PACKAGE_TO_DB_NODE_TYPE.values())):
        ov = overlays.get(db_type_code) or {}
        tc = str(ov.get("trait_class") or "").strip().upper()
        tm = ov.get("trait_mask", None)
        try:
            tm_int = int(tm) if tm is not None else -1
        except (TypeError, ValueError):
            tm_int = -1
        if not tc or tc == "UNKNOWN" or tm_int < 0:
            missing_trait.append(db_type_code)
    if missing_trait:
        raise DataPackageError(
            ERROR_WORLD_DATA_SCHEMA_UNSUPPORTED,
            f"missing trait profile for mapped node types: {missing_trait}",
        )

    return {
        "world": world,
        "spatial": {"buildings": buildings, "floors": floors, "rooms": rooms},
        "entities": entities,
        "concepts": concepts,
        "relationships": relationships,
        "meta": meta_doc,
    }
