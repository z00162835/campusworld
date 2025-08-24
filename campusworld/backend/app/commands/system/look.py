"""
Look命令 - 查看命令

用于查看对象、房间、物品等的详细信息
参考Evennia框架的look命令设计

作者：AI Assistant
创建时间：2025-08-24
"""

from typing import Optional, List, Dict, Any
from ..base import Command


class CmdLook(Command):
    """
    Look命令 - 查看命令
    
    用法:
        look                    - 查看当前位置
        look <对象>            - 查看指定对象
        look <方向>            - 查看指定方向
        look -v <对象>         - 详细查看对象
        look -a <对象>         - 查看对象的所有属性
    """
    
    key = "look"
    aliases = ["l", "examine", "exa"]
    locks = ""
    help_category = "system"
    help_entry = """
查看命令用于查看对象、房间、物品等的详细信息。

用法:
  look                    - 查看当前位置
  look <对象>            - 查看指定对象
  look <方向>            - 查看指定方向
  look -v <对象>         - 详细查看对象
  look -a <对象>         - 查看对象的所有属性

示例:
  look                   - 查看当前房间
  look sword             - 查看名为"sword"的对象
  look north             - 查看北方
  look -v chest          - 详细查看宝箱
  look -a player         - 查看玩家的所有属性

开关参数:
  -v, --verbose          - 详细模式，显示更多信息
  -a, --all              - 显示所有属性
  -s, --short            - 简短模式，只显示基本信息
  -f, --format           - 格式化输出
    """
    
    def func(self) -> None:
        """执行look命令"""
        args = self.parsed_args
        
        # 如果没有参数，查看当前位置
        if not args.get('args'):
            self.look_here()
            return
        
        # 检查开关参数
        verbose = '-v' in args.get('switches', []) or '--verbose' in args.get('switches', [])
        show_all = '-a' in args.get('switches', []) or '--all' in args.get('switches', [])
        short_mode = '-s' in args.get('switches', []) or '--short' in args.get('switches', [])
        format_output = '-f' in args.get('switches', []) or '--format' in args.get('switches', [])
        
        # 获取目标对象
        target_name = args.get('args', '').strip()
        
        # 尝试查找目标对象
        target = self.find_target(target_name)
        
        if target:
            self.look_at(target, verbose, show_all, short_mode, format_output)
        else:
            # 尝试作为方向处理
            if self.is_direction(target_name):
                self.look_direction(target_name)
            else:
                self.msg(f"找不到对象: {target_name}")
    
    def look_here(self) -> None:
        """查看当前位置"""
        if not self.caller:
            self.msg("无法确定当前位置")
            return
        
        # 获取当前位置信息
        location = self.get_caller_location()
        if location:
            self.display_location(location)
        else:
            self.msg("无法获取位置信息")
    
    def look_at(self, target: Any, verbose: bool = False, show_all: bool = False, 
                short_mode: bool = False, format_output: bool = False) -> None:
        """
        查看指定对象
        
        Args:
            target: 目标对象
            verbose: 是否详细模式
            show_all: 是否显示所有属性
            short_mode: 是否简短模式
            format_output: 是否格式化输出
        """
        if not target:
            self.msg("目标对象无效")
            return
        
        # 根据对象类型显示不同信息
        if hasattr(target, 'get_node_type'):
            # 图节点对象
            self.display_node_object(target, verbose, show_all, short_mode, format_output)
        elif hasattr(target, 'name'):
            # 普通对象
            self.display_regular_object(target, verbose, show_all, short_mode, format_output)
        else:
            # 其他类型
            self.display_generic_object(target, verbose, show_all, short_mode, format_output)
    
    def look_direction(self, direction: str) -> None:
        """
        查看指定方向
        
        Args:
            direction: 方向名称
        """
        if not self.caller:
            self.msg("无法确定当前位置")
            return
        
        # 获取方向信息
        exit_info = self.get_exit_info(direction)
        if exit_info:
            self.display_exit_info(direction, exit_info)
        else:
            self.msg(f"在{direction}方向没有出口")
    
    def find_target(self, target_name: str) -> Optional[Any]:
        """
        查找目标对象
        
        Args:
            target_name: 目标名称
            
        Returns:
            目标对象或None
        """
        if not self.caller:
            return None
        
        # 在当前房间中查找
        room_objects = self.get_room_objects()
        for obj in room_objects:
            if self.match_object_name(obj, target_name):
                return obj
        
        # 在调用者身上查找
        caller_objects = self.get_caller_objects()
        for obj in caller_objects:
            if self.match_object_name(obj, target_name):
                return obj
        
        return None
    
    def match_object_name(self, obj: Any, name: str) -> bool:
        """
        检查对象名称是否匹配
        
        Args:
            obj: 对象
            name: 名称
            
        Returns:
            是否匹配
        """
        if not obj or not name:
            return False
        
        # 检查主名称
        if hasattr(obj, 'name') and obj.name and name.lower() in obj.name.lower():
            return True
        
        # 检查别名
        if hasattr(obj, 'aliases'):
            for alias in obj.aliases:
                if alias and name.lower() in alias.lower():
                    return True
        
        # 检查节点属性中的名称
        if hasattr(obj, '_node_attributes'):
            node_name = obj._node_attributes.get('name')
            if node_name and name.lower() in node_name.lower():
                return True
        
        return False
    
    def is_direction(self, direction: str) -> bool:
        """
        检查是否为方向
        
        Args:
            direction: 方向名称
            
        Returns:
            是否为方向
        """
        directions = ['north', 'south', 'east', 'west', 'northeast', 'northwest', 
                     'southeast', 'southwest', 'up', 'down', 'in', 'out']
        return direction.lower() in directions
    
    def get_caller_location(self) -> Optional[Any]:
        """获取调用者位置"""
        if not self.caller:
            return None
        
        # 这里需要根据实际的模型设计来实现
        # 暂时返回None
        return None
    
    def get_room_objects(self) -> List[Any]:
        """获取房间中的对象"""
        # 这里需要根据实际的模型设计来实现
        # 暂时返回空列表
        return []
    
    def get_caller_objects(self) -> List[Any]:
        """获取调用者身上的对象"""
        # 这里需要根据实际的模型设计来实现
        # 暂时返回空列表
        return []
    
    def get_exit_info(self, direction: str) -> Optional[Dict[str, Any]]:
        """获取出口信息"""
        # 这里需要根据实际的模型设计来实现
        # 暂时返回None
        return None
    
    def display_location(self, location: Any) -> None:
        """显示位置信息"""
        if not location:
            self.msg("位置信息无效")
            return
        
        # 显示位置基本信息
        self.msg("=" * 50)
        
        if hasattr(location, 'name'):
            self.msg(f"📍 {location.name}")
        else:
            self.msg("📍 当前位置")
        
        # 显示描述
        if hasattr(location, 'description') and location.description:
            self.msg(f"\n{location.description}")
        elif hasattr(location, '_node_attributes'):
            desc = location._node_attributes.get('description')
            if desc:
                self.msg(f"\n{desc}")
        
        # 显示出口
        exits = self.get_location_exits(location)
        if exits:
            self.msg(f"\n🚪 出口: {', '.join(exits)}")
        
        # 显示对象
        objects = self.get_location_objects(location)
        if objects:
            self.msg(f"\n📦 物品: {', '.join(objects)}")
        
        self.msg("=" * 50)
    
    def display_node_object(self, obj: Any, verbose: bool, show_all: bool, 
                           short_mode: bool, format_output: bool) -> None:
        """显示图节点对象信息"""
        if not obj:
            return
        
        self.msg("=" * 50)
        
        # 显示基本信息
        name = getattr(obj, 'name', 'Unknown')
        obj_type = getattr(obj, '_node_type', 'unknown')
        
        self.msg(f"🔍 {name} ({obj_type})")
        
        if not short_mode:
            # 显示描述
            if hasattr(obj, 'description') and obj.description:
                self.msg(f"\n{obj.description}")
            elif hasattr(obj, '_node_attributes'):
                desc = obj._node_attributes.get('description')
                if desc:
                    self.msg(f"\n{desc}")
            
            # 显示类型信息
            if verbose and hasattr(obj, 'get_complete_type_info'):
                type_info = obj.get_complete_type_info()
                if type_info:
                    self.msg(f"\n📋 类型信息:")
                    self.msg(f"  分类: {type_info.get('category', 'unknown')}")
                    self.msg(f"  描述: {type_info.get('description', '无')}")
            
            # 显示属性
            if show_all and hasattr(obj, '_node_attributes'):
                attrs = obj._node_attributes
                if attrs:
                    self.msg(f"\n📊 属性:")
                    for key, value in attrs.items():
                        if key not in ['name', 'description']:  # 跳过已显示的信息
                            self.msg(f"  {key}: {value}")
        
        self.msg("=" * 50)
    
    def display_regular_object(self, obj: Any, verbose: bool, show_all: bool, 
                              short_mode: bool, format_output: bool) -> None:
        """显示普通对象信息"""
        if not obj:
            return
        
        self.msg("=" * 50)
        
        # 显示基本信息
        name = getattr(obj, 'name', 'Unknown')
        obj_type = type(obj).__name__
        
        self.msg(f"🔍 {name} ({obj_type})")
        
        if not short_mode:
            # 显示描述
            if hasattr(obj, 'description') and obj.description:
                self.msg(f"\n{obj.description}")
            
            # 显示其他属性
            if show_all:
                for attr_name in dir(obj):
                    if not attr_name.startswith('_') and not callable(getattr(obj, attr_name)):
                        try:
                            value = getattr(obj, attr_name)
                            if value is not None:
                                self.msg(f"  {attr_name}: {value}")
                        except:
                            pass
        
        self.msg("=" * 50)
    
    def display_generic_object(self, obj: Any, verbose: bool, show_all: bool, 
                              short_mode: bool, format_output: bool) -> None:
        """显示通用对象信息"""
        if not obj:
            return
        
        self.msg("=" * 50)
        
        # 显示基本信息
        obj_type = type(obj).__name__
        obj_repr = str(obj)[:100]  # 限制长度
        
        self.msg(f"🔍 {obj_type}")
        self.msg(f"值: {obj_repr}")
        
        if verbose and not short_mode:
            # 显示更多详细信息
            self.msg(f"类型: {type(obj)}")
            self.msg(f"ID: {id(obj)}")
        
        self.msg("=" * 50)
    
    def display_exit_info(self, direction: str, exit_info: Dict[str, Any]) -> None:
        """显示出口信息"""
        self.msg("=" * 50)
        self.msg(f"🚪 {direction}方向")
        
        if 'destination' in exit_info:
            self.msg(f"目的地: {exit_info['destination']}")
        
        if 'description' in exit_info:
            self.msg(f"描述: {exit_info['description']}")
        
        if 'locked' in exit_info and exit_info['locked']:
            self.msg("🔒 已锁定")
        
        if 'hidden' in exit_info and exit_info['hidden']:
            self.msg("👻 隐藏出口")
        
        self.msg("=" * 50)
    
    def get_location_exits(self, location: Any) -> List[str]:
        """获取位置出口"""
        # 这里需要根据实际的模型设计来实现
        # 暂时返回空列表
        return []
    
    def get_location_objects(self, location: Any) -> List[str]:
        """获取位置对象"""
        # 这里需要根据实际的模型设计来实现
        # 暂时返回空列表
        return []
