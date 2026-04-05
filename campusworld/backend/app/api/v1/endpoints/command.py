"""
命令执行 REST API
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.commands.registry import command_registry
from app.commands.base import CommandContext, CommandResult
from app.commands.shell_words import split_command_line
from app.core.database import db_session_context

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
    user_id: str = "guest",
    username: str = "Guest",
    session_id: str = "http_session",
    permissions: str = "player"
):
    """执行命令"""
    try:
        parts = split_command_line(request.command.strip())
        command_name = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        if request.args:
            args = request.args

        # 解析权限
        perm_list = [p.strip() for p in permissions.split(",")]

        with db_session_context() as db_session:
            context = CommandContext(
                user_id=user_id,
                username=username,
                session_id=session_id,
                permissions=perm_list,
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
async def list_commands():
    """获取所有可用命令"""
    commands = []
    for name, cmd in command_registry.commands.items():
        commands.append(CommandInfo(
            name=name,
            description=cmd.description or "",
            aliases=cmd.aliases,
            command_type=cmd.command_type.value
        ))
    return commands


@router.get("/{command_name}", response_model=CommandInfo)
async def get_command(command_name: str):
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
