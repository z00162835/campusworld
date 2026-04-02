"""Controllable in-room devices (Evennia-style Object descendants via WorldThing)."""

from .base import WorldThing


class NetworkAccessPoint(WorldThing):
    """Package ``type_code``: ``network_access_point``."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "network_access_point"
        super().__init__(name=name, **kwargs)


class AvDisplay(WorldThing):
    """Package ``type_code``: ``av_display`` (meeting / signage display)."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "av_display"
        super().__init__(name=name, **kwargs)


class LightingFixture(WorldThing):
    """Package ``type_code``: ``lighting_fixture``."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "lighting_fixture"
        super().__init__(name=name, **kwargs)
