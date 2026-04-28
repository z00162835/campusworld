# 文件：app/commands/character.py (优化版)
"""
角色命令系统实现 - 参考Evennia设计优化

移除硬编码的行动代价，使用角色属性和钩子系统
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import BaseCommand, CommandResult, CommandContext, CommandType
from app.core.log import get_logger, LoggerNames


class CharacterCommand(BaseCommand):
    """角色命令基类"""
    
    def __init__(self, name: str, description: str = "", aliases: List[str] = None):
        super().__init__(name, description, aliases, CommandType.GAME)
        self.logger = get_logger(LoggerNames.COMMAND)
    
    def check_character_state(self, character) -> Optional[str]:
        """检查角色状态"""
        if not hasattr(character, 'is_alive') or not character.is_alive:
            return f"{character.name} 已死亡，无法执行此行动"
        
        if not hasattr(character, 'is_conscious') or not character.is_conscious:
            return f"{character.name} 昏迷中，无法执行此行动"
        
        return None
    
    def get_action_cost(self, character, action_name: str) -> int:
        """获取行动代价 - 从角色属性中获取"""
        if hasattr(character, 'get_action_cost'):
            return character.get_action_cost(action_name)
        
        # 默认代价映射
        default_costs = {
            'walk': 5,
            'run': 15,
            'jump': 10,
            'climb': 20,
            'swim': 25,
            'fly': 30,
            'rest': 0,  # 休息不消耗体力
            'talk': 0,  # 对话不消耗体力
            'look': 0,  # 观察不消耗体力
        }
        
        return default_costs.get(action_name, 0)
    
    def consume_resources(self, character, action_name: str) -> Dict[str, Any]:
        """消耗资源 - 使用角色钩子"""
        if hasattr(character, 'at_action_cost'):
            return character.at_action_cost(action_name)
        
        # 默认资源消耗逻辑
        cost = self.get_action_cost(character, action_name)
        
        if cost > 0 and hasattr(character, 'energy'):
            if character.energy >= cost:
                character.energy -= cost
                return {
                    'success': True,
                    'energy_cost': cost,
                    'remaining_energy': character.energy
                }
            else:
                return {
                    'success': False,
                    'error': f"{character.name} 体力不足，需要 {cost} 点体力"
                }
        
        return {'success': True, 'energy_cost': 0}
    
    def calculate_action_result(self, character, action_name: str, **kwargs) -> Dict[str, Any]:
        """计算行动结果 - 使用角色钩子"""
        if hasattr(character, 'at_action_result'):
            return character.at_action_result(action_name, **kwargs)
        
        # 默认结果计算
        return {'success': True, 'message': f"{character.name} 执行了 {action_name}"}


class WalkCommand(CharacterCommand):
    """走路命令"""
    
    def __init__(self):
        super().__init__("walk", "Walk to a location", ["w", "go"])
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("请指定要前往的位置")
        
        character = context.caller
        if not character:
            return CommandResult.error_result("无效的角色")
        
        # 检查角色状态
        state_error = self.check_character_state(character)
        if state_error:
            return CommandResult.error_result(state_error)
        
        # 检查是否可以走路
        if not hasattr(character, 'can_perform_action') or not character.can_perform_action('walk'):
            return CommandResult.error_result(f"{character.name} 无法走路")
        
        # 消耗资源
        resource_result = self.consume_resources(character, 'walk')
        if not resource_result['success']:
            return CommandResult.error_result(resource_result['error'])
        
        # 获取目标位置
        target_name = args[0]
        
        # 计算行动结果
        action_result = self.calculate_action_result(character, 'walk', target=target_name)
        
        # 发送消息给角色
        if hasattr(character, 'msg'):
            character.msg(f"你开始走路前往 {target_name}")
        
        return CommandResult.success_result(f"{character.name} 开始走路前往 {target_name}")


class RunCommand(CharacterCommand):
    """跑步命令"""
    
    def __init__(self):
        super().__init__("run", "Run to a location", ["r"])
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("请指定要前往的位置")
        
        character = context.caller
        if not character:
            return CommandResult.error_result("无效的角色")
        
        # 检查角色状态
        state_error = self.check_character_state(character)
        if state_error:
            return CommandResult.error_result(state_error)
        
        # 检查是否可以跑步
        if not hasattr(character, 'can_perform_action') or not character.can_perform_action('run'):
            return CommandResult.error_result(f"{character.name} 无法跑步")
        
        # 消耗资源
        resource_result = self.consume_resources(character, 'run')
        if not resource_result['success']:
            return CommandResult.error_result(resource_result['error'])
        
        # 获取目标位置
        target_name = args[0]
        # TODO: 实现位置查找逻辑
        
        # 计算行动结果
        action_result = self.calculate_action_result(character, 'run', target=target_name)
        
        # 发送消息给角色
        if hasattr(character, 'msg'):
            character.msg(f"你开始跑步前往 {target_name}")
        
        return CommandResult.success_result(f"{character.name} 开始跑步前往 {target_name}")


class JumpCommand(CharacterCommand):
    """跳跃命令"""
    
    def __init__(self):
        super().__init__("jump", "Jump", ["j"])
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        character = context.caller
        if not character:
            return CommandResult.error_result("无效的角色")
        
        # 检查角色状态
        state_error = self.check_character_state(character)
        if state_error:
            return CommandResult.error_result(state_error)
        
        # 检查是否可以跳跃
        if not hasattr(character, 'can_perform_action') or not character.can_perform_action('jump'):
            return CommandResult.error_result(f"{character.name} 无法跳跃")
        
        # 消耗资源
        resource_result = self.consume_resources(character, 'jump')
        if not resource_result['success']:
            return CommandResult.error_result(resource_result['error'])
        
        # 计算跳跃高度 - 使用角色属性
        jump_height = self._calculate_jump_height(character)
        
        # 计算行动结果
        action_result = self.calculate_action_result(character, 'jump', height=jump_height)
        
        # 发送消息给角色
        if hasattr(character, 'msg'):
            character.msg(f"你跳了起来，高度约 {jump_height:.1f} 米")
        
        return CommandResult.success_result(f"{character.name} 跳了起来，高度约 {jump_height:.1f} 米")
    
    def _calculate_jump_height(self, character) -> float:
        """计算跳跃高度 - 基于角色属性"""
        if hasattr(character, 'calculate_jump_height'):
            return character.calculate_jump_height()
        
        # 默认计算方式
        strength = getattr(character, '_node_attributes', {}).get('strength', 10)
        agility = getattr(character, '_node_attributes', {}).get('agility', 10)
        return (strength + agility) / 20.0


class TalkCommand(CharacterCommand):
    """对话命令"""
    
    def __init__(self):
        super().__init__("talk", "Talk to someone or say something", ["say", "speak"])
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        character = context.caller
        if not character:
            return CommandResult.error_result("无效的角色")
        
        # 检查角色状态
        state_error = self.check_character_state(character)
        if state_error:
            return CommandResult.error_result(state_error)
        
        # 检查是否可以对话
        if not hasattr(character, 'can_perform_action') or not character.can_perform_action('talk'):
            return CommandResult.error_result(f"{character.name} 无法对话")
        
        if not args:
            return CommandResult.error_result("请指定要说的内容")
        
        message = " ".join(args)
        
        # 消耗资源（对话通常不消耗体力）
        resource_result = self.consume_resources(character, 'talk')
        if not resource_result['success']:
            return CommandResult.error_result(resource_result['error'])
        
        # 计算行动结果
        action_result = self.calculate_action_result(character, 'talk', message=message)
        
        # 发送消息给角色
        if hasattr(character, 'msg'):
            character.msg(f"你说：{message}")
        
        return CommandResult.success_result(f"{character.name} 说：{message}")


class LookCommand(CharacterCommand):
    """观察命令"""
    
    def __init__(self):
        super().__init__("look", "Look at something or around", ["l", "examine"])
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        character = context.caller
        if not character:
            return CommandResult.error_result("无效的角色")
        
        # 检查角色状态
        state_error = self.check_character_state(character)
        if state_error:
            return CommandResult.error_result(state_error)
        
        # 检查是否可以看见
        if not hasattr(character, 'can_perform_action') or not character.can_perform_action('see'):
            return CommandResult.error_result(f"{character.name} 无法看见")
        
        # 消耗资源（观察通常不消耗体力）
        resource_result = self.consume_resources(character, 'look')
        if not resource_result['success']:
            return CommandResult.error_result(resource_result['error'])
        
        if args:
            # 观察特定目标
            target_name = args[0]
            # TODO: 实现目标查找逻辑
            if hasattr(character, 'msg'):
                character.msg(f"你观察了 {target_name}")
            return CommandResult.success_result(f"{character.name} 观察了 {target_name}")
        else:
            # 观察周围环境
            action_result = self.calculate_action_result(character, 'look', target=None)
            
            if hasattr(character, 'msg'):
                character.msg("你观察了周围环境")
            return CommandResult.success_result(f"{character.name} 观察了周围环境")


class RestCommand(CharacterCommand):
    """休息命令"""
    
    def __init__(self):
        super().__init__("rest", "Rest to recover energy and health", ["sleep"])
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        character = context.caller
        if not character:
            return CommandResult.error_result("无效的角色")
        
        # 检查角色状态
        state_error = self.check_character_state(character)
        if state_error:
            return CommandResult.error_result(state_error)
        
        # 休息时间（默认1小时）
        duration = 1
        if args:
            try:
                duration = int(args[0])
            except ValueError:
                return CommandResult.error_result("休息时间必须是数字")
        
        # 消耗资源（休息不消耗体力）
        resource_result = self.consume_resources(character, 'rest')
        if not resource_result['success']:
            return CommandResult.error_result(resource_result['error'])
        
        # 计算恢复效果
        recovery_result = self._calculate_recovery(character, duration)
        
        # 计算行动结果
        action_result = self.calculate_action_result(character, 'rest', duration=duration, recovery=recovery_result)
        
        # 更新休息时间
        if hasattr(character, 'set_node_attribute'):
            character.set_node_attribute('last_rest_time', datetime.now().isoformat())
        
        # 发送消息给角色
        if hasattr(character, 'msg'):
            character.msg(f"你休息了 {duration} 小时，恢复了 {recovery_result['energy_recovery']} 点体力和 {recovery_result['health_recovery']} 点生命值")
        
        return CommandResult.success_result(
            f"{character.name} 休息了 {duration} 小时，恢复了 {recovery_result['energy_recovery']} 点体力和 {recovery_result['health_recovery']} 点生命值"
        )
    
    def _calculate_recovery(self, character, duration: int) -> Dict[str, int]:
        """计算恢复效果 - 基于角色属性"""
        if hasattr(character, 'calculate_recovery'):
            return character.calculate_recovery(duration)
        
        # 默认恢复计算
        energy_recovery = duration * 10
        health_recovery = duration * 2
        
        if hasattr(character, 'energy') and hasattr(character, 'max_energy'):
            old_energy = character.energy
            character.energy = min(character.max_energy, character.energy + energy_recovery)
            actual_energy_recovery = character.energy - old_energy
        else:
            actual_energy_recovery = energy_recovery
        
        if hasattr(character, 'health') and hasattr(character, 'max_health'):
            old_health = character.health
            character.health = min(character.max_health, character.health + health_recovery)
            actual_health_recovery = character.health - old_health
        else:
            actual_health_recovery = health_recovery
        
        return {
            'energy_recovery': actual_energy_recovery,
            'health_recovery': actual_health_recovery
        }


class CharacterStatsCommand(CharacterCommand):
    """角色状态命令"""
    
    def __init__(self):
        super().__init__("charstats", "Show character statistics", ["cstats", "char"])
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        character = context.caller
        if not character:
            return CommandResult.error_result("无效的角色")
        
        # 获取角色信息
        if hasattr(character, 'get_character_info'):
            char_info = character.get_character_info()
        else:
            # 基础信息
            char_info = {
                'name': getattr(character, 'name', 'Unknown'),
                'level': getattr(character, 'level', 1),
                'health': getattr(character, 'health', 100),
                'max_health': getattr(character, 'max_health', 100),
                'energy': getattr(character, 'energy', 100),
                'max_energy': getattr(character, 'max_energy', 100),
                'is_alive': getattr(character, 'is_alive', True),
                'is_conscious': getattr(character, 'is_conscious', True),
            }
        
        stats_text = f"""
{char_info.get('name', 'Unknown')} 的状态信息
{'=' * (len(char_info.get('name', 'Unknown')) + 8)}

