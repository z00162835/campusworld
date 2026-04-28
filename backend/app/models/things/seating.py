"""Furniture subtypes for HiCampus package (Evennia-style specialization)."""

from .furniture import Furniture


class ConferenceSeating(Furniture):
    """Package ``type_code``: ``conference_seating``."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "conference_seating"
        super().__init__(name=name, **kwargs)


class LoungeFurniture(Furniture):
    """Package ``type_code``: ``lounge_furniture`` (sofas, benches in public areas)."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "lounge_furniture"
        super().__init__(name=name, **kwargs)
