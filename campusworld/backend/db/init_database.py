#!/usr/bin/env python3
"""
数据库初始化 / 迁移 / 危险重建

默认（无子命令或与 migrate 等价）：
  connect → create_all → ensure_* 补丁迁移 → 可选种子数据

reset（仅 PostgreSQL，且需环境门闸 + --i-understand）：
  DROP SCHEMA public CASCADE → CREATE SCHEMA → 再执行与 migrate 相同后续步骤
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _bootstrap_path() -> Path:
    current_dir = Path(__file__).parent.absolute()
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    return current_dir


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CampusWorld database: migrate (default) or destructive reset (PostgreSQL only).",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="migrate",
        choices=["migrate", "reset"],
        help="migrate: create_all + schema patches + optional seed (default). "
        "reset: drop public schema then migrate (PostgreSQL only, guarded).",
    )
    parser.add_argument(
        "--i-understand",
        dest="i_understand",
        action="store_true",
        help="Required for reset: acknowledge total loss of data in public schema.",
    )
    parser.add_argument(
        "--json-report",
        action="store_true",
        help="Print per-step migration results as JSON.",
    )
    return parser.parse_args(argv)


def _run_seed_if_enabled(schema_ok: bool) -> bool:
    try:
        from app.core.config_manager import get_setting

        seed_enabled = bool(get_setting("development.seed_data", False))
        env_override = os.getenv("CAMPUSWORLD_DEVELOPMENT_SEED_DATA")
        if env_override is not None:
            seed_enabled = env_override.lower() == "true"

        if not seed_enabled:
            return True
        if not schema_ok:
            print("⚠️  种子数据跳过：schema 迁移未全部成功")
            return True
        print("🌱 开始初始化种子数据（development.seed_data=true）...")
        from db.seed_data import seed_minimal

        if seed_minimal():
            print("✅ 种子数据初始化完成")
            return True
        print("❌ 种子数据初始化失败")
        return False
    except Exception as e:
        print(f"⚠️  种子数据阶段跳过/失败: {e}")
        return True


def _run_migrate(engine, *, json_report: bool) -> tuple[bool, list]:
    from app.core.database import init_db
    from db.migrate_report import (
        format_migration_report,
        is_postgresql_engine,
        migrations_all_ok,
        run_schema_migrations,
    )
    from db.schema_migrations import SchemaMigrationError, ensure_required_extensions

    if is_postgresql_engine(engine):
        print("确保 PostgreSQL 扩展（postgis、vector 等，create_all 依赖 geometry/vector 类型）…")
        try:
            ensure_required_extensions(engine)
        except SchemaMigrationError as e:
            print(f"❌ 扩展检查失败: {e}")
            return False, []
        print("✅ PostgreSQL 扩展就绪")

    print("初始化数据库表（create_all）...")
    if not init_db():
        print("❌ create_all 失败")
        return False, []
    print("✅ create_all 完成")

    results = run_schema_migrations(engine)
    print(format_migration_report(results, as_json=json_report))
    schema_ok = migrations_all_ok(results)
    if schema_ok:
        print("✅ schema 兼容迁移全部成功")
    else:
        print("❌ schema 兼容迁移存在失败步骤（见报表），退出码非 0")
    return schema_ok, results


def _cmd_reset(engine, args: argparse.Namespace) -> bool:
    from db.migrate_report import (
        database_target_summary,
        is_postgresql_engine,
        reset_explicitly_allowed,
        reset_public_schema,
    )

    if not reset_explicitly_allowed():
        print(
            "❌ reset 被拒绝：请设置环境变量 CAMPUSWORLD_ALLOW_DB_RESET=true "
            "或在配置中 development.allow_db_reset: true"
        )
        return False
    if not args.i_understand:
        print("❌ reset 必须传入 --i-understand 以确认将销毁 public schema 内全部数据")
        return False
    if not is_postgresql_engine(engine):
        print("❌ reset 仅支持 PostgreSQL（当前 database URL 非 postgresql）")
        return False

    print(f"⚠️  目标库：{database_target_summary(engine)}")
    print("⚠️  即将执行 DROP SCHEMA public CASCADE …")
    try:
        reset_public_schema(engine)
        print("✅ public schema 已重建")
    except Exception as e:
        print(f"❌ reset 执行失败: {e}")
        import traceback

        traceback.print_exc()
        return False

    schema_ok, _ = _run_migrate(engine, json_report=args.json_report)
    if not schema_ok:
        return False
    return _run_seed_if_enabled(schema_ok)


def _cmd_migrate(engine, args: argparse.Namespace) -> bool:
    schema_ok, _ = _run_migrate(engine, json_report=args.json_report)
    if not schema_ok:
        return False
    return _run_seed_if_enabled(schema_ok)


def main(argv: list[str] | None = None) -> bool:
    args = _parse_args(argv)
    _bootstrap_path()
    print("🔍 数据库工具：command=%s" % args.command)

    try:
        import sqlalchemy

        print(f"✅ SQLAlchemy: {sqlalchemy.__version__}")
    except ImportError as e:
        print(f"❌ SQLAlchemy 导入失败: {e}")
        return False

    try:
        import psycopg2  # noqa: F401
    except ImportError as e:
        print(f"❌ psycopg2 导入失败: {e}")
        return False

    try:
        import app.models  # noqa: F401
        import app.commands.policy_store  # noqa: F401

        from app.core.database import engine
        from db.migrate_report import database_target_summary
    except ImportError as e:
        print(f"❌ 数据库模块导入失败: {e}")
        return False

    try:
        print("检查数据库连接…")
        print(f"目标：{database_target_summary(engine)}")
        with engine.connect() as conn:
            print("✅ 数据库连接成功")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

    if args.command == "reset":
        return _cmd_reset(engine, args)
    return _cmd_migrate(engine, args)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
