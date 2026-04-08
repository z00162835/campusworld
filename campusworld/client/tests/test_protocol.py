from campus.protocol import WSMessage


def test_connect_and_parse():
    raw = WSMessage.connect("tok")
    msg = WSMessage.parse(raw)
    assert msg == {"type": "connect", "token": "tok"}
    assert WSMessage.is_connected({"type": "connected"}) is True


def test_execute_complete():
    ex = WSMessage.execute("look", ["n"])
    m = WSMessage.parse(ex)
    assert m["type"] == "execute"
    assert m["command"] == "look"
    assert m["args"] == ["n"]
    cp = WSMessage.parse(WSMessage.complete("lo"))
    assert WSMessage.is_completions(cp) is False
    assert cp["type"] == "complete"


def test_parse_invalid():
    assert WSMessage.parse("not json") is None
