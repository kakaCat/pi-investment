"""WatchRuleRepository 集成测试（使用 quant_test 库）"""
import pytest
from datetime import datetime, timedelta

from adapters.outbound.repositories.watch_rule_repository import (
    WatchRuleRepository, WatchTriggerRepository, rule_to_dict,
)


@pytest.mark.integration
class TestWatchRuleRepository:
    def setup_method(self):
        self.repo = WatchRuleRepository()
        self.trigger_repo = WatchTriggerRepository()
        self._created_ids = []
        self._created_trigger_ids = []

    def teardown_method(self):
        for tid in self._created_trigger_ids:
            self.trigger_repo.delete_by_id(tid)
        for rid in self._created_ids:
            self.repo.delete_by_id(rid)

    def _make_rule(self, symbol='600519.SH'):
        rule = self.repo.create_rule(
            symbol=symbol,
            conditions=[{'type': 'price_break', 'params': {'direction': 'above', 'price': 1800.0}}],
            context='测试规则',
            cost_price=1700.0,
            created_by='test',
        )
        self._created_ids.append(rule.id)
        return rule

    def test_create_and_get(self):
        rule = self._make_rule()
        fetched = self.repo.get_by_id(rule.id)
        assert fetched is not None
        assert fetched.symbol == '600519.SH'
        assert fetched.enabled is True
        assert fetched.conditions[0]['type'] == 'price_break'
        assert float(fetched.cost_price) == 1700.0

    def test_rule_to_dict_serialization(self):
        rule = self._make_rule()
        d = rule_to_dict(rule)
        assert set(d.keys()) == {
            'id', 'symbol', 'enabled', 'conditions', 'context', 'cost_price',
            'active_window', 'expires_at', 'created_by', 'created_at', 'updated_at',
        }
        assert isinstance(d['cost_price'], float)
        assert d['cost_price'] == 1700.0
        assert isinstance(d['created_at'], str) and 'T' in d['created_at']
        assert isinstance(d['updated_at'], str) and 'T' in d['updated_at']

    def test_list_enabled_excludes_disabled_and_expired(self):
        active = self._make_rule('000001.SZ')
        disabled = self._make_rule('000002.SZ')
        self.repo.update_fields(disabled.id, enabled=False)
        expired = self._make_rule('000003.SZ')
        self.repo.update_fields(expired.id, expires_at=datetime.now() - timedelta(days=1))

        enabled_ids = {r.id for r in self.repo.list_enabled()}
        assert active.id in enabled_ids
        assert disabled.id not in enabled_ids
        assert expired.id not in enabled_ids

    def test_update_fields(self):
        rule = self._make_rule()
        updated = self.repo.update_fields(rule.id, context='新理由', enabled=False)
        assert updated.context == '新理由'
        assert updated.enabled is False

    def test_record_trigger(self):
        rule = self._make_rule()
        trigger = self.trigger_repo.record(
            rule_id=rule.id, symbol=rule.symbol,
            condition={'type': 'price_break', 'params': {'direction': 'above', 'price': 1800.0}},
            trigger_price=1801.5,
            detail={'value': 1801.5, 'message': '上破 1800.0'},
            notified=True,
        )
        assert trigger.id is not None
        self._created_trigger_ids.append(trigger.id)
        rows = self.trigger_repo.list_by_symbol(rule.symbol, limit=10)
        assert any(t.id == trigger.id for t in rows)
