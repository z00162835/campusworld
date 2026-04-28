from __future__ import annotations

import logging

from app.ssh.session import SSHSession


def test_session_uses_attributes_permissions_without_fallback(caplog):
    caplog.set_level(logging.WARNING)
    sess = SSHSession(
        session_id="s1",
        username="admin",
        user_id=1,
        user_attrs={"roles": ["admin"], "permissions": ["task.*"], "access_level": "admin"},
    )
    assert sess.permissions == ["task.*"]
    assert "ssh_session_permission_fallback" not in caplog.text


def test_session_fallback_logs_warning_when_permissions_missing(caplog):
    caplog.set_level(logging.WARNING)
    sess = SSHSession(
        session_id="s2",
        username="legacy",
        user_id=2,
        user_attrs={"roles": ["admin"], "access_level": "admin"},
    )
    assert sess.permissions == ["admin.*"]
    assert "ssh_session_permission_fallback" in caplog.text
