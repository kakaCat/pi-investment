"""止损规则停用守卫（2026-10-20 用户裁定）：宪法级规则不许无理由停用

事故背景：300677 止损规则 #103 曾被静默停用，持仓浮亏 -19% 时保护网是断的，
且无法回答"何时、为何被关"。停用止损 = 拆保护网，必须留理由。

证伪清单：
  1) exit_stop 启用中 + 裸 enabled=False（无 ops_notes/context）→ 拒；
  2) 随附 ops_notes 或 context → 放行（既有程序化路径天然带 banner，不受影响）；
  3) 非宪法级规则裸停用 → 放行（守卫不扩大打击面）；
  4) 本就停用的规则重复停用（幂等重放）→ 放行；
  5) 自愈 retire 宪法级规则 → 拒（裸 SQL 旁路的同源拦截）；
  6) 自愈 retire 普通规则 → 放行。
"""
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.noise_self_heal_service import (
    NoiseSelfHealService,
)
from qs_watch.domain.watch.services.rule_guard import (
    ConstitutionalRuleSilentDisable, guard_disable_rule,
)


def _rule(intent='exit_stop', enabled=True):
    return SimpleNamespace(id=103, symbol='300677', intent=intent, enabled=enabled)


# ── 领域守卫 ────────────────────────────────────────────────

def test_silent_disable_constitutional_rejected():
    with pytest.raises(ConstitutionalRuleSilentDisable, match='无理由停用'):
        guard_disable_rule(_rule(), {'enabled': False})


def test_disable_with_reason_allowed():
    guard_disable_rule(_rule(), {'enabled': False,
                                 'ops_notes': [{'text': '止损已触发，使命完成'}]})
    guard_disable_rule(_rule(), {'enabled': False, 'context': '[止损已触发] ...'})


def test_non_constitutional_silent_disable_allowed():
    guard_disable_rule(_rule(intent='trend_observe'), {'enabled': False})
    guard_disable_rule(_rule(intent='entry'), {'enabled': False})


def test_idempotent_redisable_allowed():
    guard_disable_rule(_rule(enabled=False), {'enabled': False})


def test_non_disable_payloads_untouched():
    guard_disable_rule(_rule(), {'context': 'x'})          # 不涉及 enabled
    guard_disable_rule(_rule(), {'enabled': True})         # 启用不是停用


# ── 自愈旁路的同源拦截 ──────────────────────────────────────

def test_self_heal_retire_constitutional_rejected():
    svc = NoiseSelfHealService.__new__(NoiseSelfHealService)   # 纯方法，不需装配
    from qs_watch.domain.watch.ports import WatchRuleChangeInvalidKind
    with pytest.raises(WatchRuleChangeInvalidKind, match='宪法级止损'):
        svc._config_repair_after({'id': 103, 'intent': 'exit_stop'}, 'retire', None)


def test_self_heal_retire_normal_rule_allowed():
    svc = NoiseSelfHealService.__new__(NoiseSelfHealService)
    assert svc._config_repair_after({'id': 200, 'intent': 'trend_observe'},
                                    'retire', None) == {'enabled': False}
