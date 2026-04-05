"""
Look命令实现 - 参考Evennia设计

实现查看环境和物品的功能，支持：
- 查看当前房间环境
- 查看特定物品
- 智能搜索和模糊匹配
- 权限控制和上下文感知
"""

from typing import List, Optional, Dict, Any, Union

from ..base import GameCommand, CommandResult, CommandContext
from app.core.log import get_logger, LoggerNames
from app.commands.policy_expr import evaluate_policy_expr, PolicyExprError
from app.game_engine.world_room_resolve import room_is_world_entry_gate
from app.commands.game.look_appearance import look_alias_strings_from_attrs, room_list_label_for_entry

_EXIT_DIRECTION_ORDER = (
    "north",
    "northeast",
    "east",
    "southeast",
    "south",
    "southwest",
    "west",
    "northwest",
    "up",
    "down",
    "enter",
    "out",
)


def _sort_room_exit_labels(labels: List[str]) -> List[str]:
    rank = {d: i for i, d in enumerate(_EXIT_DIRECTION_ORDER)}
    cap = len(_EXIT_DIRECTION_ORDER)
    return sorted(set(labels), key=lambda x: (rank.get(x.lower(), cap), x.lower()))


LOOK_DISAMBIGUATION_KEY = "look_disambiguation_entries"


def _entry_matches_look_target(entry: Dict[str, Any], target_lower: str) -> bool:
    """True if user search string matches graph content entry (name or list aliases)."""
    tl = (target_lower or "").strip().lower()
    if not tl:
        return False
    blobs: List[str] = [str(entry.get("name") or "")]
    blobs.extend(look_alias_strings_from_attrs(dict(entry.get("attributes") or {})))
    seen: set = set()
    for raw in blobs:
        if not raw or raw in seen:
            continue
        seen.add(raw)
        sl = raw.lower()
        if tl == sl or tl in sl:
            return True
    return False


def _merge_room_exit_labels_from_attrs_and_graph(
    room_attrs: Dict[str, Any],
    graph_labels: List[str],
) -> List[str]:
    from app.game_engine.direction_util import normalize_direction

    merged: List[str] = []
    re = room_attrs.get("room_exits")
    if isinstance(re, dict):
        for k in re.keys():
            if k is None:
                continue
            ks = str(k).strip()
            if ks:
                merged.append(normalize_direction(ks.lower()))
    merged.extend(graph_labels)
    return _sort_room_exit_labels(merged)


