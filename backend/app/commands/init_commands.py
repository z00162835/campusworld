"""
命令初始化模块
负责注册所有系统命令和场景命令
"""

from .registry import command_registry
from .graph_inspect_commands import GRAPH_INSPECT_COMMANDS
from .system_commands import SYSTEM_COMMANDS
from .system_primer_command import PRIMER_COMMANDS
from .game import GAME_COMMANDS
from .builder import get_build_cmdset
import threading
from app.core.log import get_logger, LoggerNames

logger = get_logger(LoggerNames.COMMAND)

_commands_initialized = False
_init_lock = threading.Lock()
_initializing = False
_init_done_event = threading.Event()


def _schedule_command_ability_sync() -> None:
    """
    将 system_command_ability 图同步移出启动关键路径。
    每命令一条 INSERT 时曾逐条 commit（ability_sync 旧实现），命令增多会严重拖慢 HTTP lifespan / SSH 首次 initialize_commands，表现为「卡在初始化建造命令系统」。
    """

    def _run() -> None:
        try:
            from app.core.database import db_session_context

            with db_session_context() as session:
                from app.commands.ability_sync import ensure_command_ability_nodes

                n = ensure_command_ability_nodes(session)
                logger.info("command ability graph sync finished (touched=%s)", n)
        except Exception as e:
            logger.error("command ability graph sync failed: %s", e, exc_info=True)

    threading.Thread(target=_run, name="command-ability-sync", daemon=True).start()


def trigger_command_init_warmup() -> None:
    """Non-blocking command init warmup for HTTP lifespan."""
    with _init_lock:
        if _commands_initialized or _initializing:
            return

    def _run() -> None:
        logger.info("lifespan_warmup_started")
        ok = initialize_commands()
        if ok:
            logger.info("lifespan_warmup_succeeded")
        else:
            logger.error("lifespan_warmup_failed")

    threading.Thread(target=_run, name="command-init-warmup", daemon=True).start()


def initialize_commands(force_reinit: bool = False) -> bool:
    """初始化命令系统 - 单例模式"""
    global _commands_initialized, _initializing

    if force_reinit:
        logger.warning("force_reinit=True uses blocking init path")
        with _init_lock:
            _initializing = True
            _init_done_event.clear()
        should_wait = False
    else:
        with _init_lock:
            if _commands_initialized:
                return True
            if _initializing:
                should_wait = True
            else:
                _initializing = True
                _init_done_event.clear()
                should_wait = False

    if should_wait:
        # 其他入口正在初始化，避免重复执行重路径；等待初始化结束即可。
        done = _init_done_event.wait(timeout=30)
        if not done:
            logger.error("command init wait timeout (30s)")
            return False
        return _commands_initialized

    success = False
    try:
        logger.info("command init: registering system + agent + game commands")
        from .agent_commands import get_agent_commands
        AGENT_COMMANDS = get_agent_commands()

        # 统一系统命令注册清单（四类）：SYSTEM / PRIMER / GRAPH_INSPECT / AGENT
        system_command_groups = [
            ("SYSTEM_COMMANDS", SYSTEM_COMMANDS),
            ("PRIMER_COMMANDS", PRIMER_COMMANDS),
            ("GRAPH_INSPECT_COMMANDS", GRAPH_INSPECT_COMMANDS),
            ("AGENT_COMMANDS", AGENT_COMMANDS),
        ]

        # 注册系统命令
        system_success = 0
        for _group_name, commands in system_command_groups:
            for command in commands:
                if command_registry.register_command(command):
                    system_success += 1
                else:
                    logger.error(f"系统命令 '{command.name}' 注册失败")

            # 注册场景命令
        game_success = 0
        for command in GAME_COMMANDS:
            if command_registry.register_command(command):
                game_success += 1
            else:
                logger.error(f"场景命令 '{command.name}' 注册失败")

        logger.info("command init: loading build cmdset (model discovery may touch DB)")
        build_cmdset = get_build_cmdset()
        if build_cmdset:
            for command in build_cmdset.get_commands().values():
                if not command_registry.register_command(command):
                    logger.error(f"建造命令 '{command.name}' 注册失败")

        try:
            from app.core.database import db_session_context
            from app.commands.policy_store import ensure_default_command_policies
            from app.services.task.permissions import register_task_permissions_into_admin

            logger.info("command init: ensuring default command_policies (required for authz)")
            register_task_permissions_into_admin()
            with db_session_context() as session:
                ensure_default_command_policies(session)
        except Exception as e:
            logger.error("command policy bootstrap failed: %s", e)
            return False

            # 显示注册摘要
        _ = command_registry.get_commands_summary()
        logger.info("command init: scheduling command ability graph sync (non-blocking)")
        _schedule_command_ability_sync()
        expected_sys = sum(len(commands) for _, commands in system_command_groups)
        success = system_success == expected_sys and game_success == len(GAME_COMMANDS)
        return success

    except Exception as e:
        logger.error(f"命令系统初始化失败: {e}")
        return False
    finally:
        with _init_lock:
            _initializing = False
            if success:
                _commands_initialized = True
            _init_done_event.set()


def ensure_commands_initialized() -> None:
    """
    若注册表仍为空则执行初始化。
    历史上 initialize_commands 仅在 SSH 控制台首次连接时调用，纯 HTTP/WebSocket/CLI 会拿到空 registry。
    """
    if command_registry.commands:
        return
    initialize_commands()


def get_command_summary() -> dict:
    """获取命令摘要"""
    return command_registry.get_commands_summary()


def register_game_commands(game_name: str, commands: list) -> bool:
    """注册场景特定命令"""
    try:
        success_count = 0
        for command in commands:
            if command_registry.register_command(command):
                success_count += 1
            else:
                logger.error(f"场景 '{game_name}' 命令 '{command.name}' 注册失败")
        
        logger.info(f"场景 '{game_name}' 命令注册完成: {success_count}/{len(commands)}")
        return success_count == len(commands)
        
    except Exception as e:
        logger.error(f"注册场景 '{game_name}' 命令失败: {e}")
        return False


def unregister_game_commands(game_name: str) -> bool:
    """注销场景特定命令"""
    try:
        # 这里需要实现按场景名称注销命令的逻辑
        # 暂时返回True
        logger.info(f"场景 '{game_name}' 命令已注销")
        return True
        
    except Exception as e:
        logger.error(f"注销场景 '{game_name}' 命令失败: {e}")
        return False
