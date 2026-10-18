"""action_params 结构校验（REQ-261016155500-4f2a，2026-10-16）

领域纯函数测试：validate_action_params 的枚举/数值/字符串约束与 observe 强制判据。
"""
import pytest

from qs_watch.domain.watch.models import ACTION_PARAM_ACTIONS, validate_action_params


def test_none_and_non_dict():
    assert validate_action_params(None) is None
    assert validate_action_params('buy') is not None
    assert validate_action_params([1]) is not None


def test_action_enum():
    assert validate_action_params({'action': 'buy'}) is None
    assert validate_action_params({'action': 'sell'}) is None
    assert validate_action_params({'action': 'hold'}) is None
    assert validate_action_params({'action': 'reduce'}) is None
    assert validate_action_params({'action': 'observe', 'observation_criterion': '放量'}) is None
    assert 'action' in validate_action_params({'action': 'buy_now'})


def test_action_enum_matches_export():
    assert set(ACTION_PARAM_ACTIONS) == {'buy', 'sell', 'hold', 'reduce', 'observe'}


def test_numeric_fields():
    assert validate_action_params({'reference_price': '12.5'}) is not None
    assert validate_action_params({'position_pct': 0}) is not None
    assert validate_action_params({'position_pct': 101}) is not None
    assert validate_action_params({'position_pct': 50.0}) is None
    assert validate_action_params({'quantity': 0}) is not None
    assert validate_action_params({'quantity': 1.5}) is not None
    assert validate_action_params({'quantity': 200}) is None


def test_string_fields():
    assert validate_action_params({'invalidation': 5}) is not None
    assert validate_action_params({'observation_criterion': ['x']}) is not None
    assert validate_action_params({'invalidation': '跌破 25 重估'}) is None


def test_observe_requires_criterion():
    err = validate_action_params({'action': 'observe'})
    assert err is not None and 'observation_criterion' in err
    assert validate_action_params({'action': 'observe',
                                   'observation_criterion': '跌破后 30 分钟未收回'}) is None
