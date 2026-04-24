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

from copy import deepcopy

from app.constants.data_access_defaults import (
    ADMIN_DATA_ACCESS,
    DEV_DATA_ACCESS,
    USER_LIKE_DATA_ACCESS,
)
from app.core.log import get_logger
from sqlalchemy import text

logger = get_logger("campusworld.db.seed")


def ensure_content_visibility_seed(session) -> bool:
    """
    Idempotent data seed for content visibility semantics.
    """
    from app.models.graph import Node

    # Ability nodes are semantic capabilities, not room contents.
    session.query(Node).filter(
        Node.type_code == "system_command_ability",
        Node.is_active == True,  # noqa: E712
    ).update(
        {
            Node.attributes: Node.attributes.op("||")(
                text("'{\"entity_kind\":\"ability\",\"presentation_domains\":[\"help\",\"npc\"],\"access_locks\":{\"view\":\"all()\",\"invoke\":\"all()\"}}'::jsonb")  # noqa: E501
            )
        },
        synchronize_session=False,
    )

    # Bulletin board is a visible room object.
    session.query(Node).filter(
        Node.type_code == "system_bulletin_board",
        Node.is_active == True,  # noqa: E712
    ).update(
        {
            Node.attributes: Node.attributes.op("||")(
                text("'{\"entity_kind\":\"item\",\"presentation_domains\":[\"room\"],\"access_locks\":{\"view\":\"all()\",\"interact\":\"all()\"}}'::jsonb")
            )
        },
        synchronize_session=False,
    )
    session.commit()
    return True


def ensure_command_policies_seed(session) -> bool:
    """
    Ensure minimal command policy rows exist (idempotent).

    This seeds data only (DML). Schema must already exist.
    """
    from app.commands.base import CommandType
    from app.commands.policy_bootstrap import policy_seed_for
    from app.commands.policy_store import CommandPolicyRepository
    from app.commands.agent_commands import get_agent_commands
    from app.commands.graph_inspect_commands import GRAPH_INSPECT_COMMANDS
    from app.commands.system_commands import SYSTEM_COMMANDS
    from app.commands.system_primer_command import PRIMER_COMMANDS
    from app.commands.game import GAME_COMMANDS
    from app.commands.builder import get_build_cmdset

    repo = CommandPolicyRepository(session)
    commands = (
        list(SYSTEM_COMMANDS)
        + list(PRIMER_COMMANDS)
        + list(GRAPH_INSPECT_COMMANDS)
        + list(GAME_COMMANDS)
        + list(get_agent_commands())
    )
    build_cmdset = get_build_cmdset()
    if build_cmdset:
        commands.extend(list(build_cmdset.get_commands().values()))

    created = 0
    for cmd in commands:
        if repo.get_policy(cmd.name) is not None:
            continue
        seed = policy_seed_for(cmd.name)
        if (
            not seed["required_permissions_any"]
            and not seed["required_permissions_all"]
            and not seed["required_roles_any"]
            and getattr(cmd, "command_type", None) == CommandType.ADMIN
        ):
            seed["required_permissions_any"] = ["admin.*"]
        repo.upsert_policy(
            cmd.name,
            required_permissions_any=seed["required_permissions_any"],
            required_permissions_all=seed["required_permissions_all"],
            required_roles_any=seed["required_roles_any"],
            enabled=True,
            updated_by="seed",
            commit=False,
        )
        created += 1

    session.commit()
    logger.info("ensure_command_policies_seed created=%s", created)
    return True


def ensure_account_type(session) -> bool:
    """确保 account 类型存在。"""
    from app.models.graph import NodeType

    existing = session.query(NodeType).filter(NodeType.type_code == "account").first()
    if existing:
        return True

    from db.ontology.schema_envelope import account_node_type_schema_definition

    node_type = NodeType(
        type_code="account",
        type_name="账号",
        typeclass="app.models.accounts.DefaultAccount",
        classname="DefaultAccount",
        module_path="app.models.accounts",
        description="用户账号类型，支持管理员、开发者和普通用户",
        schema_definition=account_node_type_schema_definition(),
        trait_class="PERSON",
        trait_mask=0,
        is_active=True,
    )
    session.add(node_type)
    session.commit()
    return True


