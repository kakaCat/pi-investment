"""WatchRuleRepository 集成测试（使用 quant_test 库）"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import text

from adapters.outbound.repositories import watch_rule_repository as wrr
from adapters.outbound.repositories.watch_rule_repository import (
    POSITION_STATE_HOLDING, POSITION_STATE_NONE, WatchRule,
    WatchRuleRepository, WatchTriggerRepository, rule_interval_sec,
    rule_position_state, rule_to_dict,
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
        # 2026-09-11 修正（w-c8cae280）：本断言自 09-02 起即红灯——rule_to_dict 在此期间
        # 新增了 account / notify_mode / action_hint / escalation_policy（b176c3ca、3116f6d4），
        # 属契约扩展（分层通知与账户归属），测试未同步。补全键集合，恢复契约守护作用。
        # 2026-09-11（w-c8cae280 / REQ-f08def P1）：rule_to_dict 增价值生命周期字段与
        # value_ledger（intent/lifecycle_stage/scope/target/linked_account/created_from/
        # next_action_hint/last_reviewed_at/review_interval_days/review_due_at/value_ledger）。
        # 没有这些字段，agent 拿到触发不知道该回答什么问题（RFC 014 v3 §7.1）。
        # 2026-10-16（REQ-261016155500-4f2a）：增 action_params / ops_notes——
        # 决策化改造的结构化操作指引与机器注记（见迁移 20261016_watch_rules_upgrade.py）。
        # 2026-10-21（RFC 017）：增 position_state / interval_sec——持仓状态显式化与
        # 规则级盯盘频率（见迁移 20261021_watch_rules_position_interval.py）。
        # 2026-10-23：增 watch_tier——盯盘 V2 定时任务档位（30/600/1800 秒，
        # 见迁移 20261023_watch_rules_tier.py）。
        assert set(d.keys()) == {
            'id', 'symbol', 'enabled', 'conditions', 'context', 'cost_price',
            'active_window', 'expires_at', 'created_by', 'created_at', 'updated_at',
            'account', 'notify_mode', 'action_hint', 'escalation_policy',
            'intent', 'lifecycle_stage', 'scope', 'target', 'linked_account',
            'created_from', 'next_action_hint', 'last_reviewed_at',
            'review_interval_days', 'review_due_at', 'value_ledger',
            'action_params', 'ops_notes',
            'position_state', 'interval_sec', 'watch_tier',
            'plan_id',
            # 2026-10-22 三分支：生命周期状态 + 失效留痕 + 确认直通计数 + agent 设定的失效阈值
            'rule_state', 'invalid_reason', 'invalid_at', 'confirm_count',
            'invalidation_threshold_pct', 'invalid_escalated_at',
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

    # ── 每日循环重置范围（2026-10-23 用户裁定：活跃的才重置）──────────────

    def _seed_cycle_state(self, rule_id, count=5, state='processed'):
        from sqlalchemy import update as sa_update
        self.repo.session.execute(
            sa_update(WatchRule).where(WatchRule.id == rule_id)
            .values(cycle_count=count, process_state=state))
        self.repo.session.commit()

    def _cycle_state(self, rule_id):
        # 裸 SQL 读回：绕开 ORM identity map（Core UPDATE 不会让已加载对象失效）
        row = self.repo.session.execute(
            text('select cycle_count, process_state from quant.watch_rules '
                 'where id = :id'), {'id': rule_id}).first()
        return (row[0], row[1]) if row else None

    def test_reset_active_cycles_only_touches_active_rules(self):
        """2026-10-23 用户裁定：每日重置只重置**活跃规则**。

        活跃 = rule_state='active' 且启用且未过期（与引擎判定集合同源）；
        非活跃（invalid/archived/停用/过期）不进判定，重置它们没有意义，
        还会把失效待裁决等状态一并抹掉。
        """
        active = self._make_rule('600001.SH')
        disabled = self._make_rule('600002.SH')
        self.repo.update_fields(disabled.id, enabled=False)
        archived = self._make_rule('600003.SH')
        self.repo.update_fields(archived.id, rule_state='archived')
        invalid = self._make_rule('600004.SH')
        self.repo.update_fields(invalid.id, rule_state='invalid')
        expired = self._make_rule('600005.SH')
        self.repo.update_fields(expired.id, expires_at=datetime.now() - timedelta(days=1))

        for rule in (active, disabled, archived, invalid, expired):
            self._seed_cycle_state(rule.id)

        reset_count = self.repo.reset_active_cycles()

        assert reset_count >= 1, '至少本用例创建的活跃规则被重置'
        assert self._cycle_state(active.id) == (0, 'pending')
        for rule in (disabled, archived, invalid, expired):
            assert self._cycle_state(rule.id) == (5, 'processed'), (
                f'非活跃规则 {rule.id} 不应被重置（只重置活跃规则）')

    def test_reset_all_cycles_alias_is_active_only(self):
        """旧名 reset_all_cycles 保留，但语义已收窄为活跃规则。"""
        active = self._make_rule('600006.SH')
        self._seed_cycle_state(active.id)

        assert self.repo.reset_all_cycles() >= 1
        assert self._cycle_state(active.id) == (0, 'pending')

    def test_update_fields(self):
        rule = self._make_rule()
        updated = self.repo.update_fields(rule.id, context='新理由', enabled=False)
        assert updated.context == '新理由'
        assert updated.enabled is False

    def test_update_fields_action_params_and_ops_notes(self):
        # REQ-261016155500-4f2a：决策化新列经 update_fields 白名单可写、可落库、可回读。
        rule = self._make_rule()
        updated = self.repo.update_fields(
            rule.id,
            action_params={'action': 'sell', 'reference_price': 26.5,
                           'position_pct': 50, 'invalidation': '放量跌破25.8'},
            ops_notes=[{'at': '2026-10-16T00:00:00+00:00', 'by': 'test', 'text': '注记'}],
        )
        assert updated.action_params['action'] == 'sell'
        assert updated.action_params['position_pct'] == 50
        assert updated.ops_notes[0]['by'] == 'test'
        fetched = self.repo.get_by_id(rule.id)
        assert fetched.action_params['action'] == 'sell'
        assert fetched.ops_notes[0]['text'] == '注记'

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


# ── RFC 017（2026-10-21）：position_state / interval_sec 读写与兼容语义 ──────────

class TestWatchRuleNewColumns:
    """两列经仓储读写、NULL/缺列 fail-open 的口径（迁移细节见

    test_watch_rule_columns_migration.py）。
    """

    def setup_method(self):
        self.repo = WatchRuleRepository()
        self._created_ids = []

    def teardown_method(self):
        for rid in self._created_ids:
            self.repo.delete_by_id(rid)

    def _make_rule(self, **kwargs):
        kwargs.setdefault('symbol', '600519.SH')
        kwargs.setdefault('conditions', [{'type': 'price_break',
                                          'params': {'direction': 'above', 'price': 1800.0}}])
        kwargs.setdefault('created_by', 'test')
        rule = self.repo.create_rule(**kwargs)
        assert rule is not None, '规则创建失败（DB 不可用或守卫拒绝）'
        self._created_ids.append(rule.id)
        return rule

    # ── 默认值与写读往返 ─────────────────────────────────────────────────
    def test_new_rule_defaults_to_none_state_and_no_interval(self):
        rule = self._make_rule()
        # 不传就不写：position_state 由 DB 默认 'none' 兜住；interval_sec 保持 NULL
        assert rule.position_state == POSITION_STATE_NONE
        assert rule.interval_sec is None
        d = rule_to_dict(rule)
        assert d['position_state'] == POSITION_STATE_NONE
        assert d['interval_sec'] is None

    def test_create_rule_accepts_new_fields(self):
        rule = self._make_rule(symbol='601318.SH', account='agent_virtual',
                               linked_account='agent_virtual',
                               intent='trend_observe',
                               position_state='holding', interval_sec=20)
        assert rule.position_state == POSITION_STATE_HOLDING
        assert rule.interval_sec == 20
        fetched = self.repo.get_by_id(rule.id)
        assert fetched.position_state == POSITION_STATE_HOLDING
        assert fetched.interval_sec == 20

    def test_update_fields_writes_new_fields_and_null_resets(self):
        rule = self._make_rule()
        updated = self.repo.update_fields(rule.id, position_state='holding', interval_sec=30)
        assert updated.position_state == POSITION_STATE_HOLDING
        assert updated.interval_sec == 30
        fetched = self.repo.get_by_id(rule.id)
        assert fetched.position_state == POSITION_STATE_HOLDING
        assert fetched.interval_sec == 30
        # interval_sec=None = 显式恢复"跟随全局档"
        assert self.repo.update_fields(rule.id, interval_sec=None).interval_sec is None
        # position_state=None 写入口径归一为 'none'（列是 NOT NULL，不存在"清空成 NULL"）
        assert self.repo.update_fields(rule.id, position_state=None).position_state == POSITION_STATE_NONE

    def test_update_fields_rejects_invalid_new_values(self):
        rule = self._make_rule()
        with pytest.raises(ValueError):
            self.repo.update_fields(rule.id, position_state='halfway')
        with pytest.raises(ValueError):
            self.repo.update_fields(rule.id, interval_sec=0)
        with pytest.raises(ValueError):
            self.repo.update_fields(rule.id, interval_sec='abc')
        # 拒绝后不落库（状态仍是默认值）
        fetched = self.repo.get_by_id(rule.id)
        assert fetched.position_state == POSITION_STATE_NONE
        assert fetched.interval_sec is None

    def test_set_helpers_roundtrip(self):
        rule = self._make_rule()
        assert self.repo.set_position_state(rule.id, POSITION_STATE_HOLDING).position_state == POSITION_STATE_HOLDING
        assert self.repo.set_position_state(rule.id, None).position_state == POSITION_STATE_NONE
        assert self.repo.set_interval_sec(rule.id, '45').interval_sec == 45
        assert self.repo.set_interval_sec(rule.id, None).interval_sec is None

    # ── NULL / 未知值 = 状态不可知（fail-open 旧行为）────────────────────
    def test_null_and_unknown_state_read_as_unknown(self):
        # 纯内存对象：模拟迁移前/库被回滚后 ORM 读到的 NULL
        rule = WatchRule(symbol='600519.SH', conditions=[])
        assert rule.position_state is None
        assert rule_interval_sec(rule) is None
        # None ≠ 'none'：前者是"状态不可知"，消费方须 fail-open
        assert rule_position_state(rule) is None
        rule.position_state = POSITION_STATE_NONE
        assert rule_position_state(rule) == POSITION_STATE_NONE
        rule.position_state = 'legacy_garbage'
        assert rule_position_state(rule) is None
        rule.interval_sec = -5
        assert rule_interval_sec(rule) is None
        rule.interval_sec = 15
        assert rule_interval_sec(rule) == 15

    # ── 缺列兼容（迁移未落库 / 已回滚）───────────────────────────────────
    def test_missing_columns_keeps_legacy_behaviour(self, monkeypatch):
        """列不存在时：读写不炸、旧字段照常、新字段按"不可知"处理（不伪造成 none）。"""
        monkeypatch.setattr(wrr.WatchRuleRepository, '_new_columns_available',
                            lambda self: False)
        try:
            rule = self._make_rule(symbol='601398.SH', position_state='holding',
                                   interval_sec=15)
            # 新字段被忽略，内存对象给出"状态不可知"（None），而不是伪装成 none
            assert rule.position_state is None
            assert rule.interval_sec is None
            # DB 侧由 DEFAULT 兜住（旧行为：没有状态概念）
            raw_state = self.repo.session.execute(
                text('SELECT position_state FROM quant.watch_rules WHERE id = :i'),
                {'i': rule.id}).scalar()
            assert raw_state == 'none'

            # 列表/读取路径不触发 UndefinedColumn，新字段仍为 None
            rows = self.repo.list_rules(symbol='601398.SH')
            assert rows and rows[0].id == rule.id
            assert rows[0].position_state is None
            assert self.repo.list_enabled() is not None
            assert rule_to_dict(rows[0])['position_state'] is None

            # 旧字段照常更新；新字段被丢弃（不写库、不报错）
            updated = self.repo.update_fields(rule.id, context='legacy-update',
                                              position_state='holding', interval_sec=9)
            assert updated is not None
            assert updated.context == 'legacy-update'
            assert updated.position_state is None
            assert updated.interval_sec is None
            raw = self.repo.session.execute(
                text('SELECT context, interval_sec FROM quant.watch_rules WHERE id = :i'),
                {'i': rule.id}).fetchone()
            assert raw[0] == 'legacy-update'
            assert raw[1] is None
        finally:
            monkeypatch.undo()

    def test_column_cache_can_be_reset(self):
        # 迁移在运行中落地时，清缓存即可让仓储改走新列路径
        wrr.reset_watch_rules_column_cache()
        assert self.repo._new_columns_available() is True


class TestWatchTierColumn:
    """2026-10-23：盯盘 V2 档位列（30/600/1800 秒）。"""

    def test_normalize_watch_tier_accepts_three_values(self):
        from adapters.outbound.repositories.watch_rule_repository import (
            normalize_watch_tier,
        )

        assert normalize_watch_tier(30) == 30
        assert normalize_watch_tier('600') == 600
        assert normalize_watch_tier(1800) == 1800

    def test_normalize_watch_tier_rejects_others(self):
        import pytest
        from adapters.outbound.repositories.watch_rule_repository import (
            normalize_watch_tier,
        )

        for bad in (45, 0, -30, None, True, 'abc'):
            with pytest.raises(ValueError):
                normalize_watch_tier(bad)

    def test_update_fields_writes_watch_tier(self):
        from adapters.outbound.repositories.watch_rule_repository import (
            WatchRuleRepository,
        )

        repo = WatchRuleRepository()
        rule = repo.create_rule(symbol='000007.SZ', conditions=[
            {'type': 'price_break', 'params': {'price': 10.0, 'direction': 'above'}}],
            watch_tier=600)
        try:
            assert rule.watch_tier == 600
            updated = repo.update_fields(rule.id, watch_tier=1800)
            assert updated is not None and updated.watch_tier == 1800
        finally:
            repo.update_fields(rule.id, rule_state='archived')
