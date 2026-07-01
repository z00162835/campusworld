"""NPC / agent nodes.

`NpcAgent` extends `Character` to align with the Evennia role tree while keeping
the F02 `type_code=npc_agent` and the agent runtime contract unchanged. RPG
defaults inherited from `Character.__init__` are made inert via no-op hooks and
by not mounting `CharacterCmdSet`; see
`docs/architecture/adr/ADR-F02-NpcAgent-Character-Typeclass.md`.
"""
from typing import Any, Dict

from app.commands.cmdset import NPCCmdSet
from app.models.character import Character


class NpcAgent(Character):
    """Package ``type_code``: ``npc_agent``; see entity type registry in HiCampus SPEC."""

    def __init__(self, name: str, **kwargs):
        # ``disable_auto_sync`` would otherwise be merged into ``_node_attributes``
        # by ``Character.__init__`` (it folds kwargs into the attribute dict); pop
        # it here and honor it via the ``at_object_creation`` override below.
        disable_auto_sync = bool(kwargs.pop('disable_auto_sync', False))
        self._npc_disable_auto_sync = disable_auto_sync
        kwargs.setdefault('is_npc', True)
        kwargs.setdefault('is_ai', True)
        super().__init__(name=name, **kwargs)
        # ``Character.__init__`` writes ``_node_type='character'``; restore the
        # agent type_code so graph resolution and look bucketing stay correct.
        # (Also restored inside ``at_object_creation`` before sync runs — see
        # below — so sync_to_node never observes ``type_code='character'``.)
        self._node_type = 'npc_agent'
        self._node_type_code = 'npc_agent'

    def at_object_creation(self):
        # ``Character.__init__`` sets ``_node_type='character'`` and
        # ``DefaultObject.__init__`` (called from within ``super().__init__``)
        # invokes ``self.at_object_creation()`` *before* control returns to
        # ``NpcAgent.__init__``. If sync is enabled, ``sync_to_node`` would read
        # ``type_code='character'`` — violating F02 §6.1 invariant #1. Restore
        # the agent type_code here, before sync, so the persisted node is
        # ``npc_agent``. Mirror ``DefaultObject.at_object_creation`` but gate sync
        # on the flag popped in ``__init__`` (``Character.__init__`` does not
        # forward ``disable_auto_sync`` to ``DefaultObject.__init__`` as a
        # top-level kwarg).
        self._node_type = 'npc_agent'
        self._node_type_code = 'npc_agent'
        self._at_object_creation()
        if not getattr(self, '_npc_disable_auto_sync', False):
            self.sync_to_node()

    def _initialize_base_stats(self):
        # No RPG stat initialization for agents.
        pass

    def _init_cmdsets(self):
        # Do not call super(): ``Character._init_cmdsets`` mounts ``CharacterCmdSet``
        # (RPG micro-commands), which agents do not use. ``CharacterCmdSet`` and
        # ``NPCCmdSet`` are peer extension slots; agents use ``NPCCmdSet`` as
        # their object-level extension point, branched by ``agent_role``.
        role = self._node_attributes.get('agent_role')
        if role == 'sys_worker':
            return
        self._cmdset_manager.add_cmdset(NPCCmdSet())

    def at_action_cost(self, action_name: str) -> Dict[str, Any]:
        # Agents do not consume RPG action resources.
        return {'success': True, 'energy_cost': 0}

    def at_action_result(self, action_name: str, **kwargs) -> Dict[str, Any]:
        del action_name, kwargs
        return {'success': True}

    def get_display_extra_name_info(self, looker=None, **kwargs):
        del looker, kwargs
        st = self._node_attributes.get('activity') or self._node_attributes.get('mood')
        return f'（{st}）' if st else ''

    def room_line_format_kwargs(self):
        kw = super().room_line_format_kwargs()
        extra = self.get_display_extra_name_info()
        if extra:
            kw['hints'] = (kw.get('hints') or '') + extra
        return kw
