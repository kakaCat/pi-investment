"""消息→离场链回归（REQ-261022022657-857f t4 · FR-3）

⚠️ 结论先说：消息→P1 待办→唤醒这条链**已由 REQ-261021194640-69b8 实现**
（`news_todo_bridge.NewsTodoBridge` + 工厂装配 + 既有 3 个测试文件）。
本文件不重复实现，只做**端到端回归**：证明「critical + 持仓账户」经 TodoService
产出 P1/rule_change 待办（evidence.source=news）并触发 assigner（= 唤醒通道），
且同标的未收敛待办存在时不重复建单。
"""
from datetime import datetime
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.news_todo_bridge import NewsTodoBridge
from qs_watch.application.services.watch_engine.todo_service import TodoService

NOW = datetime(2026, 10, 22, 10, 30)


class FakeTodoRepo:
    def __init__(self):
        self.rows = []
        self._seq = 0

    def create(self, **fields):
        self._seq += 1
        row = SimpleNamespace(id=self._seq, terminal=None,
                              symbol=fields.get('symbol'),
                              action_kind=fields.get('action_kind'),
                              level=fields.get('level'),
                              evidence=fields.get('evidence'))
        self.rows.append(row)
        return row

    def list_pending(self, limit=500):
        return list(self.rows)


def _bridge(repo=None, assigned=None):
    repo = repo or FakeTodoRepo()

    def assigner(todo, *a, **kw):
        if assigned is not None:
            assigned.append(todo)
        return True

    svc = TodoService(repo, assigner=assigner)
    bridge = NewsTodoBridge(svc, todo_repo=repo, now_fn=lambda: NOW)
    return bridge, repo, svc


def _alert(symbol='600519', account='agent_brain', titles=None):
    return {
        'tier': 'critical',
        'symbol': symbol,
        'account': account,
        'titles': titles or ['公司收到监管处罚决定'],
        'words': ['处罚'],
        'source': 'news',
    }


class TestNewsExitLinkage:
    def test_critical_creates_p1_todo_and_wakes(self):
        assigned = []
        bridge, repo, _ = _bridge(assigned=assigned)
        out = bridge.dispatch([_alert()])
        assert len(out['created']) == 1
        row = repo.rows[0]
        assert row.level == 'P1' and row.action_kind == 'rule_change'
        assert row.evidence['source'] == 'news'
        assert row.evidence['titles'] == ['公司收到监管处罚决定']
        assert len(assigned) == 1, '建单后必须派工（= 既有唤醒通道）'

    def test_duplicate_open_todo_skipped(self):
        bridge, repo, _ = _bridge()
        first = bridge.dispatch([_alert()])
        second = bridge.dispatch([_alert()])
        assert len(first['created']) == 1
        assert second['created'] == []
        assert len(repo.rows) == 1

    def test_soft_tier_does_not_create(self):
        bridge, repo, _ = _bridge()
        alert = dict(_alert(), tier='soft')
        bridge.dispatch([alert])
        assert repo.rows == []

    def test_missing_symbol_skipped(self):
        bridge, repo, _ = _bridge()
        out = bridge.dispatch([dict(_alert(), symbol='')])
        assert repo.rows == [] and out['skipped']

    def test_scan_sends_critical_to_bridge(self):
        """扫描层接线：critical 命中会调到 bridge.dispatch（工厂已注入）。"""
        calls = []

        class Bridge:
            def dispatch(self, alerts):
                calls.extend(alerts)
                return {'created': [], 'skipped': [], 'errors': []}

        from qs_watch.application.services.watch_engine.news_watch_service import (
            NewsWatchService,
        )

        svc = NewsWatchService(
            news_source=SimpleNamespace(
                fetch_news=lambda sym, limit=15: [
                    {'title': '公司收到监管处罚决定', 'url': 'u1',
                     'time': NOW.isoformat()},
                ],
            ),
            alert_repo=SimpleNamespace(
                record=lambda *a, **kw: SimpleNamespace(id=1),
                reported_recently=lambda *a, **kw: False,
            ),
            position_repo=SimpleNamespace(
                get_all_positions=lambda account: [
                    SimpleNamespace(symbol='600519', shares_total=100),
                ],
            ),
            sender=lambda *a, **kw: True,
            interval_sec=0,
            bridge=Bridge(),
        )
        out = svc.scan(now=NOW)
        assert out['scanned'] is True
        assert calls and calls[0]['tier'] == 'critical'
        assert calls[0]['symbol'].startswith('600519')