# Default AICO phase_llm / mode_models when seeding npc_agent (instance attributes, not agents.llm YAML).
_AICO_DEFAULT_MODE_MODELS = {
    "fast": "gpt-4o-mini",
    "plan": "gpt-4o-mini",
    "think": "gpt-4o",
}
# Previous seed default (plan+do LLM); replaced by thin PDCA — migrate idempotently when still present.
_AICO_LEGACY_PHASE_LLM = {
    "plan": {"mode": "fast"},
    "do": {"mode": "fast"},
    "check": {"mode": "skip"},
    "act": {"mode": "skip"},
}
# Check runs as a lightweight guardrail that can emit a ``RETRY:`` signal to
# re-plan when the Do reply is not backed by tool observations. See
# ``LlmPDCAFramework._parse_check_retry_signal``.
_AICO_DEFAULT_PHASE_LLM = {
    "plan": {"mode": "fast"},
    "do": {"mode": "fast"},
    "check": {"mode": "fast"},
    "act": {"mode": "skip"},
}


def _aico_phase_llm_is_legacy(phase_llm: object) -> bool:
    if not isinstance(phase_llm, dict):
        return False
    keys = {"plan", "do", "check", "act"}
    if set(phase_llm.keys()) != keys:
        return False
    return all(phase_llm.get(k) == v for k, v in _AICO_LEGACY_PHASE_LLM.items())


def ensure_root_node(session=None) -> bool:
    """确保根节点存在（奇点房间）。"""
    from app.models.root_manager import root_manager

    return root_manager.ensure_root_node_exists()


