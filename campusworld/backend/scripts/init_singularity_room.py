#!/usr/bin/env python3
"""
奇点房间初始化脚本

确保Singularity Room作为系统的根节点存在
参考Evennia的DefaultHome初始化机制
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal, engine
from app.models.root_manager import root_manager
from app.models.room import SingularityRoom
from app.core.log import get_logger, LoggerNames


def init_singularity_room(force_recreate: bool = False) -> bool:
    """
    初始化奇点房间
    
    Args:
        force_recreate: 是否强制重新创建
        
    Returns:
        bool: 初始化是否成功
    """
    logger = get_logger(LoggerNames.GAME)
    
    try:
        logger.info("开始初始化奇点房间...")
        
        # 确保数据库连接正常
        session = SessionLocal()
        try:
            # 测试数据库连接
            from sqlalchemy import text
            session.execute(text("SELECT 1"))
            logger.info("数据库连接正常")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False
        finally:
            session.close()
        
        # 初始化根节点
        success = root_manager.initialize_root_node(force_recreate=force_recreate)
        
        if success:
            # 获取根节点信息
            root_info = root_manager.get_root_node_info()
            if root_info:
                logger.info(f"奇点房间初始化成功: {root_info['name']} (ID: {root_info['id']})")
                logger.info(f"根节点UUID: {root_info['uuid']}")
                logger.info(f"是否为根节点: {root_info['is_root']}")
                logger.info(f"是否为默认home: {root_info['is_home']}")
            else:
                logger.warning("奇点房间初始化成功，但无法获取详细信息")
        else:
            logger.error("奇点房间初始化失败")
        
        return success
        
    except Exception as e:
        logger.error(f"初始化奇点房间时发生错误: {e}")
        return False


def verify_singularity_room() -> bool:
    """
    验证奇点房间是否正确设置
    
    Returns:
        bool: 验证是否通过
    """
    logger = get_logger(LoggerNames.GAME)
    
    try:
        logger.info("开始验证奇点房间设置...")
        
        # 确保根节点存在
        if not root_manager.ensure_root_node_exists():
            logger.error("根节点不存在且无法创建")
            return False
        
        # 获取根节点信息
        root_info = root_manager.get_root_node_info()
        if not root_info:
            logger.error("无法获取根节点信息")
            return False
        
        # 验证根节点属性
        checks = [
            ("名称", root_info['name'] == "Singularity Room"),
            ("类型", root_info['type'] == "room"),
            ("是否为根节点", root_info['is_root'] == True),
            ("是否为默认home", root_info['is_home'] == True),
            ("是否活跃", root_info['is_active'] == True),
            ("是否公开", root_info['is_public'] == True)
        ]
        
        all_passed = True
        for check_name, check_result in checks:
            if check_result:
                logger.info(f"✓ {check_name}: 通过")
            else:
                logger.error(f"✗ {check_name}: 失败")
                all_passed = False
        
        # 获取统计信息
        stats = root_manager.get_root_node_statistics()
        if stats:
            logger.info(f"根节点统计信息:")
            logger.info(f"  - 房间ID: {stats.get('root_node_id', 'N/A')}")
            logger.info(f"  - 房间名称: {stats.get('root_node_name', 'N/A')}")
            logger.info(f"  - 房间内用户数: {stats.get('users_in_root', 0)}")
            logger.info(f"  - 房间内对象数: {stats.get('objects_in_root', 0)}")
            logger.info(f"  - 房间容量: {stats.get('room_capacity', 0)}")
            logger.info(f"  - 房间是否已满: {stats.get('is_full', False)}")
        
        if all_passed:
            logger.info("奇点房间验证通过")
        else:
            logger.error("奇点房间验证失败")
        
        return all_passed
        
    except Exception as e:
        logger.error(f"验证奇点房间时发生错误: {e}")
        return False


def migrate_existing_users() -> bool:
    """
    迁移现有用户到奇点房间
    
    将现有用户的home_id设置为奇点房间
    """
    logger = get_logger(LoggerNames.GAME)
    
    try:
        logger.info("开始迁移现有用户到奇点房间...")
        
        # 确保根节点存在
        if not root_manager.ensure_root_node_exists():
            logger.error("根节点不存在，无法迁移用户")
            return False
        
        # 获取根节点
        root_node = root_manager.get_root_node()
        if not root_node:
            logger.error("无法获取根节点")
            return False
        
        session = SessionLocal()
        try:
            from app.models.graph import Node
            
            # 查找所有用户
            users = session.query(Node).filter(
                Node.type_code == 'user'
            ).all()
            
            migrated_count = 0
            for user in users:
                # 检查用户是否已有home_id
                if not user.home_id:
                    # 设置home_id为根节点
                    user.home_id = root_node.id
                    migrated_count += 1
                    logger.info(f"迁移用户: {user.attributes.get('username', 'Unknown')} (ID: {user.id})")
            
            session.commit()
            logger.info(f"成功迁移 {migrated_count} 个用户到奇点房间")
            
            return True
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"迁移现有用户时发生错误: {e}")
        return False


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="奇点房间初始化脚本")
    parser.add_argument("--force", action="store_true", help="强制重新创建奇点房间")
    parser.add_argument("--verify", action="store_true", help="仅验证奇点房间设置")
    parser.add_argument("--migrate", action="store_true", help="迁移现有用户到奇点房间")
    
    args = parser.parse_args()
    
    logger = get_logger(LoggerNames.GAME)
    logger.info("=" * 60)
    logger.info("奇点房间初始化脚本启动")
    logger.info("=" * 60)
    
    success = True
    
    if args.verify:
        # 仅验证
        success = verify_singularity_room()
    else:
        # 初始化奇点房间
        success = init_singularity_room(force_recreate=args.force)
        
        if success:
            # 验证设置
            success = verify_singularity_room()
            
            if success and args.migrate:
                # 迁移现有用户
                success = migrate_existing_users()
    
    if success:
        logger.info("=" * 60)
        logger.info("奇点房间初始化完成")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("=" * 60)
        logger.error("奇点房间初始化失败")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
