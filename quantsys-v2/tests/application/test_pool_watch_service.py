"""池级盯盘服务单测（2026-10-20 选池↔盯盘接线）"""
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.pool_watch_service import (
    PoolWatchService, binding_created_from,
)


def _member(sym, bp=None, sp=None, desc=None):
    return {'symbol': sym, 'name': sym, 'buy_point': bp, 'sell_point': sp,
            'description': desc, 'tags': []}


class _BindingRepo:
    def __init__(self):
        self.summaries = {}

    def list_bindings(self, enabled=None):
        return [B]

    def get_binding(self, bid):
        return B if bid == B['id'] else None

    def create_binding(self, **f):
        return dict(B, **f)

    def update_binding(self, bid, **f):
        return B

    def save_sync_summary(self, bid, s):
        self.summaries[bid] = s


class _PoolSource:
    def __init__(self, members):
        self._m = members

    def list_pools(self):
        return [{'id': 29, 'name': '科技成长', 'pool_type': 'static', 'n': len(self._m)}]

    def get_members(self, pool_id):
        return list(self._m)


class _RuleRepo:
    def __init__(self):
        self.rules = []
        self._seq = 100

    def list_rules(self, enabled=None):
        return [r for r in self.rules if (enabled is None or r.enabled)]

    def create_rule(self, symbol, conditions, **kw):
        self._seq += 1
        r = SimpleNamespace(id=self._seq, symbol=symbol, conditions=conditions,
                            enabled=True, created_from=None, intent=None,
                            linked_account=None, next_action_hint=None, **kw)
        self.rules.append(r)
        return r

    def update_fields(self, rid, **f):
        r = next(x for x in self.rules if x.id == rid)
        for k, v in f.items():
            setattr(r, k, v)
        return r


B = {'id': 1, 'pool_id': 29, 'pool_name': '科技成长',
     'conditions_template': None, 'use_member_points': True,
     'member_points_mode': 'breakout', 'intent': 'trend_observe',
     'account': None, 'cooldown_sec': 600, 'max_members': 100, 'enabled': True}


def _svc(members):
    repo = _RuleRepo()
    source = _PoolSource(members)
    svc = PoolWatchService(_BindingRepo(), source, repo)
    svc._source = source        # 测试可变成员用
    return svc


def test_members_become_rules_with_breakout_points():
    svc = _svc([_member('300750', bp=180.0, sp=220.0, desc='宁德建仓区')])
    out = svc.reconcile_binding(B)
    assert out['created'] == 1 and out['unchanged'] == 0
    rule = svc._rule_repo.rules[0]
    assert rule.created_from == binding_created_from(1)
    dirs = {(c['params']['price'], c['params']['direction']) for c in rule.conditions}
    assert dirs == {(180.0, 'above'), (220.0, 'below')}   # breakout 语义
    assert all(c.get('cooldown_sec') == 600 for c in rule.conditions)


def test_pullback_mode_flips_directions():
    b = dict(B, member_points_mode='pullback')
    svc = _svc([_member('300750', bp=180.0, sp=220.0)])
    svc.reconcile_binding(b)
    dirs = {(c['params']['price'], c['params']['direction'])
            for c in svc._rule_repo.rules[0].conditions}
    assert dirs == {(180.0, 'below'), (220.0, 'above')}


def test_member_removed_retires_rule():
    svc = _svc([_member('300750', bp=180.0)])
    svc.reconcile_binding(B)
    assert svc._rule_repo.rules[0].enabled is True
    svc._source._m = []                   # 成员清空（同一服务二次对账）
    out = svc.reconcile_binding(B)
    assert out['retired'] == 1
    assert svc._rule_repo.rules[0].enabled is False


def test_point_change_updates_conditions():
    svc = _svc([_member('300750', bp=180.0)])
    svc.reconcile_binding(B)
    svc._source._m = [_member('300750', bp=175.0)]   # 点位下调（同一服务二次对账）
    out = svc.reconcile_binding(B)
    assert out['updated'] == 1
    assert svc._rule_repo.rules[0].conditions[0]['params']['price'] == 175.0


def test_cap_refuses_oversize_pool():
    svc = _svc([_member('S%04d' % i) for i in range(150)])
    b = dict(B, max_members=100)
    with pytest.raises(RuntimeError):
        svc.reconcile_binding(b)


def test_trade_intent_requires_account():
    svc = _svc([])
    with pytest.raises(ValueError):
        svc.create_binding(**dict(B, id=2, intent='entry', account=None))


def test_template_conditions_stacked_on_points():
    b = dict(B, conditions_template=[{'type': 'ma_break',
                                      'params': {'days': 20, 'direction': 'below'}}])
    svc = _svc([_member('300750', bp=180.0)])
    svc.reconcile_binding(b)
    types = [c['type'] for c in svc._rule_repo.rules[0].conditions]
    assert types == ['price_break', 'ma_break']
