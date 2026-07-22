"""WatchNotifier 单测"""
from types import SimpleNamespace
from unittest.mock import patch

from application.services.watch_engine.conditions import EvalResult
from application.services.watch_engine.notifier import WatchNotifier


def make_rule():
    return SimpleNamespace(id=7, symbol='600519.SH', context='突破平台考虑加仓',
                           cost_price=1700.0)


def make_quote(price=1801.5):
    return SimpleNamespace(symbol='600519.SH', name='贵州茅台', price=price,
                           prev_close=1780.0, change_pct=None, volume=1_000_000)


COND = {'type': 'price_break', 'params': {'direction': 'above', 'price': 1800.0}}
RESULT = EvalResult(triggered=True, value=1801.5, distance_ratio=0.0,
                    message='现价 1801.5 ≥ 阈值 1800.0（上破）')


class FakeAgentService:
    def __init__(self, results):
        self.results = list(results)  # 每次调用的返回值
        self.calls = []

    def notify_agent(self, event, data):
        self.calls.append((event, data))
        return self.results.pop(0) if self.results else False


class FakeTriggerRepo:
    def __init__(self):
        self.records = []

    def record(self, **kw):
        self.records.append(kw)
        return SimpleNamespace(id=1)


class TestNotify:
    def test_payload_contains_context_and_pnl(self):
        agent = FakeAgentService([True])
        repo = FakeTriggerRepo()
        notifier = WatchNotifier(agent, repo, ws_url=None)
        ok = notifier.notify(make_rule(), COND, make_quote(), RESULT)
        assert ok is True
        event, data = agent.calls[0]
        assert event == 'watch_triggered'
        assert data['symbol'] == '600519.SH'
        assert data['price'] == 1801.5
        assert data['context'] == '突破平台考虑加仓'
        assert data['pnl_pct'] == round((1801.5 - 1700.0) / 1700.0 * 100, 2)
        assert data['condition']['type'] == 'price_break'
        assert data['message'] == RESULT.message
        # 审计落库
        assert repo.records[0]['notified'] is True
        assert repo.records[0]['trigger_price'] == 1801.5

    def test_retry_on_failure_then_success(self):
        agent = FakeAgentService([False, False, True])
        repo = FakeTriggerRepo()
        notifier = WatchNotifier(agent, repo, ws_url=None, max_retries=3, retry_interval=0)
        assert notifier.notify(make_rule(), COND, make_quote(), RESULT) is True
        assert len(agent.calls) == 3

    def test_all_retries_fail_still_records(self):
        agent = FakeAgentService([False, False, False])
        repo = FakeTriggerRepo()
        notifier = WatchNotifier(agent, repo, ws_url=None, max_retries=3, retry_interval=0)
        assert notifier.notify(make_rule(), COND, make_quote(), RESULT) is False
        assert repo.records[0]['notified'] is False  # 落库待补发

    def test_ws_broadcast_fire_and_forget(self):
        agent = FakeAgentService([True])
        notifier = WatchNotifier(agent, FakeTriggerRepo(),
                                 ws_url='http://127.0.0.1:5003/broadcast/market_data')
        with patch('application.services.watch_engine.notifier.requests.post') as mock_post:
            notifier.notify(make_rule(), COND, make_quote(), RESULT)
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0] == 'http://127.0.0.1:5003/broadcast/market_data'
            assert kwargs['json']['type'] == 'watch_triggered'

    def test_ws_failure_does_not_break_notify(self):
        agent = FakeAgentService([True])
        notifier = WatchNotifier(agent, FakeTriggerRepo(),
                                 ws_url='http://127.0.0.1:5003/broadcast/market_data')
        with patch('application.services.watch_engine.notifier.requests.post',
                   side_effect=ConnectionError('ws down')):
            assert notifier.notify(make_rule(), COND, make_quote(), RESULT) is True
