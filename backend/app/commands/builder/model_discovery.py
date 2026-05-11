"""
模型发现模块 - 动态从数据库发现模型

参考业界最佳实践:
- 从 node_types 表动态加载模型类型
- 支持运行时注册新模型
- 无需硬编码模型列表
"""
from typing import Dict, List, Any, Optional
from app.core.log import get_logger, LoggerNames
logger = get_logger(LoggerNames.COMMAND)

class ModelDiscoverer:
    """
    模型发现器 - 动态从数据库加载

    不再使用硬编码的模型列表，而是从 node_types 表读取类型定义，
    然后动态导入对应的 Python 类。
    """

    def __init__(self):
        self._discovered_models: Dict[str, Any] = {}
        self._discovered = False

    def discover_models(self) -> Dict[str, Any]:
        """
        从数据库发现所有已注册的模型

        动态读取 node_types 表，使用 module_path 和 classname 字段
        来动态导入对应的 Python 类。
        """
        if self._discovered:
            return self._discovered_models
        try:
            from app.models.model_manager import model_manager
            node_types = model_manager.get_all_node_types()
            for node_type in node_types:
                type_code = node_type.type_code
                if node_type.status != 0:
                    continue
                try:
                    model_class = model_manager._get_node_type_class(type_code)
                    if model_class:
                        self._discovered_models[type_code] = {'class': model_class, 'type_name': node_type.type_name, 'typeclass': node_type.typeclass, 'description': node_type.description, 'schema': node_type.schema_definition}
                except Exception as e:
                    logger.warning(f'Failed to load model class {type_code}: {e}')
            self._discovered = True
            logger.info(f'Model discovery complete, found {len(self._discovered_models)} models')
        except ImportError as e:
            logger.warning(f'ModelManager import failed, using empty model list: {e}')
            self._discovered = True
        except Exception as e:
            logger.error(f'Error during model discovery{e}')
        return self._discovered_models

    def get_model(self, model_name: str) -> Optional[Any]:
        """获取指定名称的模型类"""
        if not self._discovered:
            self.discover_models()
        model_info = self._discovered_models.get(model_name)
        return model_info['class'] if model_info else None

    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """获取指定名称的模型信息"""
        if not self._discovered:
            self.discover_models()
        return self._discovered_models.get(model_name)

    def list_models(self) -> List[str]:
        """列出所有已发现的模型名称"""
        if not self._discovered:
            self.discover_models()
        return list(self._discovered_models.keys())

    def refresh(self):
        """刷新模型发现缓存"""
        self._discovered = False
        self._discovered_models = {}
        return self.discover_models()
model_discoverer = ModelDiscoverer()
