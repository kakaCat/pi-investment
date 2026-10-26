"""反思材料包组装单元测试（t10 · 四输入 + 段级 missing）"""
from datetime import date, datetime, timezone
from types import SimpleNamespace

from qs_plan.application.reflection_pack_service import ReflectionPackService


def _plan():
    return SimpleNamespace(id=5, account='a', status='active', spec={}, version=1,
                           stats={})


class FakeRepo:
    def __init__(self, versions=None, plan=None):
        self._versions = versions or []
        self._plan = plan or _plan()

    def get_plan(self, pid):
        return self._plan

    def list_versions(self, pid, limit=50):
        return self._versions


class FakeStats:
    def __init__(self, payload):
        self.payload = payload

    def blocked_stats(self, since_days=30, horizon=5):
        return self.payload


NOW = datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc)


def _svc(versions=None, blocked=None, trades=None):
    return ReflectionPackService(
        FakeRepo(versions),
        stats_repo=FakeStats(blocked or {'samples': 0}),
        trades_provider=(lambda pid: trades or []),
        now_fn=lambda: NOW)


class TestReflectionPack:
    def test_all_sections_ok(self):
        versions = [SimpleNamespace(version=2, change_reason='放宽止损',
                                    window_ends_at=date(2026, 11, 5), baseline={'pnl': 1})]
        blocked = {'samples': 3, 'decided': 2, 'blocked_right': 1, 'blocked_wrong': 1,
                   'undecidable': 1, 'wrong_rate': 0.5, 'avg_pct': 2.1}
        trades = [{'trade_id': 1, 'symbol': 'x', 'price': 10.0, 'realized_pnl': 120.0,
                   'trade_date': '2026-10-21'}]
        pack = _svc(versions, blocked, trades).build(5)
        assert [s['status'] for s in (pack['modifications'], pack['missed'],
                                      pack['wins'], pack['losses'])] == \
            ['ok', 'ok', 'ok', 'missing']
        assert set(pack['inputs_ready']) == {'modifications', 'missed', 'wins'}

    def test_missing_sections_marked_not_empty(self):
        pack = _svc().build(5)
        assert pack['modifications']['status'] == 'missing'
        assert pack['missed']['status'] == 'missing'
        assert pack['wins']['status'] == 'missing'
        assert pack['losses']['status'] == 'missing'
        assert pack['inputs_ready'] == []

    def test_losses_include_pnl_total(self):
        trades = [{'trade_id': 2, 'symbol': 'x', 'price': 10.0, 'realized_pnl': -300.0,
                   'trade_date': '2026-10-20'}]
        pack = _svc(trades=trades).build(5)
        assert pack['losses']['status'] == 'ok'
        assert pack['losses']['total_pnl'] == -300.0
