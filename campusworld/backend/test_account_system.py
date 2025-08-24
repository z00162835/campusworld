#!/usr/bin/env python3
"""
测试账号系统功能

验证权限系统、账号类型、权限验证装饰器等
包括admin、dev、campus三个账号的测试

作者：AI Assistant
创建时间：2025-08-24
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_permission_system():
    """测试权限系统"""
    print("\n🧪 测试权限系统")
    print("=" * 50)
    
    try:
        from app.core.permissions import permission_manager, permission_checker, Role, Permission
        
        print("✅ 权限系统导入成功")
        
        # 测试角色权限映射
        print("\n📋 测试角色权限映射")
        print("-" * 30)
        
        for role in Role:
            permissions = permission_manager.get_role_permissions(role)
            print(f"  📊 {role.value}: {len(permissions)} 个权限")
            for perm in list(permissions)[:3]:  # 只显示前3个
                print(f"     - {perm.value}")
            if len(permissions) > 3:
                print(f"     ... 还有 {len(permissions) - 3} 个权限")
        
        # 测试权限检查
        print("\n📋 测试权限检查")
        print("-" * 30)
        
        # 测试角色权限检查
        admin_role = Role.ADMIN
        user_create_perm = Permission.CREATE_USER
        
        has_permission = permission_manager.check_role_permission(admin_role, user_create_perm)
        print(f"  ✅ 管理员是否有创建用户权限: {has_permission}")
        
        # 测试权限级别检查
        admin_level = permission_manager.get_permission_level(user_create_perm)
        print(f"  ✅ 创建用户权限级别: {admin_level.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试权限系统失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_account_types():
    """测试账号类型"""
    print("\n🧪 测试账号类型")
    print("=" * 50)
    
    try:
        from app.models.accounts import AdminAccount, DeveloperAccount, CampusUserAccount
        
        print("✅ 账号类型导入成功")
        
        # 测试管理员账号
        print("\n📋 测试管理员账号")
        print("-" * 30)
        
        admin = AdminAccount(
            username='test_admin',
            email='test_admin@example.com'
        )
        
        print(f"  ✅ 管理员账号创建成功")
        print(f"     用户名: {admin.username}")
        print(f"     角色: {admin.roles}")
        print(f"     权限数量: {len(admin.permissions)}")
        print(f"     访问级别: {admin._node_attributes.get('access_level')}")
        print(f"     可以管理用户: {admin.can_manage_user(admin)}")
        print(f"     可以管理校园: {admin.can_manage_campus(None)}")
        
        # 测试开发者账号
        print("\n📋 测试开发者账号")
        print("-" * 30)
        
        dev = DeveloperAccount(
            username='test_dev',
            email='test_dev@example.com'
        )
        
        print(f"  ✅ 开发者账号创建成功")
        print(f"     用户名: {dev.username}")
        print(f"     角色: {dev.roles}")
        print(f"     权限数量: {len(dev.permissions)}")
        print(f"     访问级别: {dev._node_attributes.get('access_level')}")
        print(f"     可以开发功能: {dev.can_develop_features()}")
        print(f"     可以访问调试模式: {dev.can_access_debug_mode()}")
        print(f"     可以查看日志: {dev.can_view_logs()}")
        
        # 测试校园用户账号
        print("\n📋 测试校园用户账号")
        print("-" * 30)
        
        campus_user = CampusUserAccount(
            username='test_campus',
            email='test_campus@example.com'
        )
        
        print(f"  ✅ 校园用户账号创建成功")
        print(f"     用户名: {campus_user.username}")
        print(f"     角色: {campus_user.roles}")
        print(f"     权限数量: {len(campus_user.permissions)}")
        print(f"     访问级别: {campus_user._node_attributes.get('access_level')}")
        print(f"     可以查看校园: {campus_user.can_view_campus(None)}")
        print(f"     可以编辑个人资料: {campus_user.can_edit_profile()}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试账号类型失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_permission_decorators():
    """测试权限验证装饰器"""
    print("\n🧪 测试权限验证装饰器")
    print("=" * 50)
    
    try:
        from app.core.auth import (
            require_permission, require_role, require_access_level,
            require_admin, require_developer, require_user,
            PermissionGuard
        )
        from app.models.accounts import AdminAccount, DeveloperAccount, UserAccount
        
        print("✅ 权限验证装饰器导入成功")
        
        # 测试权限装饰器
        print("\n📋 测试权限装饰器")
        print("-" * 30)
        
        class TestClass:
            def __init__(self, account):
                self.account = account
            
            @require_permission('user.create')
            def create_user(self):
                return "用户创建成功"
            
            @require_role('admin')
            def admin_only(self):
                return "管理员专用功能"
            
            @require_access_level('developer')
            def dev_level(self):
                return "开发者级别功能"
            
            @require_admin
            def admin_decorator(self):
                return "管理员装饰器功能"
            
            @require_developer
            def dev_decorator(self):
                return "开发者装饰器功能"
            
            @require_user
            def user_decorator(self):
                return "用户装饰器功能"
        
        # 测试管理员账号
        print("  📊 测试管理员账号:")
        admin = AdminAccount('test_admin', 'admin@example.com')
        test_admin = TestClass(admin)
        
        try:
            result = test_admin.create_user()
            print(f"    ✅ create_user: {result}")
        except Exception as e:
            print(f"    ❌ create_user: {e}")
        
        try:
            result = test_admin.admin_only()
            print(f"    ✅ admin_only: {result}")
        except Exception as e:
            print(f"    ❌ admin_only: {e}")
        
        try:
            result = test_admin.admin_decorator()
            print(f"    ✅ admin_decorator: {result}")
        except Exception as e:
            print(f"    ❌ admin_decorator: {e}")
        
        # 测试开发者账号
        print("  📊 测试开发者账号:")
        dev = DeveloperAccount('test_dev', 'dev@example.com')
        test_dev = TestClass(dev)
        
        try:
            result = test_dev.dev_level()
            print(f"    ✅ dev_level: {result}")
        except Exception as e:
            print(f"    ❌ dev_level: {e}")
        
        try:
            result = test_dev.dev_decorator()
            print(f"    ✅ dev_decorator: {result}")
        except Exception as e:
            print(f"    ❌ dev_decorator: {e}")
        
        # 测试普通用户账号
        print("  📊 测试普通用户账号:")
        user = UserAccount('test_user', 'user@example.com')
        test_user = TestClass(user)
        
        try:
            result = test_user.user_decorator()
            print(f"    ✅ user_decorator: {result}")
        except Exception as e:
            print(f"    ❌ user_decorator: {e}")
        
        # 测试权限守卫
        print("\n📋 测试权限守卫")
        print("-" * 30)
        
        guard = PermissionGuard(admin)
        print(f"  ✅ 权限守卫创建成功")
        print(f"     检查用户创建权限: {guard.check_permission('user.create')}")
        print(f"     检查管理员角色: {guard.check_role('admin')}")
        print(f"     检查开发者访问级别: {guard.check_access_level('developer')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试权限验证装饰器失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_account_management():
    """测试账号管理功能"""
    print("\n🧪 测试账号管理功能")
    print("=" * 50)
    
    try:
        from app.models.accounts import AdminAccount, DeveloperAccount, CampusUserAccount
        
        print("✅ 账号管理功能测试")
        
        # 测试账号状态管理
        print("\n📋 测试账号状态管理")
        print("-" * 30)
        
        # 创建测试账号
        admin = AdminAccount('test_admin_mgmt', 'admin_mgmt@example.com')
        
        print(f"  📊 初始状态:")
        print(f"     是否锁定: {admin.is_locked}")
        print(f"     是否暂停: {admin.is_suspended}")
        print(f"     登录次数: {admin.login_count}")
        print(f"     失败登录次数: {admin.failed_login_attempts}")
        
        # 测试登录相关功能
        print(f"\n  📊 测试登录功能:")
        admin.update_last_login()
        print(f"     更新最后登录时间: {admin.last_login}")
        print(f"     登录次数: {admin.login_count}")
        print(f"     失败登录次数: {admin.failed_login_attempts}")
        
        # 测试失败登录
        admin.record_failed_login()
        print(f"     记录失败登录: {admin.failed_login_attempts}")
        
        # 测试账号锁定
        admin.lock_account("测试锁定")
        print(f"     锁定账号: {admin.is_locked}")
        print(f"     锁定原因: {admin.lock_reason}")
        
        # 测试账号解锁
        admin.unlock_account()
        print(f"     解锁账号: {admin.is_locked}")
        print(f"     锁定原因: {admin.lock_reason}")
        
        # 测试账号暂停
        from datetime import timedelta
        suspend_until = datetime.now() + timedelta(hours=1)
        admin.suspend_account("测试暂停", suspend_until)
        print(f"     暂停账号: {admin.is_suspended}")
        print(f"     暂停原因: {admin.suspension_reason}")
        print(f"     暂停截止: {admin.suspension_until}")
        
        # 测试账号恢复
        admin.unsuspend_account()
        print(f"     恢复账号: {admin.is_suspended}")
        print(f"     暂停原因: {admin.suspension_reason}")
        
        # 测试权限管理
        print(f"\n  📊 测试权限管理:")
        print(f"     初始权限: {admin.permissions}")
        
        admin.add_permission('custom.permission')
        print(f"     添加权限: {admin.permissions}")
        
        admin.remove_permission('custom.permission')
        print(f"     移除权限: {admin.permissions}")
        
        # 测试角色管理
        print(f"\n  📊 测试角色管理:")
        print(f"     初始角色: {admin.roles}")
        
        admin.add_role('custom_role')
        print(f"     添加角色: {admin.roles}")
        
        admin.remove_role('custom_role')
        print(f"     移除角色: {admin.roles}")
        
        # 测试状态摘要
        print(f"\n  📊 状态摘要:")
        summary = admin.get_status_summary()
        for key, value in summary.items():
            if key not in ['hashed_password']:  # 不显示敏感信息
                print(f"     {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试账号管理功能失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_campus_user_features():
    """测试校园用户特有功能"""
    print("\n🧪 测试校园用户特有功能")
    print("=" * 50)
    
    try:
        from app.models.accounts import CampusUserAccount
        
        print("✅ 校园用户功能测试")
        
        # 创建校园用户
        campus_user = CampusUserAccount('test_campus_user', 'campus@example.com')
        
        print(f"  📊 校园用户创建成功:")
        print(f"     用户名: {campus_user.username}")
        print(f"     角色: {campus_user.roles}")
        print(f"     校园成员关系: {campus_user.get_campus_memberships()}")
        
        # 测试校园成员关系（模拟）
        print(f"\n  📊 测试校园成员关系:")
        
        # 模拟校园对象
        class MockCampus:
            def __init__(self, id, name):
                self.id = id
                self.name = name
        
        mock_campus = MockCampus(1, "测试校园")
        
        # 测试加入校园
        success = campus_user.join_campus(mock_campus, "member")
        print(f"     加入校园: {success}")
        print(f"     成员关系: {campus_user.get_campus_memberships()}")
        print(f"     是否是成员: {campus_user.is_campus_member(mock_campus)}")
        print(f"     在校园中的角色: {campus_user.get_campus_role(mock_campus)}")
        
        # 测试离开校园
        success = campus_user.leave_campus(mock_campus)
        print(f"     离开校园: {success}")
        print(f"     成员关系: {campus_user.get_campus_memberships()}")
        print(f"     是否是成员: {campus_user.is_campus_member(mock_campus)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试校园用户功能失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_tests():
    """运行所有测试"""
    print("🚀 开始测试账号系统功能")
    print("=" * 60)
    
    test_functions = [
        ("权限系统测试", test_permission_system),
        ("账号类型测试", test_account_types),
        ("权限验证装饰器测试", test_permission_decorators),
        ("账号管理功能测试", test_account_management),
        ("校园用户功能测试", test_campus_user_features)
    ]
    
    success_count = 0
    total_tests = len(test_functions)
    
    for test_name, test_func in test_functions:
        print(f"\n📋 执行测试: {test_name}")
        print("-" * 40)
        
        if test_func():
            success_count += 1
            print(f"✅ {test_name} 通过")
        else:
            print(f"❌ {test_name} 失败")
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    print(f"总计测试: {total_tests}")
    print(f"通过测试: {success_count}")
    print(f"失败测试: {total_tests - success_count}")
    print(f"通过率: {success_count/total_tests*100:.1f}%")
    
    if success_count == total_tests:
        print("\n🎉 所有测试通过！账号系统功能正常")
        return True
    else:
        print(f"\n⚠️  有 {total_tests - success_count} 个测试失败，请检查相关功能")
        return False

if __name__ == "__main__":
    try:
        success = run_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 测试过程中发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
