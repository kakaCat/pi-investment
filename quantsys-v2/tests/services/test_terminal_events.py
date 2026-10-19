"""终结事件引擎自动归宿（2026-10-19 用户裁定：过期的由引擎处理）

- C1：exit_stop 触发 → 规则自动退役（使命完成，线已消费）
- C3/C4：持仓联动覆盖 user_main/agent_brain（不再只 agent_virtual）
- C5：expires_at 到期 → 显式收摊注记
- D2：连续 3 交易日取数失败 → 停牌/退市治理项
- F1：持仓均价 vs 规则成本偏差 >2% → 自动同步
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.engine import WatchEngine
from qs_watch.application.services.watch_engine.position_lifecycle_service import (
    PositionLifecycleService,
)

NOW = datetime(2026, 10, 19, 10, 0)


def _rule(rid=128, intent='exit_stop', **over):
    base = dict(
        id=rid, symbol='000425',
        conditions=[{'type': 'price_break',
                     'params': {'direction': 'below', 'price': 8.0},
                     'cooldown_sec': 1800}],
        cost_price=9.0, active_window=None, intent=intent,
        action_hint={'trigger_level': 'L2', 'action_on_trigger': 'sell'},
        escalation_policy=None, scope='symbol', linked_account='user_main_simulation',
        lifecycle_stage='holding', created_from=None, next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
        action_params=None, ops_notes=[],
    )
    base.update(over)
    return SimpleNamespace(**base)


class _Repo:
    def __init__(self, rule):
        self.rule = rule
        self.updated = []

    def list_enabled(self):
        return [self.rule]

    def list_rules(self, enabled=None):
        return [self.rule]

    def update_fields(self, rule_id, **fields):
        self.updated.append(fields)
        for k, v in fields.items():
            setattr(self.rule, k, v)
        return self.rule


class _Quotes:
    def __init__(self, price=7.14, prev_close=8.2):
        self.price, self.prev_close = price, prev_close

    def get_realtime_quote(self, symbol):
        return SimpleNamespace(symbol=symbol, price=self.price,
                               prev_close=self.prev_close,
                               volume=1e6, change_pct=None)


class _Notifier:
    def __init__(self):
        self.sent = []
        self.governance = []

    def notify(self, rule, condition, quote, result, **kw):
        self.sent.append(kw.get('disposition'))
        return SimpleNamespace(id=len(self.sent), notified=True)

    def record_governance(self, rule, reason, detail=None):
        self.governance.append({'rule_id': rule.id, 'reason': reason, 'detail': detail})
        return SimpleNamespace(id=len(self.governance))


# ── C1：止损触发自动退役 ─────────────────────────────────────────

def test_user_account_stop_not_retired():
    """user_main 账户止损触发：规则保持原样（2026-10-19 用户裁定"拿着，不应该
    修改规则"），只落治理注记请 agent 来确认。"""
    rule = _rule()   # linked_account=user_main_simulation
    repo = _Repo(rule)
    notifier = _Notifier()
    engine = WatchEngine(rule_repo=repo, quote_service=_Quotes(), notifier=notifier,
                         now_fn=lambda: NOW)
    engine.tick()
    assert rule.enabled is True
    assert rule.lifecycle_stage == 'holding'
    assert len(notifier.governance) == 1
    assert '规则保持原样不改动' in notifier.governance[0]['reason']


def test_agent_account_stop_retires_rule():
    """agent 自有账户止损触发：引擎自动退役（线破=使命完成）。"""
    rule = _rule(linked_account='agent_brain', account='agent_brain')
    repo = _Repo(rule)
    notifier = _Notifier()
    engine = WatchEngine(rule_repo=repo, quote_service=_Quotes(), notifier=notifier,
                         now_fn=lambda: NOW)
    engine.tick()
    assert rule.enabled is False
    assert rule.lifecycle_stage == 'closed'
    assert any('止损已触发' in (n.get('text') or '') for n in rule.ops_notes)


