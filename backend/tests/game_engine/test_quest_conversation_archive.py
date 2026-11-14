"""Scoped conversation lifecycle learning-input contracts without a database."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.commands.base import CommandContext
from app.game_engine.agent_runtime import conversation_stm_service as stm
from app.models.system.agent_memory_tables import AgentConversationThread, AgentConversationStm, AgentMemoryEntry, AgentLongTermMemory


def archive_session():
    thread = SimpleNamespace(
        id=uuid.uuid4(), owner_account_node_id=1, agent_node_id=99, quest_node_id=44,
        collaboration_relationship_id=66, created_projection_revision='12',
        graph_ref_metadata={'objective_node_id': 55}, archived_at=None, archive_reason=None,
    )
    thread_query, segment_query = MagicMock(), MagicMock()
    thread_query.filter.return_value.order_by.return_value.with_for_update.return_value.all.return_value = [thread]
    segment_query.filter.return_value.order_by.return_value.all.return_value = [SimpleNamespace(
        messages=[{'role': 'user', 'content': 'Inspect', 'ts': '2026-11-14T00:00:00Z'}],
        rolling_summary='Earlier inspection context',
    )]
    session = MagicMock()
    session.query.side_effect = lambda model: {
        AgentConversationThread: thread_query, AgentConversationStm: segment_query,
    }[model]
    return session, thread, thread_query, segment_query


def test_archive_retains_scoped_episode_and_compacted_context_once(monkeypatch):
    session, thread, thread_query, segment_query = archive_session()
    monkeypatch.setattr(stm, 'try_acquire_conversation_thread_tick_lock', lambda *_args: True)
    kwargs = dict(quest_node_id=44, collaboration_relationship_id=66, reason='collaboration_ended')
    assert stm.archive_quest_conversation_threads(session, **kwargs) == 1
    episode = session.add.call_args.args[0]
    assert episode.kind == 'quest_episode_input'
    assert episode.agent_node_id == 99
    assert episode.payload['caller_account_node_id'] == 1
    assert episode.payload['conversation_thread_id'] == str(thread.id)
    assert episode.payload['quest_node_id'] == 44
    assert episode.payload['graph_refs'] == {'objective_node_id': 55}
    assert episode.payload['verification_status'] == 'unverified'
    assert episode.payload['segments'][0]['rolling_summary'] == 'Earlier inspection context'
    assert episode.payload['segments'][0]['messages'][0]['content'] == 'Inspect'
    assert thread.archive_reason == 'collaboration_ended'
    assert thread.archived_at is not None
    assert stm.archive_quest_conversation_threads(session, **kwargs) == 0
    session.add.assert_called_once()
    session.commit.assert_not_called()
    # Check the actual ORM predicates, not only the supplied snapshot values.
    thread_clauses = thread_query.filter.call_args.args
    assert [clause.right.value for clause in thread_clauses[:2]] == [44, 66]
    segment_clauses = segment_query.filter.call_args.args
    assert [clause.right.value for clause in segment_clauses] == [1, 99, thread.id]


def test_busy_thread_prevents_archival_and_episode_write(monkeypatch):
    session, thread, *_ = archive_session()
    monkeypatch.setattr(stm, 'try_acquire_conversation_thread_tick_lock', lambda *_args: False)
    with pytest.raises(RuntimeError, match='busy'):
        stm.archive_quest_conversation_threads(session, quest_node_id=44,
            collaboration_relationship_id=66, reason='collaboration_replaced')
    assert thread.archived_at is None
    session.add.assert_not_called()


def test_archived_thread_cannot_resume(monkeypatch):
    session, thread, *_ = archive_session()
    thread.archived_at = object()
    session.query.side_effect = None
    session.query.return_value.filter.return_value.first.return_value = thread
    monkeypatch.setattr(stm, 'try_acquire_conversation_thread_tick_lock', lambda *_args: True)
    context = CommandContext(user_id='1', username='u', session_id='http_1', permissions=[],
        metadata={'aico_client_thread_id': str(thread.id), 'quest_conversation_context': {
            'quest_node_id': 44, 'collaboration_relationship_id': 66, 'projection_revision': '12',
        }})
    with pytest.raises(ValueError, match='Archived'):
        stm.ensure_conversation_thread_id(session, context=context,
            caller_account_node_id=1, agent_node_id=99)


@pytest.mark.parametrize('owner,agent', [(2, 99), (1, 100)])
def test_thread_binding_rejects_foreign_account_or_agent(monkeypatch, owner, agent):
    session, thread, *_ = archive_session()
    session.query.side_effect = None
    session.query.return_value.filter.return_value.first.return_value = thread
    monkeypatch.setattr(stm, 'try_acquire_conversation_thread_tick_lock', lambda *_args: True)
    context = CommandContext(user_id=str(owner), username='u', session_id='http_1', permissions=[],
        metadata={'aico_client_thread_id': str(thread.id)})
    with pytest.raises(ValueError, match='unavailable'):
        stm.ensure_conversation_thread_id(session, context=context,
            caller_account_node_id=owner, agent_node_id=agent)


def deletion_session():
    thread = SimpleNamespace(id=uuid.uuid4(), quest_node_id=44)
    episode = SimpleNamespace(id=7, kind='quest_episode_input', payload={
        'caller_account_node_id': 1, 'segments': [{'messages': [{'content': 'private text'}]}],
        'graph_refs': {'private_note': 'private context'},
    })
    queries = {model: MagicMock() for model in (
        AgentConversationThread, AgentConversationStm, AgentMemoryEntry, AgentLongTermMemory,
    )}
    for query in queries.values():
        query.filter.return_value = query
        query.with_for_update.return_value = query
    queries[AgentConversationThread].first.return_value = thread
    queries[AgentMemoryEntry].all.return_value = [episode]
    session = MagicMock()
    session.query.side_effect = queries.__getitem__
    return session, thread, episode, queries


def test_explicit_deletion_redacts_episode_plaintext_and_deletes_derived_ltm(monkeypatch):
    session, thread, episode, queries = deletion_session()
    monkeypatch.setattr(stm, 'try_acquire_conversation_thread_tick_lock', lambda *_args: True)
    assert stm.delete_conversation_thread_for_owner(session, owner_account_node_id=1,
        agent_node_id=99, thread_id=thread.id) is True
    assert episode.kind == 'quest_episode_redacted'
    assert episode.payload['action'] == 'learning_plaintext_deleted'
    assert episode.payload['quest_node_id'] == 44
    assert 'private' not in str(episode.payload)
    assert 'segments' not in episode.payload
    assert 'graph_refs' not in episode.payload
    raw_filters = queries[AgentMemoryEntry].filter.call_args.args
    assert [clause.right.value for clause in raw_filters] == [99, thread.id, 'quest_episode_input', '1']
    ltm_filters = queries[AgentLongTermMemory].filter.call_args_list[0].args
    assert [clause.right.value for clause in ltm_filters] == [99, 1, [7]]
    queries[AgentLongTermMemory].delete.assert_called_once()
    queries[AgentConversationStm].delete.assert_called_once()
    session.delete.assert_called_once_with(thread)
    session.commit.assert_not_called()


def test_busy_deletion_keeps_transcript_and_learning_input(monkeypatch):
    session, thread, episode, queries = deletion_session()
    monkeypatch.setattr(stm, 'try_acquire_conversation_thread_tick_lock', lambda *_args: False)
    with pytest.raises(stm.ConversationThreadBusyError):
        stm.delete_conversation_thread_for_owner(session, owner_account_node_id=1,
            agent_node_id=99, thread_id=thread.id)
    assert episode.kind == 'quest_episode_input'
    session.delete.assert_not_called()
    queries[AgentMemoryEntry].filter.assert_not_called()
    queries[AgentConversationStm].delete.assert_not_called()


def test_missing_or_foreign_thread_does_not_redact_memory(monkeypatch):
    session, thread, episode, queries = deletion_session()
    queries[AgentConversationThread].first.return_value = None
    assert stm.delete_conversation_thread_for_owner(session, owner_account_node_id=2,
        agent_node_id=99, thread_id=thread.id) is False
    assert episode.kind == 'quest_episode_input'
    assert [clause.right.value for clause in queries[AgentConversationThread].filter.call_args.args] == [thread.id, 2, 99]
    queries[AgentMemoryEntry].filter.assert_not_called()
    session.delete.assert_not_called()


def test_deleting_thread_without_episode_preserves_existing_ltm_unlink_behavior(monkeypatch):
    session, thread, _episode, queries = deletion_session()
    queries[AgentMemoryEntry].all.return_value = []
    monkeypatch.setattr(stm, 'try_acquire_conversation_thread_tick_lock', lambda *_args: True)
    assert stm.delete_conversation_thread_for_owner(session, owner_account_node_id=1,
        agent_node_id=99, thread_id=thread.id) is True
    queries[AgentLongTermMemory].delete.assert_not_called()
    queries[AgentLongTermMemory].update.assert_called_once_with({'conversation_thread_id': None}, synchronize_session=False)