def ensure_aico_npc_agent(session) -> bool:
    """
    Idempotent: default assistant AICO as npc_agent in Singularity Room, trait_mask=370.
    Requires npc_agent NodeType and root room; no-op if already present.
    """
    import uuid as uuid_lib

    from app.constants.trait_mask import MOBILE, NPC_AGENT
    from app.models.graph import Node, NodeType

    existing = (
        session.query(Node)
        .filter(
            Node.type_code == "npc_agent",
            Node.attributes["service_id"].astext == "aico",
            Node.is_active == True,  # noqa: E712
        )
        .first()
    )
    if existing:
        attrs = existing.attributes or {}
        merged = dict(attrs)
        changed = False
        if "mode_models" not in merged:
            merged["mode_models"] = dict(_AICO_DEFAULT_MODE_MODELS)
            changed = True
        if "phase_llm" not in merged:
            merged["phase_llm"] = {k: dict(v) for k, v in _AICO_DEFAULT_PHASE_LLM.items()}
            changed = True
        elif _aico_phase_llm_is_legacy(merged.get("phase_llm")):
            merged["phase_llm"] = {k: dict(v) for k, v in _AICO_DEFAULT_PHASE_LLM.items()}
            changed = True
        if changed:
            existing.attributes = merged
            session.commit()
        return True

    nt = session.query(NodeType).filter(NodeType.type_code == "npc_agent").first()
    if not nt:
        logger.warning("ensure_aico_npc_agent: npc_agent NodeType missing")
        return False

    root = (
        session.query(Node)
        .filter(
            Node.type_code == "room",
            Node.attributes["is_root"].astext == "true",
            Node.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not root:
        logger.warning("ensure_aico_npc_agent: root room missing")
        return False

    trait = int(NPC_AGENT & ~MOBILE)
    node = Node(
        uuid=uuid_lib.uuid4(),
        type_id=nt.id,
        type_code="npc_agent",
        name="AICO",
        description="CampusWorld default assistant",
        is_active=True,
        is_public=True,
        access_level="normal",
        trait_class=nt.trait_class or "AGENT",
        trait_mask=trait,
        location_id=root.id,
        attributes={
            "agent_role": "narrative_npc",
            "enabled": True,
            "service_id": "aico",
            "trigger_mode": "nlp",
            "decision_mode": "llm",
            "cognition_profile_ref": "pdca_v1",
            # Discovery suite (primer / whoami / look / find / describe) is the
            # backbone of "tool first" answering. ``find`` follows Evennia's
            # ``@find`` convention; ``describe`` is our ``examine`` equivalent.
            # Allowlist aliases resolve to primaries at surface-build time so
            # ops may also spell tools as ``locate`` / ``ex`` / etc.
            "tool_allowlist": [
                "help",
                "look",
                "time",
                "version",
                "whoami",
                "primer",
                "find",
                "describe",
                "agent",
                "agent_capabilities",
                "agent_tools",
            ],
            "model_config_ref": "aico",
            "service_account_id": None,
            "version": "1",
            "mode_models": dict(_AICO_DEFAULT_MODE_MODELS),
            "phase_llm": {k: dict(v) for k, v in _AICO_DEFAULT_PHASE_LLM.items()},
        },
        tags=["system", "aico", "default"],
    )
    session.add(node)
    session.commit()
    logger.info("ensure_aico_npc_agent: created AICO node id=%s", node.id)
    return True


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
        logger.info(f"Default accounts already exist, skipping creation (idempotent)")
        return True

    def _attrs(obj, data_access: dict) -> dict:
        attrs = dict(obj._node_attributes or {})
        logger.debug(f"_attrs called for {obj.username}, keys: {list(attrs.keys())}")
        for k, v in list(attrs.items()):
            if isinstance(v, datetime):
                attrs[k] = v.isoformat()
        attrs["data_access"] = deepcopy(data_access)
        return attrs

    logger.info("Starting default account creation...")

    # 使用 disable_auto_sync=True 避免在对象创建时自动同步（会与传入的session冲突）
    # seed_data 的设计是手动创建 Node 对象，不依赖自动同步
    admin = AdminAccount(
        username="admin",
        email="admin@campusworld.com",
        hashed_password=get_password_hash("admin123"),
        description="系统管理员账号，拥有所有管理权限",
        created_by="system",
        disable_auto_sync=True,
    )
    dev = DeveloperAccount(
        username="dev",
        email="dev@campusworld.com",
        hashed_password=get_password_hash("dev123"),
        description="开发者账号，拥有开发和调试权限",
        created_by="admin",
        disable_auto_sync=True,
    )
    campus = CampusUserAccount(
        username="campus",
        email="campus@campusworld.com",
        hashed_password=get_password_hash("campus123"),
        description="园区用户账号，用于测试园区功能",
        created_by="admin",
        disable_auto_sync=True,
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
            attributes=_attrs(admin, ADMIN_DATA_ACCESS),
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
            attributes=_attrs(dev, DEV_DATA_ACCESS),
            tags=["system", "dev", "default"],
        ),
        Node(
            uuid=uuid.uuid4(),
            type_id=account_type.id,
            type_code="account",
            name="campus",
            description="园区用户账号，用于测试园区功能",
            is_active=True,
            is_public=True,
            access_level="normal",
            attributes=_attrs(campus, USER_LIKE_DATA_ACCESS),
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
        from app.core.database import db_session_context

        with db_session_context() as session:
            if not ensure_account_type(session):
                return False
            if not ensure_default_accounts(session):
                return False
            if not ensure_content_visibility_seed(session):
                return False
            if not ensure_command_policies_seed(session):
                return False

        # 根节点初始化同样是幂等的
        if not ensure_root_node():
            return False

        with db_session_context() as session:
            if not ensure_aico_npc_agent(session):
                logger.warning("ensure_aico_npc_agent skipped or failed")

        logger.info("seed_minimal completed")
        return True
    except Exception as e:
        logger.error(f"seed_minimal failed: {e}")
        return False

