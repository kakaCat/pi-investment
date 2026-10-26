"""metrics 扩展测试（REQ-261022022657-857f t5 · FR-4）"""
from datetime import datetime

from adapters.inbound.fastapi_app.routes.watch_metrics_async import build_metrics

NOW = datetime(2026, 10, 22, 16, 0)


class FakeStore:
    def load_meta(self):
        return {'heartbeat_at': NOW}


def test_fields_present_with_injected_counts():
    out = build_metrics(now=NOW, store=FakeStore(), todo_repo=None,
                        rule_noise_repo=None,
                        counts_provider=lambda now: {
                            'news_todos_today': 3, 'reflection_woken_today': 2})
    assert out['news_todos_today'] == 3
    assert out['reflection_woken_today'] == 2


def test_unknown_counts_are_null_not_zero():
    out = build_metrics(now=NOW, store=FakeStore(), todo_repo=None,
                        rule_noise_repo=None, counts_provider=lambda now: {})
    assert out['news_todos_today'] is None
    assert out['reflection_woken_today'] is None


def test_provider_failure_degrades_quietly():
    def boom(now):
        raise RuntimeError('db down')

    out = build_metrics(now=NOW, store=FakeStore(), todo_repo=None,
                        rule_noise_repo=None, counts_provider=boom)
    assert out['news_todos_today'] is None
    assert any('plan_closure_counters_failed' in d for d in out['degraded'])
