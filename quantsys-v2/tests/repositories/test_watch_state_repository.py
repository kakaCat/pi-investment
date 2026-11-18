"""WatchDigestStateRepository 固定重试批次的 JSONB 契约测试。"""
from datetime import datetime
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from adapters.outbound.repositories.watch_state_repository import WatchDigestStateRepository
from infrastructure.persistence.orm.models import WatchDigestState
from qs_kernel.infrastructure.persistence.orm import get_session

MODULE = 'adapters.outbound.repositories.watch_state_repository'


def _session_with_row(row):
    session = MagicMock()
    filtered = session.query.return_value.filter.return_value
    filtered.first.return_value = row
    filtered.with_for_update.return_value.first.return_value = row
    filtered.with_for_update.return_value.one.return_value = row
    return session


def test_pending_batch_is_namespaced_and_normal_watermarks_survive():
    row = SimpleNamespace(wake_marks={'acct_A': '2026-11-18T09:00:00'})
    session = _session_with_row(row)
    batch = {'payload': {'event_id': 'watch_digest:one'}, 'through': '2026-11-18T10:00:00'}
    with patch(f'{MODULE}.get_session', return_value=session):
        assert WatchDigestStateRepository().save_pending_batch('acct_A', batch) is True
    assert row.wake_marks['acct_A'] == '2026-11-18T09:00:00'
    assert row.wake_marks[WatchDigestStateRepository._PENDING_KEY]['acct_A'] == batch
    session.commit.assert_called_once_with()


def test_pending_batch_rejects_cross_worker_overwrite():
    key = WatchDigestStateRepository._PENDING_KEY
    old = {'payload': {'event_id': 'watch_digest:old'}, 'through': '2026-11-18T10:00:00'}
    row = SimpleNamespace(wake_marks={key: {'acct_A': old}})
    session = _session_with_row(row)
    new = {'payload': {'event_id': 'watch_digest:new'}, 'through': '2026-11-18T10:01:00'}
    with patch(f'{MODULE}.get_session', return_value=session), patch(f'{MODULE}._safe_rollback'):
        assert WatchDigestStateRepository().save_pending_batch('acct_A', new) is False
    assert row.wake_marks[key]['acct_A'] == old
    session.commit.assert_not_called()
    session.query.return_value.filter.return_value.with_for_update.assert_called_once_with()


def test_clear_one_pending_batch_does_not_drop_other_accounts():
    key = WatchDigestStateRepository._PENDING_KEY
    row = SimpleNamespace(wake_marks={
        'acct_A': 'watermark', key: {'acct_A': {'payload': {'event_id': 'event-A'}},
                                  'acct_B': {'payload': {'event_id': 'event-B'}}},
    })
    session = _session_with_row(row)
    with patch(f'{MODULE}.get_session', return_value=session):
        assert WatchDigestStateRepository().clear_pending_batch('acct_A', 'event-A') is True
    assert row.wake_marks['acct_A'] == 'watermark'
    assert list(row.wake_marks[key]) == ['acct_B']


def test_old_completion_cannot_clear_newer_pending_event():
    key = WatchDigestStateRepository._PENDING_KEY
    current = {'payload': {'event_id': 'event-Q'}, 'through': '2026-11-18T10:02:00'}
    row = SimpleNamespace(wake_marks={key: {'acct_A': current}})
    session = _session_with_row(row)
    with patch(f'{MODULE}.get_session', return_value=session), patch(f'{MODULE}._safe_rollback'):
        assert WatchDigestStateRepository().clear_pending_batch('acct_A', 'event-P') is True
    assert row.wake_marks[key]['acct_A'] == current
    session.commit.assert_not_called()


def test_load_separates_reserved_pending_batches_from_wake_marks():
    at = datetime(2026, 11, 18, 10, 0)
    key = WatchDigestStateRepository._PENDING_KEY
    row = (at, at.date(), 2, {'acct_A': at.isoformat(), key: {'acct_A': {'payload': {}}}})
    session = _session_with_row(row)
    with patch(f'{MODULE}.get_session', return_value=session):
        state = WatchDigestStateRepository().load_state()
    assert state['wake_marks'] == {'acct_A': at.isoformat()}
    assert state['pending_batches'] == {'acct_A': {'payload': {}}}


def test_cross_day_wake_preserves_pending_and_locks_shared_row():
    key = WatchDigestStateRepository._PENDING_KEY
    pending = {'acct_B': {'payload': {'event_id': 'watch_digest:B'}}}
    row = SimpleNamespace(wake_date=datetime(2026, 11, 17).date(), wake_count=2,
                          wake_marks={'acct_A': 'old', 'acct_C': 'old', key: pending})
    session = _session_with_row(row)
    with patch(f'{MODULE}.get_session', return_value=session):
        assert WatchDigestStateRepository().save_wake(
            datetime(2026, 11, 18, 10, 0), account='acct_A') is True
    assert row.wake_marks[key] == pending
    assert row.wake_marks['acct_A'] == '2026-11-18T10:00:00'
    assert 'acct_C' not in row.wake_marks
    assert row.wake_count == 1
    session.query.return_value.filter.return_value.with_for_update.assert_called_once_with()


def test_load_failure_is_explicit_and_save_failure_returns_false():
    session = MagicMock()
    session.query.return_value.filter.return_value.first.side_effect = RuntimeError('read down')
    with patch(f'{MODULE}.get_session', return_value=session), patch(f'{MODULE}._safe_rollback'):
        state = WatchDigestStateRepository().load_state()
    assert state['load_error'] == 'read down'

    session = MagicMock()
    session.execute.side_effect = RuntimeError('write down')
    with patch(f'{MODULE}.get_session', return_value=session), patch(f'{MODULE}._safe_rollback'):
        assert WatchDigestStateRepository().save_wake(datetime(2026, 11, 18, 10, 0)) is False


@pytest.mark.integration
def test_concurrent_pending_writes_for_two_accounts_neither_lost():
    session = get_session()
    row = session.query(WatchDigestState).filter(WatchDigestState.id == 1).first()
    original = None if row is None else {
        'last_wake_at': row.last_wake_at, 'wake_date': row.wake_date,
        'wake_count': row.wake_count, 'wake_marks': dict(row.wake_marks or {}),
    }
    if row is None:
        row = WatchDigestState(id=1, wake_marks={})
        session.add(row)
    marks = dict(row.wake_marks or {})
    marks.pop(WatchDigestStateRepository._PENDING_KEY, None)
    row.wake_marks = marks
    session.commit()
    barrier = threading.Barrier(2)
    results, errors = [], []

    def worker(account):
        repo = WatchDigestStateRepository()
        try:
            barrier.wait(timeout=5)
            results.append(repo.save_pending_batch(account, {
                'payload': {'event_id': f'watch_digest:{account}'},
                'through': '2026-11-18T10:00:00',
            }))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            get_session().close()

    try:
        threads = [threading.Thread(target=worker, args=(account,)) for account in ('acct_A', 'acct_B')]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert not errors
        assert sorted(results) == [True, True]
        session.expire_all()
        pending = WatchDigestStateRepository().load_state()['pending_batches']
        assert set(pending) == {'acct_A', 'acct_B'}
    finally:
        session.rollback()
        current = session.query(WatchDigestState).filter(WatchDigestState.id == 1).first()
        if original is None:
            if current is not None:
                session.delete(current)
        else:
            for key, value in original.items():
                setattr(current, key, value)
        session.commit()
