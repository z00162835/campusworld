"""
统一版本管理 - 单一真相源

所有版本号应通过 get_version() 获取，不要在子模块中定义 __version__。
"""
from importlib.metadata import version, PackageNotFoundError
__version__ = '0.1.2'

def get_version() -> str:
    """获取版本号，优先使用 importlib.metadata，降级到 __version__"""
    try:
        return version('campusworld-backend')
    except PackageNotFoundError:
        return __version__
