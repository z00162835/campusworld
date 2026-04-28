"""
Build examine text from ``nodes.attributes`` using ``node_types.schema_definition``
(graph-seed YAML shape: ``type: object``, ``properties``, optional ``title`` per field).

由 ``DefaultObject.build_synthetic_look_desc`` 在 ``get_display_desc`` 穷尽显式描述字段后调用，
**所有**图类型类（Room、Building、设备、家具等）只要 ``type_code`` 在 YAML/DB 中有
``schema_definition`` 即走同一套逻辑；子类仅需按需重写 ``_attributes_for_schema_look``。

Evennia 侧对象外观多由 ``return_appearance``/脚本拼装；此处用本体元数据驱动标签，
避免在 Python 里为每个属性硬编码中文说明。展示名优先级：

- 属性定义上的 ``title``（推荐写清中文/英文标签）
- 否则使用 **schema 中的属性名**（property key），满足「动态属性名」需求

可选在属性上设 ``x_look: omit`` 跳过展示。根对象可用 JSON Schema 标准字段 ``description``
作为 examine 开头段（如设备总述）。
"""

from __future__ import annotations

from typing import Any, Collection, List, Mapping, Optional, Set

_DEFAULT_SKIP_KEYS: frozenset[str] = frozenset(
    {
        "item_kind",
        "device_role",
        "entity_kind",
        "location_ref",
        "tags",
        "package_node_id",
    }
)


def _is_empty_for_look(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def format_schema_scalar_value(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (int, float, str)):
        return str(value).strip()
    if isinstance(value, list):
        inner = [format_schema_scalar_value(x) for x in value if not _is_empty_for_look(x)]
        return ", ".join(inner)
    if isinstance(value, dict):
        return str(value)
    return str(value)


def _property_label(key: str, spec: Mapping[str, Any]) -> str:
    t = spec.get("title")
    if isinstance(t, str) and t.strip():
        return t.strip()
    return key


def _lines_from_properties(
    properties: Mapping[str, Any],
    data: Mapping[str, Any],
    *,
    skip_keys: Set[str],
    parent_label: str = "",
    nested_sep: str = " · ",
) -> List[str]:
    lines: List[str] = []
    if not isinstance(data, Mapping):
        return lines
    for key, spec in properties.items():
        if not isinstance(spec, Mapping):
            continue
        if key in skip_keys or spec.get("x_look") == "omit":
            continue
        if key not in data:
            continue
        val = data[key]
        if _is_empty_for_look(val):
            continue
        base = _property_label(key, spec)
        label = f"{parent_label}{nested_sep}{base}" if parent_label else base

        sub_props = spec.get("properties")
        if spec.get("type") == "object" and isinstance(sub_props, Mapping) and isinstance(val, Mapping):
            lines.extend(
                _lines_from_properties(
                    sub_props,
                    val,
                    skip_keys=skip_keys,
                    parent_label=label,
                    nested_sep=nested_sep,
                )
            )
            continue

        lines.append(f"{label}：{format_schema_scalar_value(val)}")
    return lines


def format_attributes_from_schema_definition(
    attributes: Mapping[str, Any],
    schema_definition: Mapping[str, Any],
    *,
    skip_keys: Optional[Collection[str]] = None,
    include_root_description: bool = True,
    nested_separator: str = " · ",
) -> str:
    """
    Emit one line per declared property (and nested property) that has a non-empty value.

    Root ``schema_definition.description`` (if non-empty str) is prepended as its own paragraph.
    """
    props = schema_definition.get("properties")
    if not isinstance(props, Mapping):
        return ""

    sk: Set[str] = set(_DEFAULT_SKIP_KEYS)
    if skip_keys:
        sk.update(skip_keys)

    body_lines = _lines_from_properties(
        props,
        attributes,
        skip_keys=sk,
        parent_label="",
        nested_sep=nested_separator,
    )
    body = "\n".join(body_lines)

    if include_root_description:
        lead = schema_definition.get("description")
        if isinstance(lead, str) and lead.strip():
            if body:
                return f"{lead.strip()}\n\n{body}"
            return lead.strip()
    return body
