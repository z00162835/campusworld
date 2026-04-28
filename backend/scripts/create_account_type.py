#!/usr/bin/env python3
"""
创建账号节点类型脚本

在数据库中创建account节点类型，用于存储账号信息

作者：AI Assistant
创建时间：2025-08-24
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def create_account_type():
    """创建账号节点类型"""
    print("🚀 开始创建账号节点类型")
    print("=" * 50)
    
    try:
        from app.core.database import SessionLocal
        from app.models.graph import NodeType
        from db.ontology.schema_envelope import account_node_type_schema_definition

        import uuid
        
        session = SessionLocal()
        
        # 检查是否已存在account类型
        existing_type = session.query(NodeType).filter(
            NodeType.type_code == 'account'
        ).first()
        
        if existing_type:
            print("⚠️  账号类型已存在，跳过创建")
            print(f"  - ID: {existing_type.id}")
            print(f"  - 类型代码: {existing_type.type_code}")
            print(f"  - 类型名称: {existing_type.type_name}")
            session.close()
            return True
        
        # 创建account节点类型
        account_type = NodeType(
            type_code='account',
            type_name='账号',
            typeclass='app.models.accounts.DefaultAccount',
            classname='DefaultAccount',
            module_path='app.models.accounts',
            description='用户账号类型，支持管理员、开发者和普通用户',
            schema_definition=account_node_type_schema_definition(),
            is_active=True
        )
        
        session.add(account_type)
        session.commit()
        
        print(f"✅ 账号节点类型创建成功")
        print(f"  - ID: {account_type.id}")
        print(f"  - 类型代码: {account_type.type_code}")
        print(f"  - 类型名称: {account_type.type_name}")
        print(f"  - 类型类: {account_type.typeclass}")
        print(f"  - 描述: {account_type.description}")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"❌ 创建账号节点类型失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("🏗️  CampusWorld 账号节点类型创建工具")
    print("=" * 60)
    
    try:
        if create_account_type():
            print("\n✅ 账号节点类型创建完成！")
            return 0
        else:
            print("\n❌ 账号节点类型创建失败！")
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
