"""
通过配置文件和环境变量管理路径
"""

import os
from pathlib import Path
from typing import Optional

class ProjectPaths:
    """项目路径管理器"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self._project_root = None
        self._backend_root = None
        self._config_dir = None
        self._logs_dir = None
    
    def get_project_root(self) -> Path:
        """获取项目根目录"""
        if self._project_root is None:
            self._project_root = self._detect_project_root()
        return self._project_root
    
    def get_backend_root(self) -> Path:
        """获取后端根目录"""
        if self._backend_root is None:
            project_root = self.get_project_root()
            if self.config_manager:
                backend_dir = self.config_manager.get('project.backend_dir', 'backend')
            else:
                backend_dir = os.getenv('CAMPUSWORLD_BACKEND_DIR', 'backend')
            self._backend_root = project_root / backend_dir
        return self._backend_root
    
    def get_config_dir(self) -> Path:
        """获取配置目录"""
        if self._config_dir is None:
            backend_root = self.get_backend_root()
            if self.config_manager:
                config_dir = self.config_manager.get('project.config_dir', 'config')
            else:
                config_dir = os.getenv('CAMPUSWORLD_CONFIG_DIR', 'config')
            self._config_dir = backend_root / config_dir
        return self._config_dir
    
    def get_logs_dir(self) -> Path:
        """获取日志目录"""
        if self._logs_dir is None:
            backend_root = self.get_backend_root()
            if self.config_manager:
                logs_dir = self.config_manager.get('project.logs_dir', 'logs')
            else:
                logs_dir = os.getenv('CAMPUSWORLD_LOGS_DIR', 'logs')
            self._logs_dir = backend_root / logs_dir
        return self._logs_dir
    
    def _detect_project_root(self) -> Path:
        """检测项目根目录"""
        # 1. 环境变量优先
        if 'CAMPUSWORLD_ROOT' in os.environ:
            root_path = Path(os.environ['CAMPUSWORLD_ROOT'])
            if root_path.exists():
                return root_path.resolve()
        
        # 2. 从当前文件位置查找
        current_file = Path(__file__).resolve()
        current_dir = current_file.parent
        
        # 向上查找，直到找到包含backend目录的目录（项目根目录）
        while current_dir.parent != current_dir:
            # 检查是否包含backend目录，且backend目录下有config和app目录
            backend_dir = current_dir / "backend"
            if (backend_dir.exists() and 
                (backend_dir / "config").exists() and 
                (backend_dir / "app").exists()):
                return current_dir  # 返回包含backend目录的父目录
            current_dir = current_dir.parent
        
        # 3. 使用当前工作目录
        return Path.cwd().resolve()

# 全局路径管理器实例
_paths_manager = None

def get_paths_manager(config_manager=None) -> ProjectPaths:
    """获取路径管理器实例"""
    global _paths_manager
    if _paths_manager is None:
        _paths_manager = ProjectPaths(config_manager)
    return _paths_manager

# 便捷函数
def get_project_root(config_manager=None) -> Path:
    """获取项目根目录"""
    return get_paths_manager(config_manager).get_project_root()

def get_backend_root(config_manager=None) -> Path:
    """获取后端根目录"""
    return get_paths_manager(config_manager).get_backend_root()

def get_config_dir(config_manager=None) -> Path:
    """获取配置目录"""
    return get_paths_manager(config_manager).get_config_dir()

def get_logs_dir(config_manager=None) -> Path:
    """获取日志目录"""
    return get_paths_manager(config_manager).get_logs_dir()