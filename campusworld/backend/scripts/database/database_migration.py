#!/usr/bin/env python3
"""
CampusWorld 数据库迁移脚本

从当前的纯图数据设计模型迁移到优化的数据库结构
包括创建新表、迁移数据、建立索引等

作者：AI Assistant
创建时间：2025-08-24
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# 配置
DATABASE_URL = "postgresql://campusworld:campusworld@localhost:5433/campusworld"
BACKUP_TABLES = True  # 是否备份现有表


class DatabaseMigrator:
    """数据库迁移器"""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        self.metadata = MetaData()
        
    def backup_existing_tables(self):
        """备份现有表"""
        if not BACKUP_TABLES:
            return
            
        print("🔄 备份现有表...")
        
        try:
            with self.engine.connect() as conn:
                # 检查是否存在旧表
                result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('nodes', 'relationships')
                """))
                
                existing_tables = [row[0] for row in result]
                
                for table_name in existing_tables:
                    backup_name = f"{table_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    conn.execute(text(f"CREATE TABLE {backup_name} AS SELECT * FROM {table_name}"))
                    print(f"  ✅ 备份表 {table_name} -> {backup_name}")
                    
                conn.commit()
                
        except SQLAlchemyError as e:
            print(f"  ❌ 备份失败: {e}")
            
    def create_optimized_schema(self):
        """创建优化的数据库结构"""
        print("🏗️ 创建优化的数据库结构...")
        
        try:
            with self.engine.connect() as conn:
                # 读取SQL文件
                sql_file = "database_schema_optimized.sql"
                if not os.path.exists(sql_file):
                    print(f"  ❌ SQL文件不存在: {sql_file}")
                    return False
                    
                with open(sql_file, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
                
                # 执行SQL语句
                statements = sql_content.split(';')
                for statement in statements:
                    statement = statement.strip()
                    if statement and not statement.startswith('--') and not statement.startswith('\\'):
                        try:
                            conn.execute(text(statement))
                            print(f"  ✅ 执行SQL: {statement[:50]}...")
                        except SQLAlchemyError as e:
                            if "already exists" not in str(e).lower():
                                print(f"  ⚠️ SQL执行警告: {e}")
                
                conn.commit()
                print("  ✅ 数据库结构创建完成")
                return True
                
        except SQLAlchemyError as e:
            print(f"  ❌ 创建数据库结构失败: {e}")
            return False
            
    def migrate_existing_data(self):
        """迁移现有数据"""
        print("🔄 迁移现有数据...")
        
        try:
            with self.engine.connect() as conn:
                # 检查是否存在旧表
                result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'nodes_backup'
                """))
                
                if not result.fetchone():
                    print("  ℹ️ 没有找到需要迁移的数据")
                    return True
                
                # 迁移节点数据
                self._migrate_nodes(conn)
                
                # 迁移关系数据
                self._migrate_relationships(conn)
                
                conn.commit()
                print("  ✅ 数据迁移完成")
                return True
                
        except SQLAlchemyError as e:
            print(f"  ❌ 数据迁移失败: {e}")
            return False
            
    def _migrate_nodes(self, conn):
        """迁移节点数据"""
        print("  🔄 迁移节点数据...")
        
        # 获取备份表名
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'nodes_backup_%'
            ORDER BY table_name DESC
            LIMIT 1
        """))
        
        backup_table = result.fetchone()[0]
        
        # 迁移数据
        conn.execute(text(f"""
            INSERT INTO nodes (
                uuid, type_code, name, description, is_active, is_public, 
                access_level, location_id, home_id, attributes, tags, 
                created_at, updated_at
            )
            SELECT 
                uuid::uuid,
                type,
                name,
                description,
                is_active,
                is_public,
                access_level,
                location_id,
                home_id,
                attributes,
                tags,
                created_at,
                updated_at
            FROM {backup_table}
        """))
        
        # 更新type_id
        conn.execute(text("""
            UPDATE nodes 
            SET type_id = nt.id 
            FROM node_types nt 
            WHERE nodes.type_code = nt.type_code
        """))
        
        print(f"  ✅ 节点数据迁移完成")
        
    def _migrate_relationships(self, conn):
        """迁移关系数据"""
        print("  🔄 迁移关系数据...")
        
        # 获取备份表名
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'relationships_backup_%'
            ORDER BY table_name DESC
            LIMIT 1
        """))
        
        if not result.fetchone():
            print("  ℹ️ 没有关系数据需要迁移")
            return
            
        backup_table = result.fetchone()[0]
        
        # 迁移数据
        conn.execute(text(f"""
            INSERT INTO relationships (
                uuid, type_code, source_id, target_id, is_active, 
                weight, attributes, created_at, updated_at
            )
            SELECT 
                uuid::uuid,
                type,
                source_id,
                target_id,
                is_active,
                weight,
                attributes,
                created_at,
                updated_at
            FROM {backup_table}
        """))
        
        # 更新type_id
        conn.execute(text("""
            UPDATE relationships 
            SET type_id = rt.id 
            FROM relationship_types rt 
            WHERE relationships.type_code = rt.type_code
        """))
        
        print(f"  ✅ 关系数据迁移完成")
        
    def verify_migration(self):
        """验证迁移结果"""
        print("🔍 验证迁移结果...")
        
        try:
            with self.engine.connect() as conn:
                # 检查表是否存在
                tables = ['node_types', 'relationship_types', 'nodes', 'relationships', 
                         'node_attribute_indexes', 'node_tag_indexes']
                
                for table in tables:
                    result = conn.execute(text(f"""
                        SELECT COUNT(*) FROM {table}
                    """))
                    count = result.fetchone()[0]
                    print(f"  ✅ 表 {table}: {count} 条记录")
                
                # 检查索引
                result = conn.execute(text("""
                    SELECT indexname, tablename 
                    FROM pg_indexes 
                    WHERE schemaname = 'public' 
                    AND tablename IN ('nodes', 'relationships')
                    ORDER BY tablename, indexname
                """))
                
                indexes = result.fetchall()
                print(f"  ✅ 创建了 {len(indexes)} 个索引")
                
                return True
                
        except SQLAlchemyError as e:
            print(f"  ❌ 验证失败: {e}")
            return False
            
    def run_migration(self):
        """运行完整迁移"""
        print("🚀 开始数据库迁移...")
        print("=" * 50)
        
        try:
            # 1. 备份现有表
            self.backup_existing_tables()
            
            # 2. 创建优化结构
            if not self.create_optimized_schema():
                return False
                
            # 3. 迁移数据
            if not self.migrate_existing_data():
                return False
                
            # 4. 验证结果
            if not self.verify_migration():
                return False
                
            print("=" * 50)
            print("🎉 数据库迁移完成！")
            return True
            
        except Exception as e:
            print(f"❌ 迁移过程中发生错误: {e}")
            return False


def main():
    """主函数"""
    print("CampusWorld 数据库迁移工具")
    print("=" * 50)
    
    # 检查环境变量
    database_url = os.getenv('DATABASE_URL', DATABASE_URL)
    
    # 创建迁移器
    migrator = DatabaseMigrator(database_url)
    
    # 运行迁移
    success = migrator.run_migration()
    
    if success:
        print("\n✅ 迁移成功！新的数据库结构已就绪。")
        print("\n📋 下一步操作：")
        print("1. 更新应用配置以使用新的数据库结构")
        print("2. 测试新的API接口")
        print("3. 验证数据完整性")
    else:
        print("\n❌ 迁移失败！请检查错误日志。")
        sys.exit(1)


if __name__ == "__main__":
    main()
