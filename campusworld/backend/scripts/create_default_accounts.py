#!/usr/bin/env python3
"""
创建默认账号脚本

参考Evennia框架设计，创建系统默认账号
包括admin、dev、campus三个账号

作者：AI Assistant
创建时间：2025-08-24
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def create_default_accounts():
    """创建默认账号"""
    print("🚀 开始创建默认账号")
    print("=" * 50)
    
    try:
        from app.models.accounts import AdminAccount, DeveloperAccount, CampusUserAccount
        from app.core.database import SessionLocal
        from app.models.graph import Node, NodeType
        from app.core.security import get_password_hash
        import uuid
        
        session = SessionLocal()
        
        # 检查是否已存在默认账号
        existing_accounts = session.query(Node).filter(
            Node.name.in_(['admin', 'dev', 'campus'])
        ).all()
        
        if existing_accounts:
            print("⚠️  默认账号已存在，跳过创建")
            for account in existing_accounts:
                print(f"  - {account.name} (ID: {account.id})")
            session.close()
            return True
        
        # 创建账号类型节点（如果不存在）
        account_type = session.query(NodeType).filter(
            NodeType.type_code == 'account'
        ).first()
        
        if not account_type:
            print("❌ 账号类型未找到，请先运行数据库迁移脚本")
            session.close()
            return False
        
        # 创建admin管理员账号
        print("\n📋 创建admin管理员账号")
        print("-" * 30)
        
        admin_account = AdminAccount(
            username='admin',
            email='admin@campusworld.com',
            hashed_password=get_password_hash('admin123'),
            description='系统管理员账号，拥有所有管理权限',
            created_by='system',
            disable_auto_sync=True,
        )
        
        # 处理datetime序列化问题
        admin_attributes = admin_account._node_attributes.copy()
        # 将datetime对象转换为ISO格式字符串
        for key, value in admin_attributes.items():
            if isinstance(value, datetime):
                admin_attributes[key] = value.isoformat()
        
        # 创建admin节点
        admin_node = Node(
            uuid=str(uuid.uuid4()),
            type_id=account_type.id,
            type_code='account',
            name='admin',
            description='系统管理员账号，拥有所有管理权限',
            is_active=True,
            is_public=False,
            access_level='admin',
            attributes=admin_attributes,
            tags=['system', 'admin', 'default']
        )
        
        session.add(admin_node)
        session.flush()  # 获取ID
        
        print(f"  ✅ 创建admin账号成功 (ID: {admin_node.id})")
        print(f"     用户名: {admin_account.username}")
        print(f"     邮箱: {admin_account.email}")
        print(f"     角色: {admin_account.roles}")
        print(f"     权限数量: {len(admin_account.permissions)}")
        
        # 创建dev开发者账号
        print("\n📋 创建dev开发者账号")
        print("-" * 30)
        
        dev_account = DeveloperAccount(
            username='dev',
            email='dev@campusworld.com',
            hashed_password=get_password_hash('dev123'),
            description='开发者账号，拥有开发和调试权限',
            created_by='admin',
            disable_auto_sync=True,
        )
        
        # 处理datetime序列化问题
        dev_attributes = dev_account._node_attributes.copy()
        for key, value in dev_attributes.items():
            if isinstance(value, datetime):
                dev_attributes[key] = value.isoformat()
        
        # 创建dev节点
        dev_node = Node(
            uuid=str(uuid.uuid4()),
            type_id=account_type.id,
            type_code='account',
            name='dev',
            description='开发者账号，拥有开发和调试权限',
            is_active=True,
            is_public=False,
            access_level='developer',
            attributes=dev_attributes,
            tags=['system', 'dev', 'default']
        )
        
        session.add(dev_node)
        session.flush()  # 获取ID
        
        print(f"  ✅ 创建dev账号成功 (ID: {dev_node.id})")
        print(f"     用户名: {dev_account.username}")
        print(f"     邮箱: {dev_account.email}")
        print(f"     角色: {dev_account.roles}")
        print(f"     权限数量: {len(dev_account.permissions)}")
        
        # 创建campus普通用户账号
        print("\n📋 创建campus普通用户账号")
        print("-" * 30)
        
        campus_account = CampusUserAccount(
            username='campus',
            email='campus@campusworld.com',
            hashed_password=get_password_hash('campus123'),
            description='园区用户账号，用于测试园区功能',
            created_by='admin',
            disable_auto_sync=True,
        )
        
        # 处理datetime序列化问题
        campus_attributes = campus_account._node_attributes.copy()
        for key, value in campus_attributes.items():
            if isinstance(value, datetime):
                campus_attributes[key] = value.isoformat()
        
        # 创建campus节点
        campus_node = Node(
            uuid=str(uuid.uuid4()),
            type_id=account_type.id,
            type_code='account',
            name='campus',
            description='园区用户账号，用于测试园区功能',
            is_active=True,
            is_public=True,
            access_level='normal',
            attributes=campus_attributes,
            tags=['system', 'user', 'campus', 'default']
        )
        
        session.add(campus_node)
        session.flush()  # 获取ID
        
        print(f"  ✅ 创建campus账号成功 (ID: {campus_node.id})")
        print(f"     用户名: {campus_account.username}")
        print(f"     邮箱: {campus_account.email}")
        print(f"     角色: {campus_account.roles}")
        print(f"     权限数量: {len(campus_account.permissions)}")
        
        # 提交事务
        session.commit()
        session.close()
        
        print("\n🎉 所有默认账号创建成功！")
        print("=" * 50)
        print("📋 账号信息汇总:")
        print("  👑 admin - 管理员账号")
        print("     - 用户名: admin")
        print("     - 密码: admin123")
        print("     - 权限: 所有管理权限")
        print("")
        print("  🔧 dev - 开发者账号")
        print("     - 用户名: dev")
        print("     - 密码: dev123")
        print("     - 权限: 开发和调试权限")
        print("")
        print("  👤 campus - 园区用户账号")
        print("     - 用户名: campus")
        print("     - 密码: campus123")
        print("     - 权限: 基本用户权限")
        print("")
        print("⚠️  注意: 这些是默认账号，建议在生产环境中修改密码！")
        
        return True
        
    except Exception as e:
        print(f"❌ 创建默认账号失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_accounts():
    """验证创建的账号"""
    print("\n🔍 验证创建的账号")
    print("=" * 50)
    
    try:
        from app.models.accounts import AdminAccount, DeveloperAccount, CampusUserAccount
        from app.core.database import SessionLocal
        from app.models.graph import Node, NodeType
        
        session = SessionLocal()
        
        # 查询所有账号节点
        account_nodes = session.query(Node).join(
            NodeType, Node.type_id == NodeType.id
        ).filter(
            NodeType.type_code == 'account'
        ).all()
        
        print(f"📊 找到 {len(account_nodes)} 个账号节点:")
        
        for node in account_nodes:
            print(f"\n  📋 {node.name} (ID: {node.id})")
            print(f"     - 类型: {node.type_code}")
            print(f"     - 描述: {node.description}")
            print(f"     - 状态: {'活跃' if node.is_active else '非活跃'}")
            print(f"     - 访问级别: {node.access_level}")
            print(f"     - 标签: {node.tags}")
            
            # 解析账号属性
            attributes = node.attributes or {}
            username = attributes.get('username', 'Unknown')
            email = attributes.get('email', 'Unknown')
            roles = attributes.get('roles', [])
            permissions = attributes.get('permissions', [])
            
            print(f"     - 用户名: {username}")
            print(f"     - 邮箱: {email}")
            print(f"     - 角色: {roles}")
            print(f"     - 权限数量: {len(permissions)}")
        
        session.close()
        
        return True
        
    except Exception as e:
        print(f"❌ 验证账号失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("🏗️  CampusWorld 默认账号创建工具")
    print("参考Evennia框架设计，创建系统默认账号")
    print("=" * 60)
    
    try:
        # 创建默认账号
        if create_default_accounts():
            # 验证创建的账号
            verify_accounts()
            print("\n✅ 默认账号创建和验证完成！")
            return 0
        else:
            print("\n❌ 默认账号创建失败！")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⏹️  操作被用户中断")
        return 1
    except Exception as e:
        print(f"\n\n💥 操作过程中发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
