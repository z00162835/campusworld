#!/usr/bin/env python3
"""
命令系统数据迁移脚本

将现有命令系统的配置从代码迁移到数据库：
1. 创建命令相关的node_types记录
2. 将系统命令配置迁移到数据库
3. 建立命令与命令集合的关系
4. 验证迁移结果

作者：AI Assistant
创建时间：2025-08-24
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def create_command_node_types():
    """创建命令相关的节点类型定义"""
    print("\n🔧 创建命令相关的节点类型定义")
    print("=" * 50)
    
    try:
        from app.core.database import SessionLocal
        from sqlalchemy import text
        
        session = SessionLocal()
        
        # 命令相关的节点类型定义
        command_node_types = [
            {
                'type_code': 'command',
                'type_name': 'Command',
                'typeclass': 'app.models.commands.Command',
                'classname': 'Command',
                'module_path': 'app.models.commands',
                'description': '基础命令类型，所有命令都继承自此类',
                'schema_definition': {
                    'key': 'string',
                    'aliases': 'array',
                    'locks': 'string',
                    'help_category': 'string',
                    'help_entry': 'string',
                    'auto_help': 'boolean',
                    'arg_regex': 'string',
                    'is_exit': 'boolean',
                    'is_channel': 'boolean'
                }
            },
            {
                'type_code': 'cmdset',
                'type_name': 'CommandSet',
                'typeclass': 'app.models.commands.CmdSet',
                'classname': 'CmdSet',
                'module_path': 'app.models.commands',
                'description': '命令集合类型，用于管理一组相关的命令',
                'schema_definition': {
                    'key': 'string',
                    'mergetype': 'string',
                    'priority': 'integer',
                    'commands': 'object'
                }
            },
            {
                'type_code': 'command_executor',
                'type_name': 'CommandExecutor',
                'typeclass': 'app.models.commands.CommandExecutor',
                'classname': 'CommandExecutor',
                'module_path': 'app.models.commands',
                'description': '命令执行器类型，负责命令的解析和执行',
                'schema_definition': {
                    'max_history': 'integer',
                    'command_separator': 'string',
                    'argument_separator': 'string',
                    'quote_chars': 'array',
                    'show_errors': 'boolean',
                    'log_commands': 'boolean'
                }
            },
            {
                'type_code': 'system_cmdset',
                'type_name': 'SystemCommandSet',
                'typeclass': 'app.models.commands.SystemCmdSet',
                'classname': 'SystemCmdSet',
                'module_path': 'app.models.commands.system',
                'description': '系统命令集合类型，包含基础系统命令',
                'schema_definition': {
                    'key': 'system_cmdset',
                    'mergetype': 'Replace',
                    'priority': 100,
                    'commands': 'object'
                }
            }
        ]
        
        # 插入节点类型定义
        for node_type in command_node_types:
            # 检查是否已存在
            existing = session.execute(
                text("SELECT id FROM node_types WHERE type_code = :type_code"),
                {'type_code': node_type['type_code']}
            ).fetchone()
            
            if existing:
                print(f"  ⚠️  节点类型 {node_type['type_code']} 已存在，跳过")
                continue
            
            # 插入新的节点类型
            result = session.execute(
                text("""
                    INSERT INTO node_types (type_code, type_name, typeclass, classname, module_path, description, schema_definition)
                    VALUES (:type_code, :type_name, :typeclass, :classname, :module_path, :description, :schema_definition)
                    RETURNING id
                """),
                {
                    'type_code': node_type['type_code'],
                    'type_name': node_type['type_name'],
                    'typeclass': node_type['typeclass'],
                    'classname': node_type['classname'],
                    'module_path': node_type['module_path'],
                    'description': node_type['description'],
                    'schema_definition': json.dumps(node_type['schema_definition'])
                }
            )
            
            node_type_id = result.fetchone()[0]
            print(f"  ✅ 创建节点类型 {node_type['type_code']} (ID: {node_type_id})")
        
        session.commit()
        session.close()
        print("  🎉 命令节点类型创建完成")
        return True
        
    except Exception as e:
        print(f"  ❌ 创建命令节点类型失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def migrate_system_commands():
    """迁移系统命令配置到数据库"""
    print("\n🔧 迁移系统命令配置到数据库")
    print("=" * 50)
    
    try:
        from app.core.database import SessionLocal
        from app.commands.system.cmdset import SystemCmdSet
        from app.commands.system.look import CmdLook
        from app.commands.system.stats import CmdStats
        from app.commands.system.help import CmdHelp
        from app.commands.system.version import CmdVersion
        from app.commands.system.time import CmdTime
        from sqlalchemy import text
        
        session = SessionLocal()
        
        # 获取系统命令集合类型ID
        system_cmdset_type = session.execute(
            text("SELECT id FROM node_types WHERE type_code = 'system_cmdset'")
        ).fetchone()
        
        if not system_cmdset_type:
            print("  ❌ 系统命令集合类型不存在，请先创建节点类型")
            return False
        
        system_cmdset_type_id = system_cmdset_type[0]
        
        # 检查是否已存在系统命令集合节点
        existing_system_cmdset = session.execute(
            text("SELECT id FROM nodes WHERE type_code = 'system_cmdset' AND name = 'system_cmdset'")
        ).fetchone()
        
        if existing_system_cmdset:
            print(f"  ⚠️  系统命令集合节点已存在 (ID: {existing_system_cmdset[0]})，跳过创建")
            system_cmdset_id = existing_system_cmdset[0]
        else:
            # 创建系统命令集合节点
            system_cmdset_node = session.execute(
                text("""
                    INSERT INTO nodes (uuid, type_id, type_code, name, description, attributes, tags)
                    VALUES (uuid_generate_v4(), :type_id, 'system_cmdset', :name, :description, :attributes, :tags)
                    RETURNING id, uuid
                """),
                {
                    'type_id': system_cmdset_type_id,
                    'name': 'system_cmdset',
                    'description': '系统命令集合，包含基础系统命令',
                    'attributes': json.dumps({
                        'cmdset_key': 'system_cmdset',
                        'cmdset_mergetype': 'Replace',
                        'cmdset_priority': 100,
                        'cmdset_class': 'SystemCmdSet',
                        'cmdset_module': 'app.commands.system.cmdset',
                        'cmdset_version': '1.0',
                        'cmdset_description': '系统基础命令集合',
                        'cmdset_author': 'AI Assistant',
                        'cmdset_created_at': datetime.now().isoformat()
                    }),
                    'tags': json.dumps(['system', 'commands', 'base', 'default'])
                }
            ).fetchone()
            
            system_cmdset_id = system_cmdset_node[0]
            system_cmdset_uuid = system_cmdset_node[1]
            print(f"  ✅ 创建系统命令集合节点 (ID: {system_cmdset_id}, UUID: {system_cmdset_uuid})")
        
        # 获取命令类型ID
        command_type = session.execute(
            text("SELECT id FROM node_types WHERE type_code = 'command'")
        ).fetchone()
        
        if not command_type:
            print("  ❌ 命令类型不存在，请先创建节点类型")
            return False
        
        command_type_id = command_type[0]
        
        # 系统命令列表
        system_commands = [
            CmdLook,
            CmdStats,
            CmdHelp,
            CmdVersion,
            CmdTime
        ]
        
        migrated_commands = []
        
        for cmd_class in system_commands:
            try:
                # 创建命令实例获取配置
                cmd_instance = cmd_class()
                
                # 检查命令是否已存在
                existing_command = session.execute(
                    text("SELECT id FROM nodes WHERE type_code = 'command' AND name = :name"),
                    {'name': cmd_instance.key}
                ).fetchone()
                
                if existing_command:
                    print(f"    ⚠️  命令 {cmd_instance.key} 已存在 (ID: {existing_command[0]})，跳过创建")
                    command_id = existing_command[0]
                    migrated_commands.append({
                        'id': command_id,
                        'key': cmd_instance.key,
                        'class': cmd_instance.__class__.__name__
                    })
                    continue
                
                # 创建命令节点
                command_node = session.execute(
                    text("""
                        INSERT INTO nodes (uuid, type_id, type_code, name, description, attributes, tags)
                        VALUES (uuid_generate_v4(), :type_id, 'command', :name, :description, :attributes, :tags)
                        RETURNING id, uuid
                    """),
                    {
                        'type_id': command_type_id,
                        'name': cmd_instance.key,
                        'description': cmd_instance.help_entry or f"执行 {cmd_instance.key} 命令",
                        'attributes': json.dumps({
                            'command_key': cmd_instance.key,
                            'command_aliases': cmd_instance.aliases,
                            'command_locks': cmd_instance.locks,
                            'help_category': cmd_instance.help_category,
                            'help_entry': cmd_instance.help_entry,
                            'auto_help': cmd_instance.auto_help,
                            'arg_regex': cmd_instance.arg_regex,
                            'is_exit': cmd_instance.is_exit,
                            'is_channel': cmd_instance.is_channel,
                            'command_class': cmd_instance.__class__.__name__,
                            'command_module': cmd_instance.__class__.__module__,
                            'command_version': '1.0',
                            'command_description': cmd_instance.help_entry or f"执行 {cmd_instance.key} 命令",
                            'command_author': 'AI Assistant',
                            'command_created_at': datetime.now().isoformat()
                        }),
                        'tags': json.dumps([cmd_instance.key, 'command', cmd_instance.help_category])
                    }
                ).fetchone()
                
                command_id = command_node[0]
                command_uuid = command_node[1]
                
                print(f"    ✅ 迁移命令 {cmd_instance.key} (ID: {command_id}, UUID: {command_uuid})")
                migrated_commands.append({
                    'id': command_id,
                    'uuid': command_uuid,
                    'key': cmd_instance.key,
                    'class': cmd_instance.__class__.__name__
                })
                
            except Exception as e:
                print(f"    ❌ 迁移命令 {cmd_class.__name__} 失败: {e}")
                # 如果是事务错误，回滚并重试
                if "InFailedSqlTransaction" in str(e):
                    session.rollback()
                    print(f"    🔄 回滚事务，重试命令 {cmd_class.__name__}")
                    try:
                        # 重新创建命令实例
                        cmd_instance = cmd_class()
                        
                        # 重新创建命令节点
                        command_node = session.execute(
                            text("""
                                INSERT INTO nodes (uuid, type_id, type_code, name, description, attributes, tags)
                                VALUES (uuid_generate_v4(), :type_id, 'command', :name, :description, :attributes, :tags)
                                RETURNING id, uuid
                            """),
                            {
                                'type_id': command_type_id,
                                'name': cmd_instance.key,
                                'description': cmd_instance.help_entry or f"执行 {cmd_instance.key} 命令",
                                'attributes': json.dumps({
                                    'command_key': cmd_instance.key,
                                    'command_aliases': cmd_instance.aliases,
                                    'command_locks': cmd_instance.locks,
                                    'help_category': cmd_instance.help_category,
                                    'help_entry': cmd_instance.help_entry,
                                    'auto_help': cmd_instance.auto_help,
                                    'arg_regex': cmd_instance.arg_regex,
                                    'is_exit': cmd_instance.is_exit,
                                    'is_channel': cmd_instance.is_channel,
                                    'command_class': cmd_instance.__class__.__name__,
                                    'command_module': cmd_instance.__class__.__module__,
                                    'command_version': '1.0',
                                    'command_description': cmd_instance.help_entry or f"执行 {cmd_instance.key} 命令",
                                    'command_author': 'AI Assistant',
                                    'command_created_at': datetime.now().isoformat()
                                }),
                                'tags': json.dumps([cmd_instance.key, 'command', cmd_instance.help_category])
                            }
                        ).fetchone()
                        
                        command_id = command_node[0]
                        command_uuid = command_node[1]
                        
                        print(f"    ✅ 重试成功: 迁移命令 {cmd_instance.key} (ID: {command_id}, UUID: {command_uuid})")
                        migrated_commands.append({
                            'id': command_id,
                            'uuid': command_uuid,
                            'key': cmd_instance.key,
                            'class': cmd_instance.__class__.__name__
                        })
                        
                    except Exception as retry_e:
                        print(f"    ❌ 重试失败: 迁移命令 {cmd_class.__name__} 失败: {retry_e}")
                        continue
                else:
                    continue
        
        # 建立命令与命令集合的关系
        for command_info in migrated_commands:
            # 检查关系是否已存在
            existing_relationship = session.execute(
                text("""
                    SELECT id FROM relationships 
                    WHERE source_id = :source_id AND target_id = :target_id AND type_code = 'contains'
                """),
                {
                    'source_id': system_cmdset_id,
                    'target_id': command_info['id']
                }
            ).fetchone()
            
            if existing_relationship:
                print(f"    ⚠️  关系已存在: system_cmdset -> {command_info['key']}")
                continue
            
            session.execute(
                text("""
                    INSERT INTO relationships (uuid, type_id, type_code, source_id, target_id, attributes)
                    VALUES (uuid_generate_v4(), 
                           (SELECT id FROM relationship_types WHERE type_code = 'contains' LIMIT 1),
                           'contains',
                           :source_id, :target_id, :attributes)
                """),
                {
                    'source_id': system_cmdset_id,
                    'target_id': command_info['id'],
                    'attributes': json.dumps({
                        'relationship_type': 'contains',
                        'command_key': command_info['key'],
                        'command_class': command_info['class'],
                        'relationship_created_at': datetime.now().isoformat()
                    })
                }
            )
            print(f"    🔗 建立关系: system_cmdset -> {command_info['key']}")
        
        # 更新系统命令集合节点的命令列表
        command_list = {cmd['key']: cmd['class'] for cmd in migrated_commands}
        session.execute(
            text("""
                UPDATE nodes 
                SET attributes = jsonb_set(attributes, '{cmdset_commands}', :commands),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :node_id
            """),
            {
                'commands': json.dumps(command_list),
                'node_id': system_cmdset_id
            }
        )
        print(f"    📝 更新系统命令集合的命令列表: {len(command_list)} 个命令")
        
        session.commit()
        session.close()
        
        print(f"  🎉 系统命令迁移完成，共迁移 {len(migrated_commands)} 个命令")
        return True
        
    except Exception as e:
        print(f"  ❌ 迁移系统命令失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_relationship_types():
    """创建命令相关的关系类型定义"""
    print("\n🔧 创建命令相关的关系类型定义")
    print("=" * 50)
    
    try:
        from app.core.database import SessionLocal
        from sqlalchemy import text
        
        session = SessionLocal()
        
        # 命令相关的关系类型定义
        command_relationship_types = [
            {
                'type_code': 'contains',
                'type_name': 'Contains',
                'typeclass': 'app.models.relationships.ContainsRelationship',
                'description': '包含关系，表示命令集合包含命令',
                'schema_definition': {
                    'relationship_type': 'string',
                    'command_key': 'string',
                    'command_class': 'string'
                },
                'is_directed': True,
                'is_symmetric': False,
                'is_transitive': False
            },
            {
                'type_code': 'inherits',
                'type_name': 'Inherits',
                'typeclass': 'app.models.relationships.InheritsRelationship',
                'description': '继承关系，表示命令集合之间的继承',
                'schema_definition': {
                    'relationship_type': 'string',
                    'priority': 'integer'
                },
                'is_directed': True,
                'is_symmetric': False,
                'is_transitive': True
            },
            {
                'type_code': 'executes',
                'type_name': 'Executes',
                'typeclass': 'app.models.relationships.ExecutesRelationship',
                'description': '执行关系，表示执行器执行命令',
                'schema_definition': {
                    'relationship_type': 'string',
                    'execution_time': 'timestamp',
                    'success': 'boolean'
                },
                'is_directed': True,
                'is_symmetric': False,
                'is_transitive': False
            }
        ]
        
        # 插入关系类型定义
        for rel_type in command_relationship_types:
            # 检查是否已存在
            existing = session.execute(
                text("SELECT id FROM relationship_types WHERE type_code = :type_code"),
                {'type_code': rel_type['type_code']}
            ).fetchone()
            
            if existing:
                print(f"  ⚠️  关系类型 {rel_type['type_code']} 已存在，跳过")
                continue
            
            # 插入新的关系类型
            result = session.execute(
                text("""
                    INSERT INTO relationship_types (type_code, type_name, typeclass, description, schema_definition, is_directed, is_symmetric, is_transitive)
                    VALUES (:type_code, :type_name, :typeclass, :description, :schema_definition, :is_directed, :is_symmetric, :is_transitive)
                    RETURNING id
                """),
                {
                    'type_code': rel_type['type_code'],
                    'type_name': rel_type['type_name'],
                    'typeclass': rel_type['typeclass'],
                    'description': rel_type['description'],
                    'schema_definition': json.dumps(rel_type['schema_definition']),
                    'is_directed': rel_type['is_directed'],
                    'is_symmetric': rel_type['is_symmetric'],
                    'is_transitive': rel_type['is_transitive']
                }
            )
            
            rel_type_id = result.fetchone()[0]
            print(f"  ✅ 创建关系类型 {rel_type['type_code']} (ID: {rel_type_id})")
        
        session.commit()
        session.close()
        print("  🎉 命令关系类型创建完成")
        return True
        
    except Exception as e:
        print(f"  ❌ 创建命令关系类型失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_migration():
    """验证迁移结果"""
    print("\n🔍 验证迁移结果")
    print("=" * 50)
    
    try:
        from app.core.database import SessionLocal
        from sqlalchemy import text
        
        session = SessionLocal()
        
        # 检查节点类型
        node_types = session.execute(
            text("SELECT type_code, type_name FROM node_types WHERE type_code IN ('command', 'cmdset', 'command_executor', 'system_cmdset')")
        ).fetchall()
        
        print("  📊 节点类型统计:")
        for node_type in node_types:
            print(f"    - {node_type[0]}: {node_type[1]}")
        
        # 检查命令节点
        command_nodes = session.execute(
            text("SELECT n.name, n.attributes FROM nodes n JOIN node_types nt ON n.type_id = nt.id WHERE nt.type_code = 'command'")
        ).fetchall()
        
        print(f"  📊 命令节点统计: {len(command_nodes)} 个")
        for cmd_node in command_nodes:
            # 处理attributes，可能是字符串或字典
            attrs = cmd_node[1]
            if isinstance(attrs, str):
                attrs = json.loads(attrs)
            elif not isinstance(attrs, dict):
                attrs = {}
            
            print(f"    - {cmd_node[0]}: {attrs.get('help_category', 'unknown')}")
        
        # 检查命令集合节点
        cmdset_nodes = session.execute(
            text("SELECT n.name, n.attributes FROM nodes n JOIN node_types nt ON n.type_id = nt.id WHERE nt.type_code = 'cmdset'")
        ).fetchall()
        
        print(f"  📊 命令集合节点统计: {len(cmdset_nodes)} 个")
        for cmdset_node in cmdset_nodes:
            print(f"    - {cmdset_node[0]}")
        
        # 检查关系
        relationships = session.execute(
            text("SELECT r.type_code, COUNT(*) FROM relationships r GROUP BY r.type_code")
        ).fetchall()
        
        print("  📊 关系统计:")
        for rel in relationships:
            print(f"    - {rel[0]}: {rel[1]} 个")
        
        session.close()
        print("  🎉 迁移验证完成")
        return True
        
    except Exception as e:
        print(f"  ❌ 迁移验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_migration():
    """运行完整的迁移流程"""
    print("🚀 开始命令系统数据迁移")
    print("=" * 60)
    
    migration_steps = [
        ("创建命令节点类型", create_command_node_types),
        ("创建命令关系类型", create_relationship_types),
        ("迁移系统命令配置", migrate_system_commands),
        ("验证迁移结果", verify_migration)
    ]
    
    success_count = 0
    total_steps = len(migration_steps)
    
    for step_name, step_func in migration_steps:
        print(f"\n📋 执行步骤: {step_name}")
        print("-" * 40)
        
        if step_func():
            success_count += 1
            print(f"✅ {step_name} 执行成功")
        else:
            print(f"❌ {step_name} 执行失败")
            # 可以选择继续或中断
            # break
    
    print("\n" + "=" * 60)
    print("📊 迁移结果汇总")
    print("=" * 60)
    print(f"总计步骤: {total_steps}")
    print(f"成功步骤: {success_count}")
    print(f"失败步骤: {total_steps - success_count}")
    print(f"成功率: {success_count/total_steps*100:.1f}%")
    
    if success_count == total_steps:
        print("\n🎉 命令系统数据迁移完成！")
        return True
    else:
        print(f"\n⚠️  有 {total_steps - success_count} 个步骤失败，请检查相关错误")
        return False

if __name__ == "__main__":
    try:
        success = run_migration()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  迁移被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 迁移过程中发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
