"""集成：定时任务编排层 × 真实规则仓储（走 quant_test 库）。

单测（packages/qs_watch/tests/v2/test_scheduled.py）用的是 fake 仓储；本文件验证
真实 ORM 路径：`watch_tier` 落库、按档位过滤查询、距离变化回写。

行情用 fake（不打网络）；判定引擎用 fake（判定链本身已有 V2 单测覆盖）。
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
from qs_watch.application.services.watch_engine.v2 import scheduled, tier

TRADING_AM = datetime(2026, 10, 23, 10, 0, 0)


class FakeQuoteService:
    def __init__(self, price):
        self.price = price

    def get_realtime_quote(self, symbol):
        return SimpleNamespace(price=self.price, prev_close=None)


class FakeEngine:
    def __init__(self):
        self.rules = None

    def run_chain(self, rules, quotes):
        self.rules = list(rules)
        return []


class FakeTriggerRepo:
    def record(self, **kwargs):  # pragma: no cover - 本文件不触发命中
        return SimpleNamespace(id=1)


def _make(repo, symbol, tier_sec):
    return repo.create_rule(
        symbol=symbol,
        conditions=[{'type': 'price_break',
                     'params': {'price': 10.0, 'direction': 'above'}}],
        watch_tier=tier_sec,
    )


@pytest.fixture
def trading(monkeypatch):
    monkeypatch.setattr(scheduled, 'is_trading_day', lambda now=None: True)


def test_open_scan_persists_new_tier(trading):
    repo = WatchRuleRepository()
    rule = _make(repo, '000009.SZ', tier.TIER_FAST)   # 触发价 10
    try:
        # 现价 20 → 距离 100% → 应改成 1800
        result = scheduled.open_scan(rule_repo=repo,
                                     quote_service=FakeQuoteService(20.0))
        assert result['tier_changed'] >= 1
        assert repo.get_by_id(rule.id).watch_tier == tier.TIER_SLOW
    finally:
        repo.update_fields(rule.id, rule_state='archived')


def test_scan_filters_by_tier_from_db(trading):
    repo = WatchRuleRepository()
    fast = _make(repo, '000010.SZ', tier.TIER_FAST)
    slow = _make(repo, '000011.SZ', tier.TIER_SLOW)
    engine = FakeEngine()
    try:
        scheduled.scan(tier.TIER_FAST, now=TRADING_AM, rule_repo=repo,
                       quote_service=FakeQuoteService(10.0), engine=engine,
                       trigger_repo=FakeTriggerRepo())
        # 只把 30 秒档的规则交给判定链（库里可能还有别的 30 秒档规则，
        # 这里断言本用例的两条：fast 在、slow 不在）
        ids = [r.id for r in engine.rules]
        assert fast.id in ids
        assert slow.id not in ids
        # 距离 0% → 保持 30 秒档（不无谓写库）
        assert repo.get_by_id(fast.id).watch_tier == tier.TIER_FAST
        assert repo.get_by_id(slow.id).watch_tier == tier.TIER_SLOW
    finally:
        repo.update_fields(fast.id, rule_state='archived')
        repo.update_fields(slow.id, rule_state='archived')
