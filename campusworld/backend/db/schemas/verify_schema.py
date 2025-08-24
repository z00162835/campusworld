#!/usr/bin/env python3
"""
CampusWorld 数据库结构验证脚本

验证修复后的数据库schema是否创建成功

作者：AI Assistant
创建时间：2025-08-24
"""

import psycopg2
from psycopg2.extras import RealDictCursor

# 数据库连接配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'user': 'campusworld_dev_user',
    'password': 'campusworld_dev_password',
    'database': 'campusworld_dev'
}

def verify_database_structure():
    """验证数据库结构"""
    print("🔍 CampusWorld 数据库结构验证")
    print("=" * 60)
    
    try:
        # 连接数据库
        print("🔌 连接数据库...")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("✅ 数据库连接成功\n")
        
        # 1. 验证表结构
        print("📋 1. 验证表结构")
        print("-" * 40)
        
        tables_to_check = [
            'node_types', 'relationship_types', 'nodes', 
            'relationships', 'node_attribute_indexes', 'node_tag_indexes'
        ]
        
        for table_name in tables_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                result = cursor.fetchone()
                count = result['count']
                print(f"  ✅ 表 {table_name:<25}: {count:>3} 条记录")
            except Exception as e:
                print(f"  ❌ 表 {table_name:<25}: 不存在或访问失败 - {e}")
        
        # 2. 验证视图
        print("\n👁️ 2. 验证视图")
        print("-" * 40)
        
        views_to_check = ['active_nodes', 'active_relationships']
        for view_name in views_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) as count FROM {view_name}")
                result = cursor.fetchone()
                count = result['count']
                print(f"  ✅ 视图 {view_name:<23}: {count:>3} 条记录")
            except Exception as e:
                print(f"  ❌ 视图 {view_name:<23}: 不存在或访问失败 - {e}")
        
        # 3. 验证函数
        print("\n⚙️ 3. 验证函数")
        print("-" * 40)
        
        functions_to_check = ['update_node_attribute_indexes', 'update_node_tag_indexes']
        for func_name in functions_to_check:
            try:
                cursor.execute(f"""
                    SELECT COUNT(*) as count FROM information_schema.routines 
                    WHERE routine_name = '{func_name}'
                """)
                result = cursor.fetchone()
                count = result['count']
                print(f"  ✅ 函数 {func_name:<20}: {count:>3} 个")
            except Exception as e:
                print(f"  ❌ 函数 {func_name:<20}: 不存在或访问失败 - {e}")
        
        # 4. 验证索引
        print("\n🔍 4. 验证索引")
        print("-" * 40)
        
        # 检查主要表的索引
        tables_with_indexes = ['nodes', 'relationships', 'node_types', 'relationship_types']
        for table_name in tables_with_indexes:
            try:
                cursor.execute(f"""
                    SELECT COUNT(*) as count FROM pg_indexes 
                    WHERE tablename = '{table_name}'
                """)
                result = cursor.fetchone()
                count = result['count']
                print(f"  ✅ 表 {table_name:<23}: {count:>3} 个索引")
            except Exception as e:
                print(f"  ❌ 表 {table_name:<23}: 索引检查失败 - {e}")
        
        # 5. 验证扩展
        print("\n🔧 5. 验证扩展")
        print("-" * 40)
        
        extensions_to_check = ['uuid-ossp', 'pg_trgm']
        for ext_name in extensions_to_check:
            try:
                cursor.execute(f"""
                    SELECT COUNT(*) as count FROM pg_extension 
                    WHERE extname = '{ext_name}'
                """)
                result = cursor.fetchone()
                count = result['count']
                print(f"  ✅ 扩展 {ext_name:<22}: {count:>3} 个")
            except Exception as e:
                print(f"  ❌ 扩展 {ext_name:<22}: 检查失败 - {e}")
        
        # 6. 验证触发器
        print("\n⚡ 6. 验证触发器")
        print("-" * 40)
        
        try:
            cursor.execute("""
                SELECT COUNT(*) as count FROM information_schema.triggers 
                WHERE trigger_name LIKE '%node_%'
            """)
            result = cursor.fetchone()
            count = result['count']
            print(f"  ✅ 节点相关触发器: {count:>3} 个")
        except Exception as e:
            print(f"  ❌ 触发器检查失败: {e}")
        
        # 7. 验证约束
        print("\n🔒 7. 验证约束")
        print("-" * 40)
        
        try:
            cursor.execute("""
                SELECT COUNT(*) as count FROM information_schema.table_constraints 
                WHERE constraint_type = 'FOREIGN KEY' 
                AND table_name IN ('nodes', 'relationships')
            """)
            result = cursor.fetchone()
            count = result['count']
            print(f"  ✅ 外键约束: {count:>3} 个")
        except Exception as e:
            print(f"  ❌ 约束检查失败: {e}")
        
        # 8. 验证初始数据
        print("\n📊 8. 验证初始数据")
        print("-" * 40)
        
        # 检查节点类型数据
        try:
            cursor.execute("SELECT type_code, type_name FROM node_types ORDER BY type_code")
            node_types = cursor.fetchall()
            print(f"  ✅ 节点类型: {len(node_types)} 个")
            for nt in node_types:
                print(f"      - {nt['type_code']}: {nt['type_name']}")
        except Exception as e:
            print(f"  ❌ 节点类型检查失败: {e}")
        
        # 检查关系类型数据
        try:
            cursor.execute("SELECT type_code, type_name FROM relationship_types ORDER BY type_code")
            rel_types = cursor.fetchall()
            print(f"  ✅ 关系类型: {len(rel_types)} 个")
            for rt in rel_types:
                print(f"      - {rt['type_code']}: {rt['type_name']}")
        except Exception as e:
            print(f"  ❌ 关系类型检查失败: {e}")
        
        # 9. 测试基本查询
        print("\n🧪 9. 测试基本查询")
        print("-" * 40)
        
        # 测试节点查询
        try:
            cursor.execute("SELECT COUNT(*) as count FROM nodes WHERE is_active = TRUE")
            result = cursor.fetchone()
            count = result['count']
            print(f"  ✅ 活跃节点查询: {count} 个")
        except Exception as e:
            print(f"  ❌ 节点查询测试失败: {e}")
        
        # 测试关系查询
        try:
            cursor.execute("SELECT COUNT(*) as count FROM relationships WHERE is_active = TRUE")
            result = cursor.fetchone()
            count = result['count']
            print(f"  ✅ 活跃关系查询: {count} 个")
        except Exception as e:
            print(f"  ❌ 关系查询测试失败: {e}")
        
        # 测试视图查询
        try:
            cursor.execute("SELECT COUNT(*) as count FROM active_nodes")
            result = cursor.fetchone()
            count = result['count']
            print(f"  ✅ 活跃节点视图查询: {count} 个")
        except Exception as e:
            print(f"  ❌ 视图查询测试失败: {e}")
        
        print("\n" + "=" * 60)
        print("🎉 数据库结构验证完成！")
        print("=" * 60)
        
        conn.close()
        print("🔌 数据库连接已关闭")
        
    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")

if __name__ == "__main__":
    verify_database_structure()
