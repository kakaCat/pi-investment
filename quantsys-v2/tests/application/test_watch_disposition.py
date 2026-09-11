"""处置状态机决策单测（REQ-f08def，2026-09-11，w-c8cae280）

守住两件容易回归的事：
1) 机械可判的触发**不得**被归成 escal（否则每条都唤醒 agent → token 成本失控，用户硬约束）
2) 去重键必须同标的同向归一（'601600.SH' 与 '601600' 是同一标的，否则 601600 六条规则
   会在一次跌穿里各通知一次）
"""
from types import SimpleNamespace

from application.services.watch_engine.disposition import (
    DISPOSITION_AUTO_OBSERVED, DISPOSITION_DEDUPED, DISPOSITION_ESCALATED,
    DISPOSITION_PENDING, dedup_key, decide, is_resolved, normalize_symbol,
)


def _rule(symbol='600150', level=None, action=None):
    ah = {}
    if level:
        ah['trigger_level'] = level
    if action:
        ah['action_on_trigger'] = action
    return SimpleNamespace(id=1, symbol=symbol, action_hint=ah or None)


def _cond(direction='below'):
    return {'type': 'price_break', 'params': {'price': 39.25, 'direction': direction}}


def test_normalize_symbol():
    assert normalize_symbol('601600.SH') == '601600'
    assert normalize_symbol('601600') == '601600'
    assert normalize_symbol(None) == ''


def test_dedup_key_unifies_symbol_forms():
    # 601600 六条规则跨窗口/跨账户：带后缀与不带后缀必须归到同一个键
    assert dedup_key(_rule('601600.SH'), _cond('below')) == dedup_key(_rule('601600'), _cond('below'))
    # 方向不同不合并（上破与下破是两件事）
    assert dedup_key(_rule('600150'), _cond('below')) != dedup_key(_rule('600150'), _cond('above'))


def test_observe_rule_is_mechanical_no_agent():
    d, reason = decide(_rule(level='L1', action='observe'), _cond())
    assert d == DISPOSITION_AUTO_OBSERVED
    assert '不唤醒 agent' in reason


def test_l2_rule_escalates():
    d, _ = decide(_rule(level='L2', action='buy'), _cond())
    assert d == DISPOSITION_ESCALATED


def test_escalation_flag_beats_action_hint():
    # escalation_policy 命中（L1→L2）时必须升级，即使规则声明 observe
    d, _ = decide(_rule(level='L1', action='observe'), _cond(), escalated=True)
    assert d == DISPOSITION_ESCALATED


def test_buy_sell_l1_stays_pending():
    d, reason = decide(_rule(level='L1', action='sell'), _cond())
    assert d == DISPOSITION_PENDING
    assert '需人工/agent 决策' in reason


def test_unknown_action_defaults_pending():
    d, _ = decide(_rule(), _cond())
    assert d == DISPOSITION_PENDING


def test_is_resolved_marks_terminal_states_only():
    assert is_resolved(DISPOSITION_AUTO_OBSERVED)
    assert is_resolved(DISPOSITION_DEDUPED)
    assert not is_resolved(DISPOSITION_PENDING)
    assert not is_resolved(DISPOSITION_ESCALATED)
    assert not is_resolved('legacy_unknown')


def test_engine_dedup_windows_constant_is_bounded():
    """去重窗不宜过大（会吞掉真实二次破位），也不宜过小（挡不住 0.46 秒重复）"""
    from application.services.watch_engine.disposition import DEDUP_WINDOW_SEC
    assert 5 <= DEDUP_WINDOW_SEC <= 300
