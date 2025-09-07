#!/usr/bin/env python3
"""
奇点房间测试脚本

测试Singularity Room的创建、用户spawn和基本功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.root_manager import root_manager
from app.models.room import SingularityRoom
from app.models.user import User
from app.core.log import get_logger, LoggerNames


def test_singularity_room_creation():
    """测试奇点房间创建"""
    logger = get_logger(LoggerNames.GAME)
    logger.info("测试1: 奇点房间创建")
    
    try:
        # 初始化根节点
        success = root_manager.initialize_root_node(force_recreate=True)
        if not success:
            logger.error("奇点房间创建失败")
            return False
        
        # 获取根节点信息
        root_info = root_manager.get_root_node_info()
        if not root_info:
            logger.error("无法获取根节点信息")
            return False
        
        # 验证根节点属性
        assert root_info['name'] == "Singularity Room", f"房间名称错误: {root_info['name']}"
        assert root_info['type'] == "room", f"房间类型错误: {root_info['type']}"
        assert root_info['is_root'] == True, f"不是根节点: {root_info['is_root']}"
        assert root_info['is_home'] == True, f"不是默认home: {root_info['is_home']}"
        
        logger.info("✓ 奇点房间创建测试通过")
        return True
        
    except Exception as e:
        logger.error(f"奇点房间创建测试失败: {e}")
        return False


def test_user_spawn():
    """测试用户spawn到奇点房间"""
    logger = get_logger(LoggerNames.GAME)
    logger.info("测试2: 用户spawn到奇点房间")
    
    try:
        # 创建测试用户
        test_user = User(
            username="test_user_spawn",
            email="test@example.com",
            hashed_password="test_hash"
        )
        
        # 确保根节点存在
        if not root_manager.ensure_root_node_exists():
            logger.error("根节点不存在")
            return False
        
        # 获取根节点
        root_node = root_manager.get_root_node()
        if not root_node:
            logger.error("无法获取根节点")
            return False
        
        # 测试spawn到奇点房间
        success = test_user.spawn_to_singularity_room()
        if not success:
            logger.error("用户spawn失败")
            return False
        
        # 验证用户位置
        assert test_user.location_id == root_node.id, f"用户位置错误: {test_user.location_id} != {root_node.id}"
        assert test_user.home_id == root_node.id, f"用户home错误: {test_user.home_id} != {root_node.id}"
        
        # 验证用户是否在奇点房间
        assert test_user._is_in_singularity_room() == True, "用户不在奇点房间"
        
        logger.info("✓ 用户spawn测试通过")
        return True
        
    except Exception as e:
        logger.error(f"用户spawn测试失败: {e}")
        return False


def test_room_functionality():
    """测试房间功能"""
    logger = get_logger(LoggerNames.GAME)
    logger.info("测试3: 房间功能")
    
    try:
        # 创建奇点房间实例
        singularity_room = SingularityRoom()
        
        # 测试房间属性
        assert singularity_room.is_root == True, "不是根节点"
        assert singularity_room.is_home == True, "不是默认home"
        assert singularity_room.room_type == "singularity", f"房间类型错误: {singularity_room.room_type}"
        
        # 测试房间描述
        description = singularity_room.get_detailed_description()
        assert "CampusOS" in description, "房间描述不包含CampusOS"
        assert "欢迎来到CampusOS的主入口" in description, "房间描述不包含欢迎信息"
        assert "奇点" in description, "房间描述不包含奇点"
        
        # 测试房间信息
        room_info = singularity_room.get_room_info()
        assert room_info['name'] == "Singularity Room", f"房间名称错误: {room_info['name']}"
        assert room_info['is_root'] == True, "不是根节点"
        assert room_info['is_home'] == True, "不是默认home"
        
        logger.info("✓ 房间功能测试通过")
        return True
        
    except Exception as e:
        logger.error(f"房间功能测试失败: {e}")
        return False


def test_root_manager():
    """测试根节点管理器"""
    logger = get_logger(LoggerNames.GAME)
    logger.info("测试4: 根节点管理器")
    
    try:
        # 测试根节点存在性检查
        exists = root_manager.ensure_root_node_exists()
        assert exists == True, "根节点不存在"
        
        # 测试根节点获取
        root_node = root_manager.get_root_node()
        assert root_node is not None, "无法获取根节点"
        
        # 测试根节点信息
        root_info = root_manager.get_root_node_info()
        assert root_info is not None, "无法获取根节点信息"
        assert root_info['name'] == "Singularity Room", f"根节点名称错误: {root_info['name']}"
        
        # 测试根节点统计
        stats = root_manager.get_root_node_statistics()
        assert stats is not None, "无法获取根节点统计"
        assert 'root_node_id' in stats, "统计信息缺少root_node_id"
        assert 'users_in_root' in stats, "统计信息缺少users_in_root"
        
        # 测试根节点检查
        is_root = root_manager.is_root_node(root_node.id)
        assert is_root == True, "根节点检查失败"
        
        logger.info("✓ 根节点管理器测试通过")
        return True
        
    except Exception as e:
        logger.error(f"根节点管理器测试失败: {e}")
        return False


def test_user_location_management():
    """测试用户位置管理"""
    logger = get_logger(LoggerNames.GAME)
    logger.info("测试5: 用户位置管理")
    
    try:
        # 创建测试用户
        test_user = User(
            username="test_user_location",
            email="test_location@example.com",
            hashed_password="test_hash"
        )
        
        # 确保根节点存在
        root_manager.ensure_root_node_exists()
        root_node = root_manager.get_root_node()
        
        # 测试spawn到home
        success = test_user.spawn_to_home()
        assert success == True, "spawn到home失败"
        
        # 验证位置
        assert test_user.location_id == root_node.id, "位置设置错误"
        assert test_user.home_id == root_node.id, "home设置错误"
        
        # 测试位置信息获取
        location_info = test_user.get_current_location_info()
        assert location_info is not None, "无法获取位置信息"
        assert location_info['name'] == "Singularity Room", f"位置名称错误: {location_info['name']}"
        assert location_info['is_root'] == True, "不是根节点"
        
        # 测试spawn信息
        spawn_info = test_user.get_spawn_info()
        assert spawn_info['is_in_singularity_room'] == True, "不在奇点房间"
        assert spawn_info['can_spawn_to_home'] == True, "无法spawn到home"
        
        logger.info("✓ 用户位置管理测试通过")
        return True
        
    except Exception as e:
        logger.error(f"用户位置管理测试失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    logger = get_logger(LoggerNames.GAME)
    logger.info("=" * 60)
    logger.info("开始运行奇点房间测试套件")
    logger.info("=" * 60)
    
    tests = [
        ("奇点房间创建", test_singularity_room_creation),
        ("用户spawn", test_user_spawn),
        ("房间功能", test_room_functionality),
        ("根节点管理器", test_root_manager),
        ("用户位置管理", test_user_location_management)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\n运行测试: {test_name}")
            if test_func():
                passed += 1
                logger.info(f"✓ {test_name} 通过")
            else:
                failed += 1
                logger.error(f"✗ {test_name} 失败")
        except Exception as e:
            failed += 1
            logger.error(f"✗ {test_name} 异常: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info(f"测试结果: {passed} 通过, {failed} 失败")
    logger.info("=" * 60)
    
    return failed == 0


def main():
    """主函数"""
    success = run_all_tests()
    
    if success:
        print("\n🎉 所有测试通过！奇点房间系统工作正常。")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败，请检查日志。")
        sys.exit(1)


if __name__ == "__main__":
    main()
