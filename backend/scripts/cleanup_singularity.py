#!/usr/bin/env python3
"""
清理重复的奇点屋根节点数据

用法:
    python cleanup_singularity.py              # 预览模式 (dry-run)
    python cleanup_singularity.py --execute    # 执行清理
"""

import sys
import argparse
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import db_session_context
from app.models.graph import Node
from app.models.root_manager import root_manager
from app.core.log import get_logger, LoggerNames

logger = get_logger(LoggerNames.GAME)


def count_root_nodes() -> int:
    """统计根节点数量"""
    with db_session_context() as session:
        count = session.query(Node).filter(
            Node.attributes['is_root'].astext == 'true'
        ).count()
        return count


def list_root_nodes():
    """列出所有根节点"""
    with db_session_context() as session:
        root_nodes = session.query(Node).filter(
            Node.attributes['is_root'].astext == 'true'
        ).order_by(Node.created_at.desc()).all()

        return [
            {
                'id': node.id,
                'uuid': str(node.uuid),
                'name': node.name,
                'created_at': node.created_at,
                'updated_at': node.updated_at,
                'is_active': node.is_active
            }
            for node in root_nodes
        ]


def cleanup_duplicate_root_nodes(dry_run: bool = True) -> bool:
    """
    清理重复的根节点

    Args:
        dry_run: True 预览模式，False 执行清理

    Returns:
        bool: 操作是否成功
    """
    root_nodes = list_root_nodes()

    if len(root_nodes) <= 1:
        logger.info(f"根节点数量正常: {len(root_nodes)} 个")
        return True

    logger.warning(f"发现 {len(root_nodes)} 个根节点:")

    for i, node in enumerate(root_nodes, 1):
        logger.info(
            f"  {i}. ID={node['id']}, UUID={node['uuid'][:8]}..., "
            f"name={node['name']}, created={node['created_at']}"
        )

    if dry_run:
        logger.info("dry-run 模式，未执行清理")
        return True

    # 执行清理：保留最新创建的，删除其他
    try:
        with db_session_context() as session:
            # 按创建时间排序，获取要保留的
            nodes_to_keep = session.query(Node).filter(
                Node.attributes['is_root'].astext == 'true'
            ).order_by(Node.created_at.desc()).all()

            if not nodes_to_keep:
                logger.error("无法获取根节点列表")
                return False

            # 保留第一个，删除其余
            kept_node = nodes_to_keep[0]
            logger.info(f"保留根节点: ID={kept_node.id}, name={kept_node.name}")

            for node in nodes_to_keep[1:]:
                logger.info(f"删除重复根节点: ID={node.id}, name={node.name}")
                session.delete(node)

            session.commit()
            logger.info(f"已清理 {len(nodes_to_keep) - 1} 个重复根节点")
            return True

    except Exception as e:
        logger.error(f"清理失败: {e}")
        return False


def validate_uniqueness():
    """验证根节点唯一性"""
    is_unique = root_manager.validate_root_node_uniqueness()
    if is_unique:
        logger.info("✓ 根节点唯一性验证通过")
    else:
        logger.error("✗ 根节点唯一性验证失败")
    return is_unique


def main():
    parser = argparse.ArgumentParser(description='清理重复的奇点屋根节点')
    parser.add_argument(
        '--execute',
        action='store_true',
        help='执行清理（默认是预览模式）'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='仅验证根节点唯一性'
    )
    parser.add_argument(
        '--count',
        action='store_true',
        help='仅显示根节点数量'
    )

    args = parser.parse_args()

    if args.count:
        count = count_root_nodes()
        print(f"根节点数量: {count}")
        return

    if args.validate:
        validate_uniqueness()
        return

    if args.execute:
        cleanup_duplicate_root_nodes(dry_run=False)
    else:
        cleanup_duplicate_root_nodes(dry_run=True)


if __name__ == '__main__':
    main()