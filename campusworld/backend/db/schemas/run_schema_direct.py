#!/usr/bin/env python3
"""
CampusWorld 数据库Schema直接执行脚本

直接执行修复后的SQL文件，避免复杂的迁移逻辑
用于快速创建数据库结构

作者：AI Assistant
创建时间：2025-08-24
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# 数据库连接配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5433')),
    'user': 'campusworld_dev_user',
    'password': 'campusworld_dev_password',
    'database': 'campusworld_dev'
}

def execute_sql_file(sql_file_path: str):
    """直接执行SQL文件"""
    print(f"🚀 开始执行SQL文件: {sql_file_path}")
    
    if not os.path.exists(sql_file_path):
        print(f"❌ SQL文件不存在: {sql_file_path}")
        return False
    
    try:
        # 连接数据库
        print("🔌 连接数据库...")
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("✅ 数据库连接成功")
        
        # 读取SQL文件
        print("📖 读取SQL文件...")
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 分割SQL语句（简单分割，避免分割函数定义）
        print("✂️ 分割SQL语句...")
        statements = split_sql_statements(sql_content)
        print(f"📊 共分割出 {len(statements)} 个SQL语句")
        
        # 执行SQL语句
        print("⚡ 开始执行SQL语句...")
        success_count = 0
        error_count = 0
        
        for i, statement in enumerate(statements, 1):
            statement = statement.strip()
            if not statement or statement.startswith('--') or statement.startswith('\\'):
                continue
                
            try:
                cursor.execute(statement)
                print(f"  ✅ [{i:3d}/{len(statements)}] 执行成功: {statement[:50]}...")
                success_count += 1
            except Exception as e:
                error_msg = str(e)
                if "already exists" in error_msg.lower():
                    print(f"  ⚠️ [{i:3d}/{len(statements)}] 已存在: {statement[:50]}...")
                    success_count += 1
                else:
                    print(f"  ❌ [{i:3d}/{len(statements)}] 执行失败: {statement[:50]}...")
                    print(f"     错误: {error_msg}")
                    error_count += 1
        
        # 提交事务
        conn.commit()
        
        print("\n" + "="*60)
        print("📊 执行结果统计")
        print("="*60)
        print(f"✅ 成功执行: {success_count} 个")
        print(f"❌ 执行失败: {error_count} 个")
        print(f"📊 总计: {len(statements)} 个")
        
        if error_count == 0:
            print("🎉 所有SQL语句执行成功！")
            return True
        else:
            print("⚠️ 部分SQL语句执行失败，请检查错误日志")
            return False
            
    except Exception as e:
        print(f"❌ 执行过程中发生错误: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()
            print("🔌 数据库连接已关闭")

def split_sql_statements(sql_content: str):
    """智能分割SQL语句，避免分割函数定义"""
    statements = []
    current_statement = ""
    in_function = False
    in_dollar_quote = False
    
    lines = sql_content.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # 跳过注释和空行
        if not line or line.startswith('--'):
            continue
            
        # 检查是否进入函数定义
        if 'CREATE OR REPLACE FUNCTION' in line.upper():
            in_function = True
            current_statement += line + "\n"
            continue
            
        # 检查是否进入美元引号
        if '$$' in line:
            if not in_dollar_quote:
                in_dollar_quote = True
            else:
                in_dollar_quote = False
                current_statement += line + "\n"
                continue
                
        # 如果在函数定义中，继续累积
        if in_function:
            current_statement += line + "\n"
            # 检查函数是否结束
            if line.endswith('$$ LANGUAGE plpgsql'):
                in_function = False
                statements.append(current_statement)
                current_statement = ""
            continue
            
        # 如果在美元引号中，继续累积
        if in_dollar_quote:
            current_statement += line + "\n"
            continue
            
        # 检查是否进入触发器定义
        if 'CREATE TRIGGER' in line.upper():
            current_statement += line + "\n"
            continue
            
        # 检查触发器是否结束
        if line.endswith('EXECUTE FUNCTION') and current_statement.strip().startswith('CREATE TRIGGER'):
            current_statement += line + "\n"
            statements.append(current_statement)
            current_statement = ""
            continue
            
        # 检查是否进入视图定义
        if 'CREATE VIEW' in line.upper():
            current_statement += line + "\n"
            continue
            
        # 检查视图是否结束
        if line.endswith(';') and current_statement.strip().startswith('CREATE VIEW'):
            current_statement += line + "\n"
            statements.append(current_statement)
            current_statement = ""
            continue
            
        # 普通SQL语句，按分号分割
        if line.endswith(';'):
            current_statement += line + "\n"
            if current_statement.strip():
                statements.append(current_statement)
                current_statement = ""
        else:
            current_statement += line + "\n"
            
    # 添加最后一个语句
    if current_statement.strip():
        statements.append(current_statement)
        
    return statements

def verify_schema():
    """验证数据库结构是否创建成功"""
    print("\n🔍 验证数据库结构...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 检查表是否创建成功
        tables_to_check = [
            'node_types', 'relationship_types', 'nodes', 
            'relationships', 'node_attribute_indexes', 'node_tag_indexes'
        ]
        
        print("📋 检查表结构:")
        for table_name in tables_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  ✅ 表 {table_name}: {count} 条记录")
            except Exception as e:
                print(f"  ❌ 表 {table_name}: 不存在或访问失败 - {e}")
        
        # 检查视图是否创建成功
        views_to_check = ['active_nodes', 'active_relationships']
        print("\n👁️ 检查视图:")
        for view_name in views_to_check:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {view_name}")
                count = cursor.fetchone()[0]
                print(f"  ✅ 视图 {view_name}: {count} 条记录")
            except Exception as e:
                print(f"  ❌ 视图 {view_name}: 不存在或访问失败 - {e}")
        
        # 检查函数是否创建成功
        functions_to_check = ['update_node_attribute_indexes', 'update_node_tag_indexes']
        print("\n⚙️ 检查函数:")
        for func_name in functions_to_check:
            try:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM information_schema.routines 
                    WHERE routine_name = '{func_name}'
                """)
                count = cursor.fetchone()[0]
                print(f"  ✅ 函数 {func_name}: {count} 个")
            except Exception as e:
                print(f"  ❌ 函数 {func_name}: 不存在或访问失败 - {e}")
        
        conn.close()
        print("\n✅ 验证完成")
        
    except Exception as e:
        print(f"❌ 验证过程中发生错误: {e}")

def main():
    """主函数"""
    print("CampusWorld 数据库Schema直接执行工具")
    print("=" * 60)
    
    # 检查SQL文件
    sql_file = "database_schema.sql"
    
    if not os.path.exists(sql_file):
        print(f"❌ SQL文件不存在: {sql_file}")
        print("请确保 database_schema_fixed.sql 文件在当前目录")
        return
    
    # 执行SQL文件
    success = execute_sql_file(sql_file)
    
    if success:
        # 验证结果
        verify_schema()
        print("\n🎉 数据库结构创建成功！")
    else:
        print("\n❌ 数据库结构创建失败！")

if __name__ == "__main__":
    main()
