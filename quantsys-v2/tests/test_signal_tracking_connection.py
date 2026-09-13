"""信号追踪 Repository 连接纪律回归（2026-09-13，w-32314d00，事件 21ee9ab6）

事故（原始 traceback 来自看板卡片）：
    signal_tracking_repository.py:106 update_signal_performance → cursor.execute(...)
        psycopg2.OperationalError: terminating connection due to idle-in-transaction timeout
    signal_tracking_repository.py:110 → self.db.rollback()
        psycopg2.InterfaceError: connection already closed
两个缺陷：
  ① 读方法（get_signals_by_date / get_signals_after_date / get_signals）**不结束事务**，
     而 repository 持长寿命裸连接 → 两次调用之间空闲在事务中 → 超过 PG 的
     idle_in_transaction_session_timeout 被服务端杀连接 → 下一次写操作 bomb；
  ② except 里对**已死连接**调 rollback() → InterfaceError **顶替**原始 OperationalError，
     真因被掩盖，且连接永不重建 → 之后每次调用都失败。

本文件锁定：读后事务结束；死连接的 rollback 失败不掩盖原始异常；连接可自愈重建。
"""
import psycopg2
import pytest

from adapters.outbound.repositories.signal_tracking_repository import SignalTrackingRepository


class _Cursor:
    def __init__(self, rows=None, description=None, execute_exc=None):
        self._rows = rows or []
        self.description = description or [('id',), ('symbol',)]
        self._execute_exc = execute_exc
        self.closed = False

    def execute(self, sql, params=None):
        if self._execute_exc:
            raise self._execute_exc

    def fetchall(self):
        return self._rows

    def close(self):
        self.closed = True


class _Conn:
    def __init__(self, cursor, closed=0, rollback_exc=None):
        self._cursor = cursor
        self.closed = closed
        self._rollback_exc = rollback_exc
        self.rollbacks = 0
        self.commits = 0

    def cursor(self):
        return self._cursor

    def rollback(self):
        self.rollbacks += 1
        if self._rollback_exc:
            raise self._rollback_exc

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = 1


def _repo(conn):
    return SignalTrackingRepository(db_connection=conn)


def test_read_ends_transaction():
    """读方法退出前必须结束事务，否则长寿命连接会空闲在事务里被 PG 杀掉。"""
    conn = _Conn(_Cursor(rows=[(1, '600519')]))
    repo = _repo(conn)
    rows = repo.get_signals_by_date('2026-09-13')
    assert rows == [{'id': 1, 'symbol': '600519'}]
    assert conn.rollbacks >= 1, "读后未结束事务"


def test_get_signals_also_ends_transaction():
    conn = _Conn(_Cursor(rows=[]))
    _repo(conn).get_signals(limit=5)
    assert conn.rollbacks >= 1


def test_dead_connection_rollback_does_not_mask_original_error():
    """原始异常必须冒泡（真因是 idle-in-transaction 超时，不是 connection already closed）。"""
    original = psycopg2.OperationalError('terminating connection due to idle-in-transaction timeout')
    conn = _Conn(_Cursor(execute_exc=original),
                 rollback_exc=psycopg2.InterfaceError('connection already closed'))
    repo = _repo(conn)
    with pytest.raises(psycopg2.OperationalError) as ei:
        repo.update_signal_performance(1, {'price_5d': 10.5})
    assert 'idle-in-transaction' in str(ei.value)
    assert repo.db is None, "死连接应被丢弃，交由下次调用重建"


def test_ensure_connection_reconnects_when_closed():
    conn = _Conn(_Cursor(), closed=1)
    repo = _repo(conn)
    new_conn = _Conn(_Cursor())
    repo._connect = lambda: new_conn          # 替换真实建连（测试不碰库）
    assert repo._ensure_connection() is new_conn
    assert repo.db is new_conn


def test_ensure_connection_keeps_healthy_connection():
    conn = _Conn(_Cursor())
    repo = _repo(conn)
    assert repo._ensure_connection() is conn
    assert conn.closed == 0
