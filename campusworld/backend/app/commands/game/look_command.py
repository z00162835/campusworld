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
        """执行look命令"""
        try:
            # 检查游戏是否运行
            if not self.is_game_running(context):
                return CommandResult.error_result("游戏未运行，无法执行look命令")
            
            if not args:
                # 没有参数，查看当前环境
                return self._look_room(context)
            else:
                # 有参数，查看特定物品
                target = " ".join(args)
                return self._look_object(context, target)
                
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
    
    def _look_object(self, context: CommandContext, target: str) -> CommandResult:
        """查看特定物品"""
        try:
            # 搜索目标物品
            found_objects = self._search_objects(context, target)
            
            if not found_objects:
                return CommandResult.error_result(f"找不到 '{target}'")
            
            if len(found_objects) > 1:
                # 多个匹配，显示选择列表
                return self._show_multiple_matches(context, target, found_objects)
            
            # 单个匹配，显示详细信息
            obj = found_objects[0]
            obj_info = self._build_object_description(context, obj)
            
            return CommandResult.success_result(obj_info)
            
        except Exception as e:
            self.logger.error(f"查看物品失败: {e}")
            return CommandResult.error_result(f"查看物品失败: {str(e)}")
    
    def _get_current_room(self, context: CommandContext) -> Optional[Dict[str, Any]]:
        """获取当前房间信息 - 修复版本"""
        try:
            # 从用户图数据获取当前位置
            current_room_id = self._get_user_current_room_id(context)

            # 如果游戏中没有该房间，尝试从图数据获取
            return self._get_room_from_graph_data(context, current_room_id)
            
        except Exception as e:
            self.logger.error(f"获取当前房间失败: {e}")
            return None

    def _get_user_current_room_id(self, context: CommandContext) -> Optional[str]:
        """从用户图数据获取当前房间ID"""
        try:
            from app.core.database import SessionLocal
            from app.models.graph import Node
            
            with SessionLocal() as session:
                # 根据用户ID查找用户节点
                user_node = session.query(Node).filter(
                    Node.id == context.user_id,
                    Node.type_code == 'account',
                    Node.is_active == True
                ).first()
                
                if not user_node:
                    self.logger.warning(f"未找到用户节点: {context.user_id}")
                    return None
                
                # 获取用户当前位置
                location_id = user_node.location_id
                if location_id:
                    # 查找位置节点
                    location_node = session.query(Node).filter(
                        Node.id == location_id,
                        Node.is_active == True
                    ).first()
                    
                    if location_node:
                        # 返回房间名称或ID
                        return location_node.attributes.get('room_name', str(location_id))
                
                return None
                
        except Exception as e:
            self.logger.error(f"从图数据获取用户位置失败: {e}")
            return None

    def _get_room_from_graph_data(self, context: CommandContext, room_id: str) -> Optional[Dict[str, Any]]:
        """从图数据获取房间信息"""
        try:
            from app.core.database import SessionLocal
            from app.models.graph import Node
            
            with SessionLocal() as session:
                # 尝试通过ID查找
                room_node = session.query(Node).filter(
                    Node.id == int(room_id) if room_id.isdigit() else None,
                    Node.is_active == True
                ).first()
                
                # 如果通过ID没找到，尝试通过名称查找
                if not room_node:
                    room_node = session.query(Node).filter(
                        Node.attributes['room_name'].astext == room_id,
                        Node.type == 'room',
                        Node.is_active == True
                    ).first()
                
                if room_node:
                    # 构建房间数据
                    attrs = room_node.attributes
                    return {
                        'id': str(room_node.id),
                        'name': attrs.get('room_name', room_node.name),
                        'description': attrs.get('room_description', '这里没有什么特别的。'),
                        'exits': attrs.get('room_exits', {}).keys() if attrs.get('room_exits') else [],
                        'items': attrs.get('room_objects', []),
                        'is_singularity': attrs.get('is_root', False),
                        'is_home': attrs.get('is_home', False)
                    }
                
                return None
                
        except Exception as e:
            self.logger.error(f"从图数据获取房间信息失败: {e}")
            return None
    
    def _build_room_description(self, context: CommandContext, room: Dict[str, Any]) -> str:
        """构建房间描述"""
        try:
            room_name = room.get('name', '未知房间')
            room_desc = room.get('description', '这里没有什么特别的。')
            exits = room.get('exits', [])
            items = room.get('items', [])
            
            # 构建基本描述
            description = f"""
{room_name}
{'=' * len(room_name)}

{room_desc}
"""
            
            # 添加出口信息
            if exits:
                description += f"\n出口: {', '.join(exits)}"
            
            # 添加物品信息
            if items:
                description += f"\n物品: {', '.join(items)}"
            
            # 添加房间状态信息
            room_status = self._get_room_status(room)
            if room_status:
                description += f"\n\n{room_status}"
            
            # 添加其他玩家信息
            other_players = self._get_other_players(context, room)
            if other_players:
                description += f"\n\n其他玩家: {', '.join(other_players)}"
            
            return description.strip()
            
        except Exception as e:
            self.logger.error(f"构建房间描述失败: {e}")
            return f"房间描述生成失败: {str(e)}"
    
    def _search_objects(self, context: CommandContext, target: str) -> List[Dict[str, Any]]:
        """搜索目标物品"""
        try:
            found_objects = []
            found_ids = set()  # 用于去重
            target_lower = target.lower()
            
            # 获取当前房间的物品
            current_room = self._get_current_room(context)
            if current_room:
                room_items = current_room.get('items', [])
                for item_name in room_items:
                    if target_lower in item_name.lower():
                        item_info = self._get_item_info(context, item_name)
                        if item_info and item_info.get('id') not in found_ids:
                            found_objects.append(item_info)
                            found_ids.add(item_info.get('id'))
            
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
    
    def _build_object_description(self, context: CommandContext, obj: Dict[str, Any]) -> str:
        """构建物品描述"""
        try:
            obj_name = obj.get('name', obj.get('id', '未知物品'))
            obj_desc = obj.get('description', '这看起来没什么特别的。')
            obj_type = obj.get('type', '未知')
            obj_location = obj.get('location', '未知位置')
            
            description = f"""
{obj_name}
{'=' * len(obj_name)}

{obj_desc}

类型: {obj_type}
位置: {obj_location}
"""
            
            # 添加物品状态信息
            obj_status = self._get_object_status(obj)
            if obj_status:
                description += f"\n状态: {obj_status}"
            
            # 添加物品属性信息
            obj_attrs = self._get_object_attributes(obj)
            if obj_attrs:
                description += f"\n属性: {obj_attrs}"
            
            return description.strip()
            
        except Exception as e:
            self.logger.error(f"构建物品描述失败: {e}")
            return f"物品描述生成失败: {str(e)}"
    
    def _show_multiple_matches(self, context: CommandContext, target: str, objects: List[Dict[str, Any]]) -> CommandResult:
        """显示多个匹配结果"""
        try:
            message = f"找到多个匹配 '{target}' 的物品:\n\n"
            
            for i, obj in enumerate(objects, 1):
                obj_name = obj.get('name', obj.get('id', '未知'))
                obj_type = obj.get('type', '未知')
                message += f"{i}. {obj_name} ({obj_type})\n"
            
            message += f"\n请使用更具体的名称，或使用 'look <编号>' 查看特定物品。"
            
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
            # 这里需要从游戏状态获取当前房间的玩家列表
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
