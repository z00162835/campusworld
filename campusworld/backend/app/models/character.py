"""
角色模型定义 - 添加钩子系统

继承自DefaultObject，集成CmdSet机制和钩子系统
与现有命令系统兼容
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime

from .base import DefaultObject
from app.commands.cmdset import CmdSetManager, CharacterCmdSet, PlayerCmdSet, NPCCmdSet
from app.core.log import get_logger, LoggerNames

if TYPE_CHECKING:
    from .user import User
    from .room import Room


class Character(DefaultObject):
    """
    基础角色模型 - 与现有项目集成
    
    继承自DefaultObject，集成CmdSet机制和钩子系统
    与现有命令系统兼容
    所有数据存储在Node中，type='character'
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None, **kwargs):
        # 设置角色特定的节点类型
        self._node_type = 'character'
        self.logger = get_logger(LoggerNames.GAME)
        
        # 设置角色最基础的默认属性
        default_attrs = {
            # ==================== 基础身份信息 ====================
            "character_type": "generic",  # generic, player, npc, ai, etc.
            "character_class": "commoner",  # commoner, warrior, mage, etc.
            "character_race": "human",  # human, elf, dwarf, etc.
            
            # ==================== 外观描述 ====================
            "short_description": "",  # 简短描述
            "long_description": "",  # 详细描述
            
            # ==================== 基础属性 ====================
            "level": 1,  # 等级
            "experience": 0,  # 经验值
            
            # 基础属性点（六维属性）
            "strength": 10,  # 力量
            "agility": 10,  # 敏捷
            "intelligence": 10,  # 智力
            "constitution": 10,  # 体质
            "wisdom": 10,  # 智慧
            "charisma": 10,  # 魅力
            
            # ==================== 基础状态 ====================
            "health": 100,  # 当前生命值
            "max_health": 100,  # 最大生命值
            "energy": 100,  # 当前体力
            "max_energy": 100,  # 最大体力
            "mana": 50,  # 当前魔法值
            "max_mana": 50,  # 最大魔法值
            
            # 基础状态
            "is_alive": True,  # 是否存活
            "is_conscious": True,  # 是否清醒
            "is_awake": True,  # 是否清醒
            
            # ==================== 基础能力标识 ====================
            "can_move": True,  # 是否可以移动
            "can_talk": True,  # 是否可以对话
            "can_see": True,  # 是否可以看见
            "can_hear": True,  # 是否可以听见
            "can_touch": True,  # 是否可以触摸
            
            # ==================== 移动能力标识 ====================
            "can_walk": True,  # 是否可以走路
            "can_run": True,  # 是否可以跑步
            "can_jump": True,  # 是否可以跳跃
            "can_climb": False,  # 是否可以攀爬
            "can_swim": False,  # 是否可以游泳
            "can_fly": False,  # 是否可以飞行
            
            # ==================== 基础标识 ====================
            "is_player": False,  # 是否为玩家角色
            "is_npc": True,  # 是否为NPC
            "is_ai": False,  # 是否为AI角色
            
            # ==================== 状态信息 ====================
            "last_action_time": None,  # 最后行动时间
            "last_rest_time": None,  # 最后休息时间
            
            # ==================== 行动代价配置 ====================
            "action_costs": {
                "walk": 5,
                "run": 15,
                "jump": 10,
                "climb": 20,
                "swim": 25,
                "fly": 30,
                "rest": 0,
                "talk": 0,
                "look": 0,
            },
            
            # ==================== 恢复配置 ====================
            "recovery_rates": {
                "energy_per_hour": 10,
                "health_per_hour": 2,
                "mana_per_hour": 5,
            },
            
            **kwargs
        }
        
        # 设置默认标签
        default_tags = ['character']
        
        # 合并配置
        if config:
            # 合并attributes
            if 'attributes' in config:
                default_attrs.update(config['attributes'])
            # 合并tags
            if 'tags' in config:
                default_tags.extend(config['tags'])
        
        # 合并kwargs
        default_attrs.update(kwargs)
        
        # 根据角色类型更新标签
        character_type = default_attrs.get('character_type', 'generic')
        default_tags.append(character_type)
        
        if default_attrs.get('is_player'):
            default_tags.append('player')
        if default_attrs.get('is_npc'):
            default_tags.append('npc')
        if default_attrs.get('is_ai'):
            default_tags.append('ai')
        
        default_config = {
            'attributes': default_attrs,
            'tags': default_tags,
        }
        
        super().__init__(name=name, **default_config)
        
        # 初始化命令集合管理器
        self._cmdset_manager = CmdSetManager()
        self._init_cmdsets()
    
    # ==================== 行动代价钩子 ====================
    
    def get_action_cost(self, action_name: str) -> int:
        """获取行动代价"""
        action_costs = self._node_attributes.get('action_costs', {})
        base_cost = action_costs.get(action_name, 0)
        
        # 调用钩子进行动态调整
        if hasattr(self, 'at_action_cost_calculation'):
            adjusted_cost = self.at_action_cost_calculation(action_name, base_cost)
            return adjusted_cost
        
        return base_cost
    
    def at_action_cost_calculation(self, action_name: str, base_cost: int) -> int:
        """行动代价计算钩子 - 子类可重写"""
        # 可以根据角色状态、装备、环境等因素调整代价
        return base_cost
    
    def at_action_cost(self, action_name: str) -> Dict[str, Any]:
        """行动代价消耗钩子 - 子类可重写"""
        cost = self.get_action_cost(action_name)
        
        if cost > 0 and self.energy >= cost:
            self.energy -= cost
            return {
                'success': True,
                'energy_cost': cost,
                'remaining_energy': self.energy
            }
        elif cost > 0:
            return {
                'success': False,
                'error': f"{self.name} 体力不足，需要 {cost} 点体力"
            }
        
        return {'success': True, 'energy_cost': 0}
    
    def at_action_result(self, action_name: str, **kwargs) -> Dict[str, Any]:
        """行动结果计算钩子 - 子类可重写"""
        return {'success': True, 'message': f"{self.name} 执行了 {action_name}"}
    
    # ==================== 特殊行动钩子 ====================
    
    def calculate_jump_height(self) -> float:
        """计算跳跃高度 - 子类可重写"""
        strength = self._node_attributes.get('strength', 10)
        agility = self._node_attributes.get('agility', 10)
        
        # 基础计算
        base_height = (strength + agility) / 20.0
        
        # 调用钩子进行调整
        if hasattr(self, 'at_jump_height_calculation'):
            adjusted_height = self.at_jump_height_calculation(base_height)
            return adjusted_height
        
        return base_height
    
    def at_jump_height_calculation(self, base_height: float) -> float:
        """跳跃高度计算钩子 - 子类可重写"""
        return base_height
    
    def calculate_recovery(self, duration: int) -> Dict[str, int]:
        """计算恢复效果 - 子类可重写"""
        recovery_rates = self._node_attributes.get('recovery_rates', {})
        
        energy_rate = recovery_rates.get('energy_per_hour', 10)
        health_rate = recovery_rates.get('health_per_hour', 2)
        mana_rate = recovery_rates.get('mana_per_hour', 5)
        
        energy_recovery = duration * energy_rate
        health_recovery = duration * health_rate
        mana_recovery = duration * mana_rate
        
        # 恢复体力
        old_energy = self.energy
        self.energy = min(self.max_energy, self.energy + energy_recovery)
        actual_energy_recovery = self.energy - old_energy
        
        # 恢复生命值
        old_health = self.health
        self.health = min(self.max_health, self.health + health_recovery)
        actual_health_recovery = self.health - old_health
        
        # 恢复魔法值
        old_mana = self.mana
        self.mana = min(self.max_mana, self.mana + mana_recovery)
        actual_mana_recovery = self.mana - old_mana
        
        return {
            'energy_recovery': actual_energy_recovery,
            'health_recovery': actual_health_recovery,
            'mana_recovery': actual_mana_recovery
        }
    
    # ==================== 其他现有方法保持不变 ====================
    
    def __repr__(self):
        char_type = self._node_attributes.get('character_type', 'generic')
        level = self._node_attributes.get('level', 1)
        is_alive = self._node_attributes.get('is_alive', True)
        status = "alive" if is_alive else "dead"
        return f"<Character(name='{self._node_name}', type='{char_type}', level={level}, status='{status}')>"
    
    # ==================== 生命周期钩子重写 ====================
    
    def _at_object_creation(self):
        """角色创建时的基础处理"""
        # 初始化基础属性
        self._initialize_base_stats()
    
    def _at_object_delete(self):
        """角色删除时的基础清理"""
        pass
    
    def _at_pre_move(self, destination: 'DefaultObject', **kwargs) -> bool:
        """移动前检查"""
        # 检查是否可以移动
        if not self._node_attributes.get('can_move', True):
            return False
        
        # 检查是否存活
        if not self._node_attributes.get('is_alive', True):
            return False
        
        # 检查是否清醒
        if not self._node_attributes.get('is_conscious', True):
            return False
        
        return True
    
    def _at_post_move(self, source: 'DefaultObject', destination: 'DefaultObject', **kwargs):
        """移动后处理"""
        # 更新最后行动时间
        self.set_node_attribute('last_action_time', datetime.now().isoformat())
    
    # ==================== 命令集合管理 ====================
    
    def _init_cmdsets(self):
        """初始化命令集合"""
        # 添加基础角色命令集合
        self._cmdset_manager.add_cmdset(CharacterCmdSet())
        
        # 根据角色类型添加特定命令集合
        if self.is_player:
            self._cmdset_manager.add_cmdset(PlayerCmdSet())
        elif self.is_npc:
            self._cmdset_manager.add_cmdset(NPCCmdSet())
    
    def get_cmdset_manager(self) -> CmdSetManager:
        """获取命令集合管理器"""
        return self._cmdset_manager
    
    def add_cmdset(self, cmdset):
        """添加命令集合"""
        self._cmdset_manager.add_cmdset(cmdset)
    
    def remove_cmdset(self, cmdset):
        """移除命令集合"""
        self._cmdset_manager.remove_cmdset(cmdset)
    
    def has_command(self, command_name: str) -> bool:
        """检查是否有指定命令"""
        return self._cmdset_manager.has_command(command_name)
    
    def get_command(self, command_name: str):
        """获取指定命令"""
        return self._cmdset_manager.get_command(command_name)
    
    def get_available_commands(self) -> List[str]:
        """获取可用命令列表"""
        return list(self._cmdset_manager.get_all_commands().keys())
    
    # ==================== 命令执行 ====================
    
    def execute_command(self, command_string: str, **kwargs) -> Dict[str, Any]:
        """
        执行命令 - Evennia风格
        
        Args:
            command_string: 命令字符串
            **kwargs: 其他参数
            
        Returns:
            执行结果字典
        """
        try:
            # 解析命令
            parts = command_string.strip().split()
            if not parts:
                return {
                    'success': False,
                    'error': '空命令',
                    'command': command_string
                }
            
            command_name = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            
            # 获取命令
            command = self.get_command(command_name)
            if not command:
                return {
                    'success': False,
                    'error': f'未知命令: {command_name}',
                    'command': command_string
                }
            
            # 创建命令上下文
            from app.commands.context import CommandContext
            context = CommandContext(caller=self, **kwargs)
            
            # 验证参数
            if not command.validate_args(args):
                return {
                    'success': False,
                    'error': f'参数验证失败: {command.get_usage()}',
                    'command': command_string
                }
            
            # 检查权限
            if not command.check_permission(context):
                return {
                    'success': False,
                    'error': '权限不足',
                    'command': command_string
                }
            
            # 执行命令
            result = command.execute(context, args)
            
            # 记录命令历史
            self._add_command_to_history(command_string, result)
            
            return {
                'success': result.success,
                'message': result.message,
                'error': result.error,
                'command': command_string,
                'command_type': result.command_type
            }
            
        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'command': command_string
            }
            self._add_command_to_history(command_string, error_result)
            return error_result
    
    def msg(self, message: str, **kwargs):
        """
        发送消息给角色 - Evennia风格
        
        Args:
            message: 消息内容
            **kwargs: 其他参数
        """
        # 这里可以实现消息发送逻辑
        # 例如：发送给连接的客户端、记录到日志等
        print(f"[{self.name}] {message}")
    
    # ==================== 基础属性访问器 ====================
    
    @property
    def character_type(self) -> str:
        """获取角色类型"""
        return self._node_attributes.get('character_type', 'generic')
    
    @character_type.setter
    def character_type(self, value: str):
        """设置角色类型"""
        self.set_node_attribute('character_type', value)
    
    @property
    def level(self) -> int:
        """获取等级"""
        return self._node_attributes.get('level', 1)
    
    @level.setter
    def level(self, value: int):
        """设置等级"""
        self.set_node_attribute('level', value)
    
    @property
    def health(self) -> int:
        """获取当前生命值"""
        return self._node_attributes.get('health', 100)
    
    @health.setter
    def health(self, value: int):
        """设置当前生命值"""
        max_health = self._node_attributes.get('max_health', 100)
        self.set_node_attribute('health', min(value, max_health))
    
    @property
    def max_health(self) -> int:
        """获取最大生命值"""
        return self._node_attributes.get('max_health', 100)
    
    @max_health.setter
    def max_health(self, value: int):
        """设置最大生命值"""
        self.set_node_attribute('max_health', value)
        # 确保当前生命值不超过最大值
        current_health = self._node_attributes.get('health', 100)
        if current_health > value:
            self.set_node_attribute('health', value)
    
    @property
    def energy(self) -> int:
        """获取当前体力"""
        return self._node_attributes.get('energy', 100)
    
    @energy.setter
    def energy(self, value: int):
        """设置当前体力"""
        max_energy = self._node_attributes.get('max_energy', 100)
        self.set_node_attribute('energy', min(value, max_energy))
    
    @property
    def max_energy(self) -> int:
        """获取最大体力"""
        return self._node_attributes.get('max_energy', 100)
    
    @max_energy.setter
    def max_energy(self, value: int):
        """设置最大体力"""
        self.set_node_attribute('max_energy', value)
        # 确保当前体力不超过最大值
        current_energy = self._node_attributes.get('energy', 100)
        if current_energy > value:
            self.set_node_attribute('energy', value)
    
    @property
    def mana(self) -> int:
        """获取当前魔法值"""
        return self._node_attributes.get('mana', 50)
    
    @mana.setter
    def mana(self, value: int):
        """设置当前魔法值"""
        max_mana = self._node_attributes.get('max_mana', 50)
        self.set_node_attribute('mana', min(value, max_mana))
    
    @property
    def max_mana(self) -> int:
        """获取最大魔法值"""
        return self._node_attributes.get('max_mana', 50)
    
    @max_mana.setter
    def max_mana(self, value: int):
        """设置最大魔法值"""
        self.set_node_attribute('max_mana', value)
        # 确保当前魔法值不超过最大值
        current_mana = self._node_attributes.get('mana', 50)
        if current_mana > value:
            self.set_node_attribute('mana', value)
    
    @property
    def is_alive(self) -> bool:
        """获取是否存活"""
        return self._node_attributes.get('is_alive', True)
    
    @is_alive.setter
    def is_alive(self, value: bool):
        """设置是否存活"""
        self.set_node_attribute('is_alive', value)
        if not value:
            self.set_node_attribute('is_conscious', False)
            self.set_node_attribute('is_awake', False)
    
    @property
    def is_conscious(self) -> bool:
        """获取是否清醒"""
        return self._node_attributes.get('is_conscious', True)
    
    @is_conscious.setter
    def is_conscious(self, value: bool):
        """设置是否清醒"""
        self.set_node_attribute('is_conscious', value)
    
    @property
    def is_player(self) -> bool:
        """获取是否为玩家角色"""
        return self._node_attributes.get('is_player', False)
    
    @is_player.setter
    def is_player(self, value: bool):
        """设置是否为玩家角色"""
        self.set_node_attribute('is_player', value)
        if value:
            self.set_node_attribute('is_npc', False)
    
    @property
    def is_npc(self) -> bool:
        """获取是否为NPC"""
        return self._node_attributes.get('is_npc', True)
    
    @is_npc.setter
    def is_npc(self, value: bool):
        """设置是否为NPC"""
        self.set_node_attribute('is_npc', value)
        if value:
            self.set_node_attribute('is_player', False)
    
    # ==================== 基础属性管理 ====================
    
    def _initialize_base_stats(self):
        """初始化基础属性"""
        # 根据角色类型设置不同的基础属性
        char_type = self._node_attributes.get('character_type', 'generic')
        
        if char_type == 'athlete':
            self.set_node_attribute('agility', 15)
            self.set_node_attribute('constitution', 15)
            self.set_node_attribute('max_energy', 150)
        elif char_type == 'scholar':
            self.set_node_attribute('intelligence', 15)
            self.set_node_attribute('wisdom', 15)
            self.set_node_attribute('max_mana', 100)
        elif char_type == 'social':
            self.set_node_attribute('charisma', 15)
            self.set_node_attribute('wisdom', 15)
        
        # 设置当前值为最大值
        self.set_node_attribute('health', self._node_attributes.get('max_health', 100))
        self.set_node_attribute('energy', self._node_attributes.get('max_energy', 100))
        self.set_node_attribute('mana', self._node_attributes.get('max_mana', 50))
    
    def get_base_stats(self) -> Dict[str, int]:
        """获取基础属性"""
        return {
            'strength': self._node_attributes.get('strength', 10),
            'agility': self._node_attributes.get('agility', 10),
            'intelligence': self._node_attributes.get('intelligence', 10),
            'constitution': self._node_attributes.get('constitution', 10),
            'wisdom': self._node_attributes.get('wisdom', 10),
            'charisma': self._node_attributes.get('charisma', 10),
        }
    
    # ==================== 基础状态管理 ====================
    
    def take_damage(self, damage: int) -> Dict[str, Any]:
        """受到伤害（基础版本，不涉及战斗逻辑）"""
        if not self.is_alive:
            return {"success": False, "message": "角色已死亡"}
        
        # 减少生命值
        new_health = max(0, self.health - damage)
        self.health = new_health
        
        # 检查是否死亡
        if new_health <= 0:
            self.die()
            return {
                "success": True,
                "message": f"{self.name} 受到 {damage} 点伤害并死亡",
                "damage": damage,
                "died": True
            }
        
        return {
            "success": True,
            "message": f"{self.name} 受到 {damage} 点伤害",
            "damage": damage,
            "remaining_health": new_health
        }
    
    def heal(self, amount: int) -> Dict[str, Any]:
        """治疗"""
        if not self.is_alive:
            return {"success": False, "message": "无法治疗已死亡的角色"}
        
        old_health = self.health
        self.health = min(self.max_health, self.health + amount)
        actual_healing = self.health - old_health
        
        return {
            "success": True,
            "message": f"{self.name} 恢复了 {actual_healing} 点生命值",
            "healing": actual_healing,
            "current_health": self.health
        }
    
    def die(self):
        """死亡"""
        self.is_alive = False
        self.set_node_attribute('is_conscious', False)
        self.set_node_attribute('is_awake', False)
    
    def revive(self, health_percentage: float = 0.5):
        """复活"""
        self.is_alive = True
        self.set_node_attribute('is_conscious', True)
        self.set_node_attribute('is_awake', True)
        self.health = int(self.max_health * health_percentage)
    
    def gain_experience(self, amount: int) -> Dict[str, Any]:
        """获得经验值"""
        if not self.is_alive:
            return {"success": False, "message": "已死亡的角色无法获得经验"}
        
        old_exp = self._node_attributes.get('experience', 0)
        new_exp = old_exp + amount
        self.set_node_attribute('experience', new_exp)
        
        return {
            "success": True,
            "message": f"{self.name} 获得了 {amount} 点经验值",
            "experience_gained": amount,
            "total_experience": new_exp
        }
    
    # ==================== 能力检查方法 ====================
    
    def can_perform_action(self, action_type: str) -> bool:
        """检查是否可以执行指定类型的行动"""
        if not self.is_alive:
            return False
        
        if not self.is_conscious:
            return False
        
        # 检查基础能力
        ability_map = {
            'move': 'can_move',
            'talk': 'can_talk',
            'see': 'can_see',
            'hear': 'can_hear',
            'touch': 'can_touch',
            'walk': 'can_walk',
            'run': 'can_run',
            'jump': 'can_jump',
            'climb': 'can_climb',
            'swim': 'can_swim',
            'fly': 'can_fly'
        }
        
        ability_key = ability_map.get(action_type)
        if ability_key:
            return self._node_attributes.get(ability_key, False)
        
        return False
    
    def has_energy(self, required_energy: int) -> bool:
        """检查是否有足够的体力"""
        return self.energy >= required_energy
    
    def has_mana(self, required_mana: int) -> bool:
        """检查是否有足够的魔法值"""
        return self.mana >= required_mana
    
    # ==================== 信息获取方法 ====================
    
    def get_character_info(self) -> Dict[str, Any]:
        """获取角色基础信息"""
        return {
            'id': self.id,
            'uuid': self._node_uuid,
            'name': self._node_name,
            'type': self._node_attributes.get('character_type'),
            'class': self._node_attributes.get('character_class'),
            'race': self._node_attributes.get('character_race'),
            'level': self.level,
            'experience': self._node_attributes.get('experience', 0),
            'health': self.health,
            'max_health': self.max_health,
            'energy': self.energy,
            'max_energy': self.max_energy,
            'mana': self.mana,
            'max_mana': self.max_mana,
            'stats': self.get_base_stats(),
            'is_alive': self.is_alive,
            'is_conscious': self.is_conscious,
            'is_player': self.is_player,
            'is_npc': self.is_npc,
            'is_ai': self._node_attributes.get('is_ai', False),
            'abilities': {
                'can_move': self._node_attributes.get('can_move', True),
                'can_talk': self._node_attributes.get('can_talk', True),
                'can_see': self._node_attributes.get('can_see', True),
                'can_hear': self._node_attributes.get('can_hear', True),
                'can_touch': self._node_attributes.get('can_touch', True),
                'can_walk': self._node_attributes.get('can_walk', True),
                'can_run': self._node_attributes.get('can_run', True),
                'can_jump': self._node_attributes.get('can_jump', True),
                'can_climb': self._node_attributes.get('can_climb', False),
                'can_swim': self._node_attributes.get('can_swim', False),
                'can_fly': self._node_attributes.get('can_fly', False)
            },
            'available_commands': self.get_available_commands(),
            'location_id': self.location_id,
            'created_at': self._node_created_at.isoformat() if self._node_created_at else None,
            'updated_at': self._node_updated_at.isoformat() if self._node_updated_at else None
        }
    
    def get_short_description(self) -> str:
        """获取简短描述"""
        short_desc = self._node_attributes.get('short_description', '')
        if short_desc:
            return short_desc
        
        # 生成默认描述
        char_type = self._node_attributes.get('character_type', 'generic')
        char_class = self._node_attributes.get('character_class', 'commoner')
        level = self.level
        
        return f"一个{level}级的{char_class}，看起来{char_type}。"
    
    def get_detailed_description(self) -> str:
        """获取详细描述"""
        long_desc = self._node_attributes.get('long_description', '')
        if long_desc:
            return long_desc
        
        # 生成默认详细描述
        char_type = self._node_attributes.get('character_type', 'generic')
        char_class = self._node_attributes.get('character_class', 'commoner')
        char_race = self._node_attributes.get('character_race', 'human')
        level = self.level
        health = self.health
        max_health = self.max_health
        energy = self.energy
        max_energy = self.max_energy
        
        desc = f"这是一个{level}级的{char_race}{char_class}。"
        
        if char_type == 'player':
            desc += " 这是一个玩家角色。"
        elif char_type == 'npc':
            desc += " 这是一个NPC角色。"
        elif char_type == 'ai':
            desc += " 这是一个AI控制的角色。"
        
        desc += f" 当前生命值：{health}/{max_health}，体力：{energy}/{max_energy}"
        
        if not self.is_alive:
            desc += "（已死亡）"
        elif not self.is_conscious:
            desc += "（昏迷中）"
        
        return desc