class LookCommand(GameCommand):
    """Look命令 - 查看环境和物品"""
    
    def __init__(self):
        super().__init__(
            name="look",
            description="查看当前环境或特定物品",
            aliases=["l", "lookat", "examine"],
            game_name="campus_life"
        )
        self.logger = get_logger(LoggerNames.COMMAND)
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        """执行look命令

        注意：look命令不依赖游戏场景运行状态，用户在奇点屋登录后即可查看周围环境。
        世界数据（图数据中的房间、实体）独立于游戏场景存在。
        """
        try:
            if not args:
                # 没有参数，查看当前环境
                return self._look_room(context)
            else:
                # 有参数，查看特定物品/对象
                target = args[0]
                target_args = args[1:]
                return self._look_object(context, target, target_args)
                
        except Exception as e:
            self.logger.error(f"Look命令执行失败: {e}")
            return CommandResult.error_result(f"查看失败: {str(e)}")
    
    def _look_room(self, context: CommandContext) -> CommandResult:
        """查看当前房间"""
        try:
            # 获取当前房间信息
            current_room = self._get_current_room(context)
            if not current_room:
                return CommandResult.error_result("无法确定当前位置")
            
            # 构建房间描述
            room_info = self._build_room_description(context, current_room)
            
            return CommandResult.success_result(room_info)
            
        except Exception as e:
            self.logger.error(f"查看房间失败: {e}")
            return CommandResult.error_result(f"查看房间失败: {str(e)}")
    
    def _look_object(self, context: CommandContext, target: str, target_args: Optional[List[str]] = None) -> CommandResult:
        """查看特定物品/对象（统一：命令只负责目标解析，展示由对象自身决定）"""
        try:
            target_args = target_args or []
            t = str(target or "").strip()
            if t.isdigit():
                return self._resolve_look_disambiguation_index(context, t, target_args)

            # 搜索目标物品
            found_objects = self._search_objects(context, target)
            
            if not found_objects:
                return CommandResult.error_result(f"找不到 '{target}'")
            
            if len(found_objects) > 1:
                # 多个匹配，显示选择列表
                return self._show_multiple_matches(context, target, found_objects)
            
            # 单个匹配，显示详细信息
            obj = found_objects[0]
            obj_info = self._build_object_description(context, obj, target_args=target_args)
            
            return CommandResult.success_result(obj_info)
            
        except Exception as e:
            self.logger.error(f"查看物品失败: {e}")
            return CommandResult.error_result(f"查看物品失败: {str(e)}")
    
    def _get_current_room(self, context: CommandContext) -> Optional[Dict[str, Any]]:
        """获取当前房间信息 - 修复版本"""
        try:
            room_ref = self._get_user_current_room_ref(context)
            if not room_ref:
                return None
            current_room_id = str(room_ref.get("room_id") or "")
            return self._get_room_from_graph_data(context, current_room_id)
            
        except Exception as e:
            self.logger.error(f"获取当前房间失败: {e}")
            return None

    def _get_user_current_room_ref(self, context: CommandContext) -> Optional[Dict[str, str]]:
        """从用户图数据获取当前位置（支持世界内 room_package_id）。"""
        try:
            from app.core.database import db_session_context
            from app.models.graph import Node
            
            with db_session_context() as session:
                # 根据用户ID查找用户节点
                user_node = session.query(Node).filter(
                    Node.id == context.user_id,
                    Node.type_code == 'account',
                    Node.is_active == True
                ).first()
                
                if not user_node:
                    self.logger.warning(f"未找到用户节点: {context.user_id}")
                    return None

                # Evennia 主路径：location_id 指向 room 节点（含世界内房间与奇点屋）
                location_id = user_node.location_id
                if location_id:
                    location_node = session.query(Node).filter(
                        Node.id == location_id,
                        Node.is_active == True,
                    ).first()
                    if location_node and location_node.type_code == "room":
                        return {"scope": "system", "room_id": str(location_node.id)}

                return None
                
        except Exception as e:
            self.logger.error(f"从图数据获取用户位置失败: {e}")
            return None

    def _exit_labels_from_connects_to(self, session, room_node_id: int) -> List[str]:
        """Outgoing graph exits: direction (normalized) or target package_node_id."""
        from app.game_engine.direction_util import normalize_direction
        from app.models.graph import Node, Relationship

        labels: List[str] = []
        outgoing = (
            session.query(Relationship, Node)
            .join(Node, Relationship.target_id == Node.id)
            .filter(
                Relationship.source_id == room_node_id,
                Relationship.type_code == "connects_to",
                Relationship.is_active == True,  # noqa: E712
                Node.is_active == True,  # noqa: E712
            )
            .all()
        )
        for rel, target in outgoing:
            rattrs = dict(rel.attributes or {})
            raw = str(rattrs.get("direction") or "").strip().lower()
            if raw:
                labels.append(normalize_direction(raw))
            else:
                pkg = str((target.attributes or {}).get("package_node_id") or "").strip()
                if pkg:
                    labels.append(pkg.lower())
        return labels

    def _get_room_from_graph_data(self, context: CommandContext, room_id: str) -> Optional[Dict[str, Any]]:
        """从图数据获取房间信息"""
        try:
            from app.core.database import db_session_context
            from app.models.graph import Node
            
            with db_session_context() as session:
                # 尝试通过ID查找
                room_node = session.query(Node).filter(
                    Node.id == int(room_id) if room_id.isdigit() else None,
                    Node.is_active == True
                ).first()
                
                # 如果通过ID没找到，尝试通过名称查找
                if not room_node:
                    room_node = session.query(Node).filter(
                        Node.attributes['room_name'].astext == room_id,
                        Node.type_code == 'room',
                        Node.is_active == True
                    ).first()
                
                if room_node:
                    # 构建房间数据
                    attrs = room_node.attributes
                    # 当前房间内容从图数据 location_id 反查（避免依赖 room_objects 静态属性）
                    contents = (
                        session.query(Node)
                        .filter(Node.location_id == room_node.id, Node.is_active == True)
                        .all()
                    )
                    ra = dict(attrs or {})
                    content_entries = []
                    room_objects = []
                    for n in contents:
                        if n.type_code in ("account", "user"):
                            continue
                        if not self._is_visible_in_room(context, n):
                            continue
                        entry_d = {
                            "node_id": n.id,
                            "name": n.name,
                            "type_code": n.type_code,
                            "type": n.type_code,
                            "description": n.description or "",
                            "attributes": dict(n.attributes or {}),
                        }
                        content_entries.append(entry_d)
                        room_objects.append(room_list_label_for_entry(entry_d))
                    rname = ra.get("room_name") or ra.get("display_name") or room_node.name
                    rdesc = (ra.get("room_description") or "").strip() or ra.get(
                        "display_name"
                    ) or "这里没有什么特别的。"
                    graph_exit_labels = self._exit_labels_from_connects_to(session, room_node.id)
                    exit_labels = _merge_room_exit_labels_from_attrs_and_graph(ra, graph_exit_labels)
                    wid_gate = str(ra.get("world_id") or "").strip().lower()
                    if wid_gate and room_is_world_entry_gate(session, room_node, wid_gate):
                        lower = {str(e).lower() for e in exit_labels}
                        if "out" not in lower:
                            exit_labels = _sort_room_exit_labels(list(exit_labels) + ["out"])
                    return {
                        "id": str(room_node.id),
                        "name": rname,
                        "description": rdesc,
                        "short_description": (ra.get("room_short_description") or "").strip(),
                        "ambiance": (ra.get("room_ambiance") or "").strip(),
                        "exits": exit_labels,
                        "items": room_objects,
                        "content_entries": content_entries,
                        "appearance_template": str(ra.get("appearance_template") or "").strip(),
                        "room_node_attributes": dict(ra),
                        "extra_name_info": str(ra.get("floor_label") or ra.get("room_extra_name_info") or "").strip(),
                        "is_singularity": ra.get("is_root", False),
                        "is_home": ra.get("is_home", False),
                    }
                
                return None
                
        except Exception as e:
            self.logger.error(f"从图数据获取房间信息失败: {e}")
            return None

    def _is_visible_in_room(self, context: Optional[CommandContext], node: Any) -> bool:
        """
        Evennia-style visibility gate driven by model attributes.
        """
        attrs = dict(getattr(node, "attributes", {}) or {})
        tc = str(getattr(node, "type_code", "") or "").lower()
        if tc == "world_entrance" and attrs.get("portal_enabled") is False:
            return False

        entity_kind = str(attrs.get("entity_kind", "") or "").lower()
        if not entity_kind:
            # Sensible default for legacy room content nodes
            entity_kind = "item"

        domains = attrs.get("presentation_domains", None)
        if isinstance(domains, list):
            domain_set = {str(x).lower() for x in domains}
        else:
            domain_set = {"room"} if entity_kind in {"item", "service", "ui", "exit"} else set()

        if "room" not in domain_set:
            return False

        locks = attrs.get("access_locks", {}) if isinstance(attrs.get("access_locks", {}), dict) else {}
        view_lock = str(locks.get("view", "all()"))
        try:
            return evaluate_policy_expr(
                view_lock,
                    user_permissions=list(getattr(context, "permissions", []) or []) if context else [],
                    user_roles=list(getattr(context, "roles", []) or []) if context else [],
                object_attrs=attrs,
            )
        except PolicyExprError:
            return False
    
    def _build_room_description(self, context: CommandContext, room: Dict[str, Any]) -> str:
        """构建房间描述（Evennia 式模板 + return_appearance_room）"""
        try:
            from app.commands.game.look_appearance import return_appearance_room

            r = dict(room)
            r["room_status"] = self._get_room_status(r)
            r["other_players"] = self._get_other_players(context, r)
            return return_appearance_room(r, context)
        except Exception as e:
            self.logger.error(f"构建房间描述失败: {e}")
            return f"房间描述生成失败: {str(e)}"
    
    def _search_objects(self, context: CommandContext, target: str) -> List[Dict[str, Any]]:
        """搜索目标物品/对象（优先在当前房间图内容中找，其次回退到场景内置 items）"""
        try:
            found_objects = []
            found_ids = set()  # 用于去重
            target_lower = target.lower()
            
            # 获取当前房间的物品
            current_room = self._get_current_room(context)
            if current_room:
                entries = current_room.get("content_entries") or []
                if entries:
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        if not _entry_matches_look_target(entry, target_lower):
                            continue
                        nid = entry.get("node_id")
                        if nid is None:
                            continue
                        gid = f"node:{nid}"
                        if gid in found_ids:
                            continue
                        graph_obj = self._graph_object_dict_by_node_id(context, int(nid))
                        if graph_obj:
                            found_objects.append(graph_obj)
                            found_ids.add(gid)
                else:
                    room_items = current_room.get("items", [])
                    for item_name in room_items:
                        if target_lower in item_name.lower():
                            graph_obj = self._get_graph_object_in_room_by_name(context, item_name)
                            if graph_obj:
                                gid = f"node:{graph_obj.get('node_id')}"
                                if gid not in found_ids:
                                    found_objects.append(graph_obj)
                                    found_ids.add(gid)
                            else:
                                item_info = self._get_item_info(context, item_name)
                                if item_info and item_info.get("id") not in found_ids:
                                    found_objects.append(item_info)
                                    found_ids.add(item_info.get("id"))
            
            # 搜索全局物品
            game_info = self.get_game_info(context)
            global_items = game_info.get('items', {})
            for item_id, item_data in global_items.items():
                item_name = item_data.get('name', item_id)
                if (target_lower in item_name.lower() or target_lower in item_id.lower()) and item_id not in found_ids:
                    item_info = item_data.copy()
                    item_info['id'] = item_id
                    found_objects.append(item_info)
                    found_ids.add(item_id)
            
            return found_objects
            
        except Exception as e:
            self.logger.error(f"搜索物品失败: {e}")
            return []

    def _get_graph_object_in_room_by_name(self, context: CommandContext, name: str) -> Optional[Dict[str, Any]]:
        """Try resolve a graph Node in user's current room by name (exact, then fuzzy)."""
        try:
            from app.core.database import db_session_context
            from app.models.graph import Node

            with db_session_context() as session:
                user_node = session.query(Node).filter(
                    Node.id == context.user_id,
                    Node.type_code == "account",
                    Node.is_active == True,
                ).first()
                if not user_node:
                    return None

                room_ref = self._get_user_current_room_ref(context)
                room_node_id = None
                if room_ref and room_ref.get("scope") == "system":
                    rid = str(room_ref.get("room_id") or "")
                    if rid.isdigit():
                        room_node_id = int(rid)
                    else:
                        room_node_id = user_node.location_id
                else:
                    room_node_id = user_node.location_id

                if not room_node_id:
                    return None

                candidates = (
                    session.query(Node)
                    .filter(
                        Node.location_id == room_node_id,
                        Node.is_active == True,
                    )
                    .all()
                )
                node = None
                nl = (name or "").strip().lower()
                for c in candidates:
                    if (c.name or "").strip().lower() == nl:
                        node = c
                        break
                if not node:
                    for c in candidates:
                        attrs = dict(c.attributes or {})
                        for blob in look_alias_strings_from_attrs(attrs):
                            if blob.strip().lower() == nl:
                                node = c
                                break
                        if node:
                            break
                if not node:
                    token = nl
                    for c in candidates:
                        if token in (c.name or "").lower():
                            node = c
                            break
                        attrs = dict(c.attributes or {})
                        if token and token in str(attrs.get("display_name", "")).lower():
                            node = c
                            break
                        if token and any(token in b.lower() for b in look_alias_strings_from_attrs(attrs)):
                            node = c
                            break
                        tags = c.tags or []
                        if isinstance(tags, list) and any(token in str(t).lower() for t in tags):
                            node = c
                            break
                if not node:
                    return None
                return {
                    "id": str(node.id),
                    "name": node.name,
                    "type": node.type_code,
                    "node_id": node.id,
                    "type_code": node.type_code,
                    "description": node.description,
                    "attributes": dict(node.attributes or {}),
                }
        except Exception:
            return None
    
    def _get_item_info(self, context: CommandContext, item_name: str) -> Optional[Dict[str, Any]]:
        """获取物品信息"""
        try:
            game_info = self.get_game_info(context)
            items = game_info.get('items', {})
            
            # 直接匹配
            if item_name in items:
                item_info = items[item_name].copy()
                item_info['id'] = item_name
                return item_info
            
            # 模糊匹配
            for item_id, item_data in items.items():
                if item_name.lower() in item_id.lower():
                    item_info = item_data.copy()
                    item_info['id'] = item_id
                    return item_info
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取物品信息失败: {e}")
            return None
    
    def _build_object_description(self, context: CommandContext, obj: Dict[str, Any], target_args: Optional[List[str]] = None) -> str:
        """构建物品/对象描述（get_appearance 优先，否则 Evennia 式 return_appearance_object）"""
        try:
            target_args = target_args or []

            type_code = obj.get("type_code") or obj.get("type")
            if type_code:
                try:
                    from app.models import model_factory

                    model_cls = model_factory.get_model(type_code)
                    if model_cls and hasattr(model_cls, "get_appearance"):
                        try:
                            inst = model_cls(
                                name=obj.get("name", type_code),
                                description=str(obj.get("description") or ""),
                                attributes=dict(obj.get("attributes") or {}),
                                disable_auto_sync=True,
                            )
                        except TypeError:
                            try:
                                inst = model_cls(name=obj.get("name", type_code), disable_auto_sync=True)
                            except TypeError:
                                inst = None
                        if inst is not None:
                            try:
                                return inst.get_appearance(context=context, args=target_args)
                            except TypeError:
                                return inst.get_appearance(context=context)
                except Exception:
                    pass

            from app.commands.game.look_appearance import return_appearance_object

            text = return_appearance_object(context, obj, target_args=target_args)
            extras = []
            st = self._get_object_status(obj)
            if st:
                extras.append(f"状态: {st}")
            oa = self._get_object_attributes(obj)
            if oa:
                extras.append(f"属性: {oa}")
            if extras:
                text = f"{text}\n\n" + "\n".join(extras)
            return text
        except Exception as e:
            self.logger.error(f"构建物品描述失败: {e}")
            return f"物品描述生成失败: {str(e)}"

    def _graph_object_dict_by_node_id(self, context: CommandContext, node_id: int) -> Optional[Dict[str, Any]]:
        try:
            from app.core.database import db_session_context
            from app.models.graph import Node

            with db_session_context() as session:
                user = (
                    session.query(Node)
                    .filter(
                        Node.id == context.user_id,
                        Node.type_code == "account",
                        Node.is_active == True,  # noqa: E712
                    )
                    .first()
                )
                if not user or not user.location_id:
                    return None
                node = (
                    session.query(Node)
                    .filter(Node.id == node_id, Node.is_active == True)  # noqa: E712
                    .first()
                )
                if not node or node.location_id != user.location_id:
                    return None
                return {
                    "id": str(node.id),
                    "name": node.name,
                    "node_id": node.id,
                    "type_code": node.type_code,
                    "type": node.type_code,
                    "description": node.description,
                    "attributes": dict(node.attributes or {}),
                }
        except Exception:
            return None

    def _object_from_disambig_entry(
        self, context: CommandContext, entry: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(entry, dict):
            return None
        if entry.get("node_id") is not None:
            return self._graph_object_dict_by_node_id(context, int(entry["node_id"]))
        sid = entry.get("scenic_item_id")
        if sid:
            return self._get_item_info(context, str(sid))
        return None

    def _resolve_look_disambiguation_index(
        self, context: CommandContext, target: str, target_args: List[str]
    ) -> CommandResult:
        if not context.session or not hasattr(context.session, "command_ephemeral"):
            return CommandResult.error_result(
                "当前连接不支持「look <编号>」消歧；请使用完整对象名称查看。"
            )
        ep = getattr(context.session, "command_ephemeral", None)
        if not isinstance(ep, dict):
            return CommandResult.error_result(
                "当前连接不支持「look <编号>」消歧；请使用完整对象名称查看。"
            )
        entries = ep.get(LOOK_DISAMBIGUATION_KEY)
        if not isinstance(entries, list) or not entries:
            return CommandResult.error_result(
                "当前没有待选列表。请先输入关键词出现「多个匹配」后再使用「look <编号>」，或直接「look <完整名称>」。"
            )
        idx = int(target) - 1
        if idx < 0 or idx >= len(entries):
            return CommandResult.error_result(
                f"编号 {target} 无效（上次列表共 {len(entries)} 项）。请重新搜索或改用完整名称。"
            )
        obj = self._object_from_disambig_entry(context, entries[idx])
        if not obj:
            return CommandResult.error_result(f"无法加载编号 {target} 对应的对象（可能已移动或无效）。")
        ep.pop(LOOK_DISAMBIGUATION_KEY, None)
        return CommandResult.success_result(
            self._build_object_description(context, obj, target_args=target_args)
        )
    
    def _show_multiple_matches(self, context: CommandContext, target: str, objects: List[Dict[str, Any]]) -> CommandResult:
        """显示多个匹配结果"""
        try:
            message = f"找到多个匹配 '{target}' 的物品:\n\n"
            entries: List[Dict[str, Any]] = []

            for i, obj in enumerate(objects, 1):
                obj_name = room_list_label_for_entry(
                    {
                        "name": obj.get("name"),
                        "type_code": obj.get("type_code") or obj.get("type"),
                        "attributes": dict(obj.get("attributes") or {}),
                        "description": str(obj.get("description") or ""),
                    }
                )
                if not obj_name or obj_name == "?":
                    obj_name = str(obj.get("name", obj.get("id", "未知")))
                obj_type = obj.get("type_code") or obj.get("type", "未知")
                nid = obj.get("node_id")
                suffix = f"  [#{nid}]" if nid is not None else ""
                message += f"{i}. {obj_name} ({obj_type}){suffix}\n"
                if obj.get("node_id") is not None:
                    entries.append({"node_id": int(obj["node_id"])})
                elif obj.get("id") is not None:
                    entries.append({"scenic_item_id": str(obj["id"])})
                else:
                    entries.append({})

            if context.session and hasattr(context.session, "command_ephemeral"):
                ep = getattr(context.session, "command_ephemeral", None)
                if isinstance(ep, dict) and entries:
                    ep[LOOK_DISAMBIGUATION_KEY] = entries

            if context.session and hasattr(context.session, "command_ephemeral"):
                message += "\n\n请使用更具体的名称，或使用 'look <编号>' 查看列表中对应项。"
            else:
                message += "\n\n请使用更具体的完整名称查看。"

            return CommandResult.success_result(message)
            
        except Exception as e:
            self.logger.error(f"显示多个匹配失败: {e}")
            return CommandResult.error_result(f"显示匹配结果失败: {str(e)}")
    
    def _get_room_status(self, room: Dict[str, Any]) -> str:
        """获取房间状态信息"""
        try:
            status_info = []
            
            # 检查房间类型
            room_type = room.get('room_type', 'normal')
            if room_type != 'normal':
                status_info.append(f"房间类型: {room_type}")
            
            # 检查房间容量
            capacity = room.get('room_capacity', 0)
            if capacity > 0:
                current_objects = len(room.get('items', []))
                status_info.append(f"容量: {current_objects}/{capacity}")
            
            # 检查房间环境
            lighting = room.get('room_lighting', 'normal')
            if lighting != 'normal':
                status_info.append(f"光线: {lighting}")
            
            temperature = room.get('room_temperature', 20)
            if temperature != 20:
                status_info.append(f"温度: {temperature}°C")
            
            return ", ".join(status_info) if status_info else ""
            
        except Exception as e:
            self.logger.error(f"获取房间状态失败: {e}")
            return ""
    
    def _get_other_players(self, context: CommandContext, room: Dict[str, Any]) -> List[str]:
        """获取房间内其他玩家"""
        try:
            # 这里需要从场景状态获取当前房间的玩家列表
            # 暂时返回空列表，实际实现需要与玩家管理系统集成
            return []
            
        except Exception as e:
            self.logger.error(f"获取其他玩家失败: {e}")
            return []
    
    def _get_object_status(self, obj: Dict[str, Any]) -> str:
        """获取物品状态信息"""
        try:
            status_info = []
            
            # 检查物品状态
            status = obj.get('status', 'normal')
            if status != 'normal':
                status_info.append(status)
            
            # 检查物品耐久度
            durability = obj.get('durability', None)
            if durability is not None:
                status_info.append(f"耐久度: {durability}")
            
            # 检查物品重量
            weight = obj.get('weight', None)
            if weight is not None:
                status_info.append(f"重量: {weight}kg")
            
            return ", ".join(status_info) if status_info else ""
            
        except Exception as e:
            self.logger.error(f"获取物品状态失败: {e}")
            return ""
    
    def _get_object_attributes(self, obj: Dict[str, Any]) -> str:
        """获取物品属性信息"""
        try:
            attrs = []
            
            # 检查物品属性
            if obj.get('is_magical', False):
                attrs.append("魔法")
            
            if obj.get('is_rare', False):
                attrs.append("稀有")
            
            if obj.get('is_valuable', False):
                attrs.append("贵重")
            
            if obj.get('is_consumable', False):
                attrs.append("消耗品")
            
            return ", ".join(attrs) if attrs else ""
            
        except Exception as e:
            self.logger.error(f"获取物品属性失败: {e}")
            return ""
    
    def get_usage(self) -> str:
        """获取使用说明"""
        return "look [物品名]"
    
    def _get_specific_help(self) -> str:
        """获取特定帮助信息"""
        return """
用法:
  look          - 查看当前环境
  look <物品>   - 查看特定物品

示例:
  look          - 查看当前房间
  look books    - 查看书籍
  look fountain - 查看喷泉

说明:
  - 不带参数时显示当前房间的详细描述
  - 带参数时搜索并显示指定物品的信息
  - 支持模糊匹配，可以输入物品名的一部分
  - 如果找到多个匹配，会显示选择列表
"""
