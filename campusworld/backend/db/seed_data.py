"""
数据库种子数据初始化（幂等）

目标：
- 让 `python -m db.init_database` 在开发环境能一键可用
- 避免依赖手工执行多个 scripts/* 来创建必要类型/默认账号/根节点

说明：
- 这里的 seed 只负责“最小可运行集”：
  - 必要 NodeType（account、room）
  - 默认账号（admin/dev/campus）
  - 根节点（Singularity Room）
"""

from __future__ import annotations

from app.core.log import get_logger

logger = get_logger("campusworld.db.seed")


def ensure_account_type(session) -> bool:
    """确保 account 类型存在。"""
    from app.models.graph import NodeType

    existing = session.query(NodeType).filter(NodeType.type_code == "account").first()
    if existing:
        return True

    # 复用现有脚本里的 schema_definition 语义（最小集合）
    node_type = NodeType(
        type_code="account",
        type_name="账号",
        typeclass="app.models.accounts.DefaultAccount",
        classname="DefaultAccount",
        module_path="app.models.accounts",
        description="用户账号类型，支持管理员、开发者和普通用户",
        schema_definition={
            "username": {"type": "string", "required": True},
            "email": {"type": "string", "required": True},
            "hashed_password": {"type": "string", "required": True},
            "roles": {"type": "array", "default": ["user"]},
            "permissions": {"type": "array", "default": []},
            "access_level": {"type": "string", "default": "normal"},
        },
        is_active=True,
    )
    session.add(node_type)
    session.commit()
    return True


def ensure_root_node(session=None) -> bool:
    """确保根节点存在（奇点房间）。"""
    from app.models.root_manager import root_manager

    return root_manager.ensure_root_node_exists()


def ensure_default_accounts(session) -> bool:
    """创建默认账号（admin/dev/campus），幂等。"""
    import uuid
    from datetime import datetime

    from app.core.security import get_password_hash
    from app.models.accounts import AdminAccount, DeveloperAccount, CampusUserAccount
    from app.models.graph import Node, NodeType

    # account 类型必须已存在
    account_type = session.query(NodeType).filter(NodeType.type_code == "account").first()
    if not account_type:
        return False

    # 若任何默认账号已存在，则跳过创建（保持幂等）
    existing = (
        session.query(Node)
        .filter(Node.type_code == "account")
        .filter(Node.name.in_(["admin", "dev", "campus"]))
        .all()
    )
    if existing:
        return True

    def _attrs(obj) -> dict:
        attrs = dict(obj._node_attributes or {})
        for k, v in list(attrs.items()):
            if isinstance(v, datetime):
                attrs[k] = v.isoformat()
        return attrs

    admin = AdminAccount(
        username="admin",
        email="admin@campusworld.com",
        hashed_password=get_password_hash("admin123"),
        description="系统管理员账号，拥有所有管理权限",
        created_by="system",
    )
    dev = DeveloperAccount(
        username="dev",
        email="dev@campusworld.com",
        hashed_password=get_password_hash("dev123"),
        description="开发者账号，拥有开发和调试权限",
        created_by="admin",
    )
    campus = CampusUserAccount(
        username="campus",
        email="campus@campusworld.com",
        hashed_password=get_password_hash("campus123"),
        description="校园用户账号，用于测试校园功能",
        created_by="admin",
    )

    nodes = [
        Node(
            uuid=uuid.uuid4(),
            type_id=account_type.id,
            type_code="account",
            name="admin",
            description="系统管理员账号，拥有所有管理权限",
            is_active=True,
            is_public=False,
            access_level="admin",
            attributes=_attrs(admin),
            tags=["system", "admin", "default"],
        ),
        Node(
            uuid=uuid.uuid4(),
            type_id=account_type.id,
            type_code="account",
            name="dev",
            description="开发者账号，拥有开发和调试权限",
            is_active=True,
            is_public=False,
            access_level="developer",
            attributes=_attrs(dev),
            tags=["system", "dev", "default"],
        ),
        Node(
            uuid=uuid.uuid4(),
            type_id=account_type.id,
            type_code="account",
            name="campus",
            description="校园用户账号，用于测试校园功能",
            is_active=True,
            is_public=True,
            access_level="normal",
            attributes=_attrs(campus),
            tags=["system", "user", "campus", "default"],
        ),
    ]

    session.add_all(nodes)
    session.commit()
    return True


def seed_minimal() -> bool:
    """
    执行最小种子数据初始化（幂等）。
    """
    try:
        from app.core.database import get_db_session

        with get_db_session() as session:
            if not ensure_account_type(session):
                return False
            if not ensure_default_accounts(session):
                return False

        # 根节点初始化同样是幂等的
        if not ensure_root_node():
            return False

        logger.info("seed_minimal completed")
        return True
    except Exception as e:
        logger.error(f"seed_minimal failed: {e}")
        return False

