#!/usr/bin/env python3
"""
Demo Building Generator Test Runner

快速运行Demo Building Generator的所有测试
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.log import get_logger, LoggerNames


def run_demo_building_tests():
    """运行Demo Building Generator测试"""
    logger = get_logger(LoggerNames.GAME)
    
    print("=" * 80)
    print("Demo Building Generator 测试运行器")
    print("=" * 80)
    
    try:
        # 导入测试模块
        from tests.test_demo_building_generator import run_all_tests
        
        # 运行测试
        success = run_all_tests()
        
        if success:
            print("\n🎉 所有测试通过！Demo Building Generator工作正常。")
            return True
        else:
            print("\n❌ 部分测试失败，请检查日志。")
            return False
            
    except ImportError as e:
        logger.error(f"导入测试模块失败: {e}")
        print(f"❌ 导入错误: {e}")
        return False
    except Exception as e:
        logger.error(f"运行测试失败: {e}")
        print(f"❌ 运行错误: {e}")
        return False


def run_demo_building_example():
    """运行Demo Building Generator示例"""
    logger = get_logger(LoggerNames.GAME)
    
    print("=" * 80)
    print("Demo Building Generator 示例运行器")
    print("=" * 80)
    
    try:
        # 导入示例模块
        from tests.demo_building_example import main
        
        # 运行示例
        success = main()
        
        if success:
            print("\n🎉 示例运行成功！")
            return True
        else:
            print("\n❌ 示例运行失败，请检查日志。")
            return False
            
    except ImportError as e:
        logger.error(f"导入示例模块失败: {e}")
        print(f"❌ 导入错误: {e}")
        return False
    except Exception as e:
        logger.error(f"运行示例失败: {e}")
        print(f"❌ 运行错误: {e}")
        return False


def main():
    """主函数"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "test":
            return run_demo_building_tests()
        elif command == "example":
            return run_demo_building_example()
        elif command == "all":
            print("运行所有Demo Building Generator测试和示例...")
            test_success = run_demo_building_tests()
            print("\n" + "=" * 80)
            example_success = run_demo_building_example()
            return test_success and example_success
        else:
            print(f"未知命令: {command}")
            print("可用命令: test, example, all")
            return False
    else:
        # 默认运行测试
        return run_demo_building_tests()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
