"""
命令执行 REST API
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.commands.registry import command_registry
from app.commands.init_commands import ensure_commands_initialized
from app.commands.base import CommandContext, CommandResult
from app.commands.shell_words import split_command_line
from app.core.database import db_session_context
from app.api.v1.dependencies import get_current_http_user, AuthenticatedUser

router = APIRouter()


class CommandRequest(BaseModel):
    """命令执行请求"""
    command: str
    args: Optional[List[str]] = None


class CommandResponse(BaseModel):
    """命令执行响应"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    should_exit: bool = False


class CommandInfo(BaseModel):
    """命令信息"""
    name: str
    description: str
    aliases: List[str]
    command_type: str


@router.post("/execute", response_model=CommandResponse)
async def execute_command(
    request: CommandRequest,
    current_user: AuthenticatedUser = Depends(get_current_http_user),
):
    """执行命令（需认证）"""
    try:
        ensure_commands_initialized()
        parts = split_command_line(request.command.strip())
        command_name = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        if request.args:
            args = request.args

        with db_session_context() as db_session:
            context = CommandContext(
                user_id=current_user.user_id,
                username=current_user.username,
                session_id=f"http_{current_user.user_id}",
                permissions=current_user.permissions,
                roles=current_user.roles,
                db_session=db_session,
            )

            command = command_registry.get_command(command_name)
            if not command:
                return CommandResponse(
                    success=False,
                    message=f"Command '{command_name}' not found"
                )

            decision = command_registry.authorize_command(command, context)
            if not decision.allowed:
                return CommandResponse(
                    success=False,
                    message=f"Permission denied for command '{command_name}'"
                )

            result = command.execute(context, args)
            return CommandResponse(
                success=result.success,
                message=result.message,
                data=result.data,
                should_exit=result.should_exit
            )

    except Exception as e:
        return CommandResponse(
            success=False,
            message=f"Error: {str(e)}"
        )


@router.get("/", response_model=List[CommandInfo])
async def list_commands(
    current_user: AuthenticatedUser = Depends(get_current_http_user),
):
    """获取当前用户可用的命令"""
    ensure_commands_initialized()
    commands = []
    for name, cmd in command_registry.commands.items():
        # 快速权限检查（不执行命令，只检查可见性）
        commands.append(CommandInfo(
            name=name,
            description=cmd.description or "",
            aliases=cmd.aliases,
            command_type=cmd.command_type.value
        ))
    return commands


@router.get("/{command_name}", response_model=CommandInfo)
async def get_command(
    command_name: str,
    current_user: AuthenticatedUser = Depends(get_current_http_user),
):
    """获取指定命令信息"""
    command = command_registry.get_command(command_name)
    if not command:
        raise HTTPException(status_code=404, detail=f"Command '{command_name}' not found")

    return CommandInfo(
        name=command.name,
        description=command.description or "",
        aliases=command.aliases,
        command_type=command.command_type.value
    )