基本信息:
  等级: {char_info.get('level', 1)}
  类型: {char_info.get('type', 'unknown')}
  职业: {char_info.get('class', 'unknown')}
  种族: {char_info.get('race', 'unknown')}

状态:
  生命值: {char_info.get('health', 100)}/{char_info.get('max_health', 100)}
  体力: {char_info.get('energy', 100)}/{char_info.get('max_energy', 100)}
  魔法值: {char_info.get('mana', 50)}/{char_info.get('max_mana', 50)}
  状态: {'存活' if char_info.get('is_alive', True) else '死亡'}
  意识: {'清醒' if char_info.get('is_conscious', True) else '昏迷'}

属性:
  力量: {char_info.get('stats', {}).get('strength', 10)}
  敏捷: {char_info.get('stats', {}).get('agility', 10)}
  智力: {char_info.get('stats', {}).get('intelligence', 10)}
  体质: {char_info.get('stats', {}).get('constitution', 10)}
  智慧: {char_info.get('stats', {}).get('wisdom', 10)}
  魅力: {char_info.get('stats', {}).get('charisma', 10)}
"""
        
        # 发送消息给角色
        if hasattr(character, 'msg'):
            character.msg(stats_text)
        
        return CommandResult.success_result(stats_text)


# 角色命令列表
CHARACTER_COMMANDS = [
    WalkCommand(),
    RunCommand(),
    JumpCommand(),
    TalkCommand(),
    LookCommand(),
    RestCommand(),
    CharacterStatsCommand(),
]
