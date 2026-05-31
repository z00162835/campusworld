"""Regression tests for AICO nested REPL SSH integration."""
from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from app.ssh.nested_repl.aico_repl import AicoNestedReplDriver
from app.ssh.nested_repl.io import SshReplIo


def test_read_line_select_timeout_does_not_stop_console():
    """F01 regress: select timeout must not tear down the whole SSH session."""
    driver = AicoNestedReplDriver()
    console = MagicMock()
    console.running = True
    console.current_session = MagicMock(nested_repl=driver, should_disconnect=lambda: False)
    console.session_manager = MagicMock()
    channel = MagicMock()
    channel.closed = False
    console.channel = channel

    io = SshReplIo(console)
    call_count = {'n': 0}

    def fake_select(*_args, **_kwargs):
        call_count['n'] += 1
        if call_count['n'] >= 2:
            console.running = False
        return ([], [], [])

    with patch('app.ssh.nested_repl.aico_repl.select.select', side_effect=fake_select):
        result = driver._read_line(io)

    assert result is None
    assert console.running is False


def test_ctrl_q_exits_repl_without_stop_console():
    driver = AicoNestedReplDriver()
    console = MagicMock()
    console.running = True
    sess = SimpleNamespace(nested_repl=driver, command_ephemeral={}, should_disconnect=lambda: False)
    console.current_session = sess
    console.session_manager = MagicMock()
    channel = MagicMock()
    channel.closed = False
    console.channel = channel
    console._check_channel_status = MagicMock(return_value=True)
    console._safe_send_output = MagicMock(return_value=True)

    io = SshReplIo(console)

    with patch('app.ssh.nested_repl.aico_repl.select.select', return_value=([channel], [], [])), patch.object(channel, 'recv', return_value=b'\x11'):
        result = driver._read_line(io)

    assert result is None
    assert sess.nested_repl is None
    assert console.running is True
