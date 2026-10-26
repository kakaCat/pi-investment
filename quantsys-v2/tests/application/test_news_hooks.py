"""新闻/政策扫描接入消息桥（REQ-261021194640-69b8 FR-3，卡 t-88d4da）

判据：critical 命中 → 调用桥建单；soft → 不调用桥；桥未注入 = 旧行为（只发卡）；
桥抛错不影响发卡与扫描结果。
"""
from datetime import datetime
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.news_watch_service import NewsWatchService
from qs_watch.application.services.watch_engine.policy_watch_service import PolicyWatchService

NOW = datetime(2026, 10, 21, 16, 30)  # 周三、扫描窗口内


class FakeAlertRepo:
    def __init__(self):
        self.seen = set()

    def record(self, symbol, title, words, tier):
        key = (symbol, title)
        if key in self.seen:
            return None
        self.seen.add(key)
        return {'id': len(self.seen)}


class FakePositions:
    def get_all_positions(self, account):
        return [SimpleNamespace(symbol='600519.SH', shares_total=100)]


class FakeBridge:
    def __init__(self, boom=False):
        self.alerts = []
        self.boom = boom

    def dispatch(self, alerts):
        if self.boom:
            raise RuntimeError('bridge down')
        self.alerts.extend(alerts)
        return {'created': [1], 'skipped': [], 'errors': []}


def _news_service(bridge, titles=('某公司被立案调查',), tier_words=('立案',)):
    svc = NewsWatchService(
        news_source=object(), alert_repo=FakeAlertRepo(), position_repo=FakePositions(),
        accounts=('agent_virtual',), sender=lambda payload: True, bridge=bridge,
        interval_sec=0)
    svc._fetch_news = lambda symbol, limit=15: [
        {'title': titles[0], 'time': NOW.strftime('%Y-%m-%d %H:%M:%S')}]
    return svc


def test_critical_news_calls_bridge():
    bridge = FakeBridge()
    svc = _news_service(bridge)
    out = svc.scan(now=NOW)

    assert out['scanned'] is True
    assert bridge.alerts, 'critical 命中必须交给桥'
    alert = bridge.alerts[0]
    assert alert['symbol'] == '600519'
    assert alert['tier'] == 'critical'
    assert alert['account'] == 'agent_virtual'
    assert alert['words'] == ['立案']


def test_soft_news_does_not_call_bridge():
    bridge = FakeBridge()
    svc = _news_service(bridge, titles=('某公司发布业绩预告',))
    svc.scan(now=NOW)
    assert bridge.alerts == []


def test_bridge_failure_does_not_break_scan():
    bridge = FakeBridge(boom=True)
    svc = _news_service(bridge)
    out = svc.scan(now=NOW)
    assert out['scanned'] is True and out['reported'] == 1


def test_news_without_bridge_keeps_old_behavior():
    svc = NewsWatchService(
        news_source=object(), alert_repo=FakeAlertRepo(), position_repo=FakePositions(),
        accounts=('agent_virtual',), sender=lambda payload: True, interval_sec=0)
    svc._fetch_news = lambda symbol, limit=15: [
        {'title': '某公司被立案调查', 'time': NOW.strftime('%Y-%m-%d %H:%M:%S')}]
    out = svc.scan(now=NOW)
    assert out['reported'] == 1


def _policy_service(bridge):
    return PolicyWatchService(
        news_source=object(), position_repo=FakePositions(), accounts=('agent_virtual',),
        alert_repo=FakeAlertRepo(), sender=lambda payload: True, bridge=bridge,
        now_fn=lambda: NOW)


def test_policy_critical_calls_bridge():
    bridge = FakeBridge()
    svc = _policy_service(bridge)
    svc._dispatch_alerts([{'symbol': '600519.SH', 'title': '某行业被限制',
                           'tier': 'critical', 'words': ['限制'],
                           'sectors': ['半导体']}], NOW)
    assert bridge.alerts and bridge.alerts[0]['symbol'] == '600519.SH'
    assert bridge.alerts[0]['source'] == 'policy'


def test_policy_soft_does_not_call_bridge():
    bridge = FakeBridge()
    svc = _policy_service(bridge)
    svc._dispatch_alerts([{'symbol': '600519.SH', 'title': '某行业会议召开',
                           'tier': 'soft', 'words': ['会议']}], NOW)
    assert bridge.alerts == []
