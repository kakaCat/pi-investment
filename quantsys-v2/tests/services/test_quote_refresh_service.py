"""QuoteRefreshService 契约锁（RFC 017 P2，2026-10-27，w-7e3880c6）

锁四件事：
  ① single-flight：同账户并发触发合并为一次 provider 调用（15s 轮询+多窗口不放大）；
  ② 成功写库、部分成功标 partial（缺口显式）；
  ③ 全程失败**不发写**（保留最后有效快照）+ 错误进 last 状态；
  ④ 空仓 skipped，不产生无意义 provider 请求。
"""
import threading
import time

from qs_trading.application.services.quote_refresh_service import QuoteRefreshService


class _FakeRepo:
    def __init__(self, positions):
        self._positions = positions
        self.written = []

    def get_all_positions(self, account_name):
        return self._positions

    def update_position_prices(self, account_name, prices):
        self.written.append((account_name, dict(prices)))


class _FakePosition:
    def __init__(self, symbol):
        self.symbol = symbol


class _FakeService:
    def __init__(self, positions, prices, block: threading.Event = None, entered: threading.Event = None):
        self.repo = _FakeRepo(positions)
        self._prices = prices
        self._block = block
        self._entered = entered
        self.calls = 0

    def _fetch_current_prices(self, symbols):
        self.calls += 1
        if self._entered is not None:
            self._entered.set()
        if self._block is not None:
            self._block.wait(timeout=5)
        prices = {s: p for s, p in self._prices.items() if s in symbols}
        return prices, {}


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_success_writes_prices_and_status():
    svc = _FakeService([_FakePosition('600519'), _FakePosition('000001')],
                       {'600519': 1500.0, '000001': 10.0})
    q = QuoteRefreshService(svc)
    accepted = q.schedule('acct')
    assert accepted['accepted'] is True and accepted['coalesced'] is False
    assert _wait_until(lambda: q.last('acct') is not None), '刷新必须完成'
    last = q.last('acct')
    assert last['status'] == 'success'
    assert last['prices'] == 2 and last['symbols'] == 2
    assert svc.repo.written == [('acct', {'600519': 1500.0, '000001': 10.0})]


def test_partial_marks_partial_and_writes_what_got():
    svc = _FakeService([_FakePosition('600519'), _FakePosition('000001')], {'600519': 1500.0})
    q = QuoteRefreshService(svc)
    q.schedule('acct')
    assert _wait_until(lambda: q.last('acct') is not None)
    assert q.last('acct')['status'] == 'partial'
    assert svc.repo.written == [('acct', {'600519': 1500.0})]


def test_all_failed_no_write_keeps_snapshot():
    svc = _FakeService([_FakePosition('600519')], {})
    q = QuoteRefreshService(svc)
    q.schedule('acct')
    assert _wait_until(lambda: q.last('acct') is not None)
    last = q.last('acct')
    assert last['status'] == 'failed'
    assert last['error'] and '保留最后有效快照' in last['error']
    assert svc.repo.written == [], '刷新失败不得写空价格（保留最后有效快照）'


def test_empty_positions_skipped_no_provider_call():
    svc = _FakeService([], {})
    q = QuoteRefreshService(svc)
    q.schedule('acct')
    assert _wait_until(lambda: q.last('acct') is not None)
    assert q.last('acct')['status'] == 'skipped'
    assert svc.calls == 0, '空仓不得发 provider 请求'


def test_single_flight_coalesces_concurrent_requests():
    block = threading.Event()
    entered = threading.Event()
    svc = _FakeService([_FakePosition('600519')], {'600519': 1500.0},
                       block=block, entered=entered)
    q = QuoteRefreshService(svc)
    first = q.schedule('acct')
    assert entered.wait(timeout=3), '第一次刷新应已进入 provider 调用'
    second = q.schedule('acct')
    assert first['coalesced'] is False
    assert second['coalesced'] is True, '同账户在途请求必须合并（single-flight）'
    assert svc.calls == 1
    block.set()
    assert _wait_until(lambda: q.last('acct') is not None)
    assert q.last('acct')['status'] == 'success'