def test_exit_reduce_does_not_retire():
    rule = _rule(intent='exit_reduce')
    repo = _Repo(rule)
    notifier = _Notifier()
    engine = WatchEngine(rule_repo=repo, quote_service=_Quotes(), notifier=notifier,
                         now_fn=lambda: NOW)
    engine.tick()
    assert rule.enabled is True            # 减仓档不退役（剩余仓位还要盯）


# ── C3/C4：账户范围扩展（factory 装配）────────────────────────────

def test_factory_covers_user_and_agent_accounts():
    import inspect
    from qs_watch.application.services.watch_engine import factory
    src = inspect.getsource(factory)
    assert '"agent_virtual", "agent_brain", "user_main_simulation"' in src


def test_lifecycle_reconcile_covers_user_main():
    """user_main 清仓后，卖出规则族应收摊（此前只盯 agent_virtual → #128 病根）。"""
    rule = _rule(intent='exit_stop', enabled=True, account='user_main_simulation')
    repo = _Repo(rule)

    class _Pos:
        def get_all_positions(self, account):
            return []          # 无持仓 = 已清仓

    svc = PositionLifecycleService(
        rule_repo=repo, position_repo=_Pos(),
        accounts=("agent_virtual", "agent_brain", "user_main_simulation"))
    out = svc.reconcile(NOW)
    assert out['retired'] == 1
    assert rule.enabled is False


# ── C5：到期收摊注记 ─────────────────────────────────────────────

def test_expired_rule_gets_closed_with_note():
    rule = _rule(enabled=True, expires_at=NOW - timedelta(days=1))
    repo = _Repo(rule)
    svc = PositionLifecycleService(rule_repo=repo)
    n = svc.expire_overdue_rules(NOW)
    assert n == 1
    assert rule.enabled is False
    assert rule.lifecycle_stage == 'closed'
    assert any('到期收摊' in (x.get('text') or '') for x in rule.ops_notes)


# ── D2：停牌/退市检测 ────────────────────────────────────────────

class _DeadQuotes:
    def get_realtime_quote(self, symbol):
        return None


def test_halt_detection_governance_after_3_days():
    rule = _rule(intent='trend_observe',
                 action_hint={'trigger_level': 'L1', 'action_on_trigger': 'observe'})
    repo = _Repo(rule)
    notifier = _Notifier()
    clock = {'now': NOW}
    engine = WatchEngine(rule_repo=repo, quote_service=_DeadQuotes(),
                         notifier=notifier, now_fn=lambda: clock['now'])
    engine.tick()                                   # 第 1 天
    assert notifier.governance == []
    clock['now'] = NOW + timedelta(days=1)
    engine.tick()                                   # 第 2 天
    assert notifier.governance == []
    clock['now'] = NOW + timedelta(days=2)
    engine.tick()                                   # 第 3 天 → 治理项
    assert len(notifier.governance) == 1
    assert '停牌' in notifier.governance[0]['reason']
    assert notifier.governance[0]['detail']['suspected_halt'] is True


# ── F1：成本同步 ─────────────────────────────────────────────────

def test_cost_sync_updates_rule_cost():
    rule = _rule(cost_price=9.0)
    repo = _Repo(rule)
    svc = PositionLifecycleService(rule_repo=repo)
    note = svc._sync_cost_price(rule, {'avg_cost': 8.0, 'account': 'user_main_simulation'})
    assert note is not None and '成本同步' in note
    assert float(rule.cost_price) == 8.0
    assert any('持仓均价' in (x.get('text') or '') for x in rule.ops_notes)


def test_cost_sync_skips_small_deviation():
    rule = _rule(cost_price=8.05)
    svc = PositionLifecycleService(rule_repo=_Repo(rule))
    assert svc._sync_cost_price(rule, {'avg_cost': 8.0}) is None   # 0.6% < 2%
