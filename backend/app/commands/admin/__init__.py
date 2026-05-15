"""
Admin commands module.
"""
from .notice_command import NoticeCommand

ADMIN_COMMANDS = [NoticeCommand()]

__all__ = ['NoticeCommand', 'ADMIN_COMMANDS']
