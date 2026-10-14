"""交易日门判据单测（REQ-261006093620-a315 · t-63bc0a / FR-1、FR-2、FR-5）

覆盖卡上验收：13 行策略真值表 + `future` 反例锁。

## 打桩纪律（本仓踩过的坑）

- 桩打在**被调函数所在模块**：`application.services.trading_day_gate.TradingDayGuard`
  （本模块用自己模块的全局名取值）。
- **零网络零 DB**：用假判定器替代真实日历链；真实日历/降级链本身由既有
  `tests/test_trading_day_guard.py`（47 条）与 `tests/test_trading_day_resolver.py` 覆盖。
  本文件只验"给定判定 → 策略取舍与注解"。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from application.services import trading_day_gate as gate_mod
from application.services.trading_day_gate import (
    KNOWN_POLICIES,
    POLICY_ALWAYS,
    POLICY_HOLIDAYS,
    POLICY_TRADING_DAYS,
    SOURCE_GATE_ERROR,
    is_non_trading_day,
    should_skip,
    skip_non_trading_day,
    verdict_info,
)
from application.services.trading_day_guard import TradingDayGuard as RealGuard

_DAY = date(2026, 10, 7)          # 2026 国庆休市窗口内的周三
_SATURDAY = date(2026, 10, 3)     # 周六（weekend）
_HOLIDAY = 'trading-calendar-holiday'
_TRADING = 'trading-calendar'


@dataclass(frozen=True)
class _Verdict:
    """`TradingDayVerdict` 的最小替身（只带门用到的五个字段）。"""

    day: date
    is_trading_day: bool
    source: str
    degraded: bool
    reason: str


class _Guard:
    def __init__(self, verdict: _Verdict) -> None:
        self._verdict = verdict

    def check(self, now=None):  # noqa: D102 - 替身
        return self._verdict


class _BoomGuard:
    """判定器自身异常（模拟 gate 之外的意外，如 import/属性错误）。"""

    @staticmethod
    def check(now=None):
        raise RuntimeError('boom')


def _install(monkeypatch, spec):
    """按 spec 安装假判定器。spec = ('boom',) 或 (is_trading_day, source, degraded)。"""
    if spec[0] == 'boom':
        monkeypatch.setattr(gate_mod, 'TradingDayGuard', _BoomGuard)
        return
    is_trading_day, source, degraded = spec
    day = _SATURDAY if source == 'weekend' else _DAY
    monkeypatch.setattr(
        gate_mod,
        'TradingDayGuard',
        _Guard(_Verdict(day, is_trading_day, source, degraded, 'stub')),
    )


#: (id, policy, 判定注解, 期望跳过) —— 与 design/test-cases.md §2 的 13 行逐行对应
CASES = [
    ('always_holiday', POLICY_ALWAYS, (False, _HOLIDAY, False), False),
    ('trading_days_holiday', POLICY_TRADING_DAYS, (False, _HOLIDAY, False), True),
    ('trading_days_weekend', POLICY_TRADING_DAYS, (False, 'weekend', False), True),
    ('trading_days_trading', POLICY_TRADING_DAYS, (True, _TRADING, False), False),
    ('trading_days_weekday_fallback', POLICY_TRADING_DAYS, (False, 'weekday_fallback', True), False),
    ('trading_days_unavailable', POLICY_TRADING_DAYS, (False, 'unavailable', True), False),
    ('trading_days_guard_boom', POLICY_TRADING_DAYS, ('boom',), False),
    ('trading_days_future', POLICY_TRADING_DAYS, (False, 'future', False), True),
    ('holidays_holiday', POLICY_HOLIDAYS, (False, _HOLIDAY, False), True),
    ('holidays_weekend_must_run', POLICY_HOLIDAYS, (False, 'weekend', False), False),
    ('holidays_trading', POLICY_HOLIDAYS, (True, _TRADING, False), False),
    ('holidays_holiday_degraded_must_run', POLICY_HOLIDAYS, (False, _HOLIDAY, True), False),
    ('unknown_policy_runs', 'holiday', (False, _HOLIDAY, False), False),
    ('none_policy_runs', None, (False, _HOLIDAY, False), False),
]


@pytest.mark.parametrize(
    'policy,spec,expected',
    [c[1:] for c in CASES],
    ids=[c[0] for c in CASES],
)
def test_should_skip_truth_table(monkeypatch, policy, spec, expected):
    """13 行真值表：策略 × 判定条件 → 跳过与否。

    其中 `holidays_weekend_must_run` 与 `holidays_holiday_degraded_must_run` 是本表的
    存在理由：其余各行都能靠"非交易日就跳"蒙对，只有这两行把
    「只跳法定节假日」与「降级优先于跳过」钉死（需求 D-6）。
    """
    _install(monkeypatch, spec)
    skip, info = should_skip(policy)
    assert skip is expected
    # 注解五键必须齐全（调用方要把它写进任务 result）
    assert set(info) >= {'day', 'is_trading_day', 'source', 'degraded', 'reason'}


def test_unknown_policy_marks_info_and_runs(monkeypatch):
    """未知策略 → 照跑，但必须响亮留痕（不许静默退化成 always）。"""
    _install(monkeypatch, (False, _HOLIDAY, False))
    skip, info = should_skip('holiday')  # 少个 s
    assert skip is False
    assert info['policy_unknown'] is True
    assert '未知策略' in info['reason']


def test_gate_error_source_is_gate_error(monkeypatch):
    """判定器抛异常 → 照跑且 source 标注为 gate-error（与 unavailable 同形，不谎报交易日）。"""
    _install(monkeypatch, ('boom',))
    skip, info = should_skip(POLICY_TRADING_DAYS)
    assert skip is False
    assert info['source'] == SOURCE_GATE_ERROR
    assert info['degraded'] is True


def test_should_skip_never_raises_even_if_verdict_info_breaks(monkeypatch):
    """最后一道兜底：verdict_info 自身炸了也不许把异常抛给调度线程。"""

    def _boom(now=None):
        raise RuntimeError('verdict exploded')

    monkeypatch.setattr(gate_mod, 'verdict_info', _boom)
    skip, info = should_skip(POLICY_TRADING_DAYS)
    assert skip is False
    assert info['source'] == SOURCE_GATE_ERROR


def test_known_policies_value_domain():
    """策略值域与 `quant.scheduler_tasks.trading_day_policy` 的 CHECK 约束同值域。"""
    assert KNOWN_POLICIES == {'always', 'trading-days', 'holidays'}


def test_compat_entrypoints_equal_trading_days(monkeypatch):
    """③ 的两个兼容入口语义 = `trading-days`（转发收口后不许漂移）。"""
    _install(monkeypatch, (False, _HOLIDAY, False))
    assert skip_non_trading_day()[0] is True
    assert is_non_trading_day() is True
    _install(monkeypatch, (True, _TRADING, False))
    assert skip_non_trading_day()[0] is False
    assert is_non_trading_day() is False


def test_verdict_info_shape_with_real_guard():
    """真实守卫（不打桩）返回五键注解——链路口径不破。"""
    info = verdict_info()
    assert set(info) == {'day', 'is_trading_day', 'source', 'degraded', 'reason'}
    assert isinstance(info['is_trading_day'], bool)
    assert isinstance(info['degraded'], bool)


def test_future_date_is_conservatively_non_trading():
    """反例锁：未来日期 → `source='future'` / 非交易日（写入型路径的刻意保守口径）。

    **为什么用远期日期而不是 2026-10-08**：`check('2026-10-08')` 只在 10-08 之前返回
    `future`，写死它会让本用例在 10-08 之后自己变红。用远期日期锁住的是**语义**，能长期跑；
    2026-10-08 的实际读数由卡上验收命令当场取证（见 notes/acceptance-run.md）。

    这条锁存在的意义：防止有人拿 `check(复市首日).is_trading_day` 当"复市首日不得跳过"的判据
    ——那会把好代码判成 bug（正确判据是 `resolve_trading_day(d).date == d`）。
    """
    v = RealGuard.check('2030-01-02')  # 周三，远期
    assert v.is_trading_day is False
    assert v.source == 'future'
