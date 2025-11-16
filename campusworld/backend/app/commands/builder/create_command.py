# app/commands/build/create_command.py
"""
建造命令 - 统一的对象创建命令
"""

import json
import ast
from typing import List, Dict, Any, Optional, Type
from app.commands.base import SystemCommand, CommandResult, CommandType
from app.commands.builder.model_discovery import ModelDiscoverer # 模型发现器
from app.models.base import DefaultObject
from app.core.log import get_logger, LoggerNames

class CreateCommand(SystemCommand):
    def __init__(self):
        super().__init__(
            name="create",
            description="创建对象 - create ClassName = {参数}",
            aliases=["spawn", "build", "make"],
            command_type=CommandType.ADMIN
        )
        self.logger = get_logger(LoggerNames.COMMAND)
    
    def validate_args(self, args: List[str]) -> bool:
        """验证参数"""
        if len(args) < 2:
            return False
        
        # 检查是否包含等号
        command_str = ' '.join(args)
        if '=' not in command_str:
            return False
        
        return True
    
    def check_permission(self, context) -> bool:
        """检查权限"""
        # 只有管理员可以创建对象
        caller = context.get_caller()
        if not caller:
            return False
        return hasattr(caller, 'is_admin') and caller.is_admin
    
    def execute(self, context, args: List[str]) -> CommandResult:
        """执行创建命令"""
        try:
            # 解析命令
            command_str = ' '.join(args)
            parse_result = self._parse_create_command(command_str)
            
            if not parse_result['success']:
                return CommandResult.error_result(parse_result['error'])
            
            model_name = parse_result['model_name']
            parameters = parse_result['parameters']
            
            # 发现模型类
            model_class = ModelDiscoverer.get_model_class(model_name)
            if not model_class:
                available_models = ModelDiscoverer.list_models()
                return CommandResult.error_result(
                    f"未找到模型类 '{model_name}'。可用模型: {', '.join(available_models)}"
                )
            
            # 验证参数
            validation_result = self._validate_parameters(model_name, parameters)
            if not validation_result['success']:
                return CommandResult.error_result(validation_result['error'])
            
            # 创建对象
            creation_result = self._create_object(model_class, parameters, context)
            if not creation_result['success']:
                return CommandResult.error_result(creation_result['error'])
            
            obj = creation_result['object']
            
            # 返回成功结果
            message = f"成功创建 {model_name} 对象: {obj.get_node_name()} (UUID: {obj.get_node_uuid()})"
            return CommandResult.success_result(message)
            
        except Exception as e:
            self.logger.error(f"创建对象失败: {e}")
            return CommandResult.error_result(f"创建对象失败: {str(e)}")
    
    def _parse_create_command(self, command_str: str) -> Dict[str, Any]:
        """解析创建命令"""
        try:
            
            rest = command_str.strip()
            
            # 分割类名和参数
            if '=' not in rest:
                return {'success': False, 'error': '命令格式错误，缺少 "=" 符号'}
            
            parts = rest.split('=', 1)
            if len(parts) != 2:
                return {'success': False, 'error': '命令格式错误'}
            
            model_name = parts[0].strip()
            params_str = parts[1].strip()
            
            # 解析参数
            try:
                # 尝试使用 ast.literal_eval 解析（更安全）
                parameters = ast.literal_eval(params_str)
            except (ValueError, SyntaxError):
                try:
                    # 如果失败，尝试使用 json.loads
                    parameters = json.loads(params_str)
                except json.JSONDecodeError:
                    return {'success': False, 'error': '参数格式错误，请使用有效的 JSON 格式'}
            
            if not isinstance(parameters, dict):
                return {'success': False, 'error': '参数必须是字典格式'}
            
            return {
                'success': True,
                'model_name': model_name,
                'parameters': parameters
            }
            
        except Exception as e:
            return {'success': False, 'error': f'解析命令失败: {str(e)}'}
    
    def _validate_parameters(self, model_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证参数"""
        metadata = ModelDiscoverer.get_model_metadata(model_name)
        if not metadata:
            return {'success': False, 'error': f'无法获取模型 {model_name} 的元数据'}
        
        # 检查必需参数
        required_params = []
        for param_name, param_info in metadata['parameters'].items():
            if param_info['required']:
                required_params.append(param_name)
        
        missing_params = [param for param in required_params if param not in parameters]
        if missing_params:
            return {
                'success': False, 
                'error': f'缺少必需参数: {", ".join(missing_params)}'
            }
        
        # 检查参数类型（基础检查）
        for param_name, param_value in parameters.items():
            if param_name in metadata['parameters']:
                param_info = metadata['parameters'][param_name]
                expected_type = param_info['type']
                
                if expected_type and not isinstance(param_value, expected_type):
                    return {
                        'success': False,
                        'error': f'参数 {param_name} 类型错误，期望 {expected_type.__name__}，实际 {type(param_value).__name__}'
                    }
        
        return {'success': True}
    
    def _create_object(self, model_class: Type[DefaultObject], parameters: Dict[str, Any], context) -> Dict[str, Any]:
        """创建对象"""
        try:
            # 创建对象实例
            obj = model_class(**parameters)
            
            # 对象会自动同步到图数据库（通过 at_object_creation 钩子）
            
            return {
                'success': True,
                'object': obj
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'创建对象失败: {str(e)}'
            }
    
    def get_help(self) -> str:
        """获取帮助信息"""
        available_models = ModelDiscoverer.list_models()
        
        help_text = f"""
{self.name} 命令帮助
{'=' * (len(self.name) + 8)}

描述: {self.description}
用法: create ClassName = {{参数}}

可用模型类:
{chr(10).join(f"  - {model}" for model in available_models)}

示例:
  create User = {{"username": "test", "email": "test@example.com"}}
  create Campus = {{"name": "测试园区", "campus_type": "university"}}
  create Building = {{"name": "教学楼A", "building_type": "academic"}}

使用 'create info <模型名>' 查看特定模型的详细信息
"""
        return help_text.strip()
    
    def get_usage(self) -> str:
        """获取使用说明"""
        return "create ClassName = {参数}"


class CreateInfoCommand(SystemCommand):
    """
    创建信息命令 - 显示模型详细信息
    """
    
    def __init__(self):
        super().__init__(
            name="create_info",
            description="显示模型详细信息",
            aliases=["cinfo", "model_info"],
            command_type=CommandType.ADMIN
        )
    
    def validate_args(self, args: List[str]) -> bool:
        """验证参数"""
        return len(args) == 1
    
    def check_permission(self, context) -> bool:
        """检查权限"""
        caller = context.get_caller()
        if not caller:
            return False
        return hasattr(caller, 'is_admin') and caller.is_admin
    
    def execute(self, context, args: List[str]) -> CommandResult:
        """执行命令"""
        model_name = args[0].lower()
        
        # 获取模型信息
        model_info = ModelDiscoverer.get_model_info(model_name)
        if not model_info:
            available_models = ModelDiscoverer.list_models()
            return CommandResult.error_result(
                f"未找到模型 '{model_name}'。可用模型: {', '.join(available_models)}"
            )
        
        return CommandResult.success_result(model_info)
    
    def get_usage(self) -> str:
        """获取使用说明"""
        return "create_info <模型名>"
    