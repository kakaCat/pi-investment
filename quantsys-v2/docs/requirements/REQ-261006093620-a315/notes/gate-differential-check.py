#!/usr/bin/env python
"""差分核对：新判据模块 vs ③ 旧 gate（REQ-261006093620-a315 · t1 复核段）

> ⚠️ **一次性产物 —— t3 之后本脚本失效（2026-10-06）**：它的全部价值在于"新旧两实现**并存**时
> 逐场景比对"。`t3` 把 `daily_jobs/gate.py` 退成**纯转发壳**之后，脚本里的 `old_gate` 与
> `new_gate` 指向的是**同一个函数对象**——再跑它只是自比，**不再构成等价性证据**。
> 保留本文件，是因为 t1 复核当时的真实输出已存进 `notes/acceptance-run.md`（证据本体在那里）。
> 若将来又出现"两份实现并存"的搬迁，请**照此脚本改写**再跑，不要直接复用本文件并声称等价。

## 为什么写它

t1 把 `skip_non_trading_day` 的实现从 `adapters/inbound/fastapi_app/daily_jobs/gate.py`
搬到了 `application/services/trading_day_gate.py`，并让旧入口改为委托。**搬迁最大的风险不是报错，
而是"看着一样、结论不同"**——那会静默改掉 ③ 的语义且被 87 条既有用例放过（它们只覆盖旧实现）。

本脚本对同一批判定注解**同时喂给新旧两个实现**，逐场景比对 `(skip, 五键注解)`。

## 用法

    ./venv/bin/python docs/requirements/REQ-261006093620-a315/notes/gate-differential-check.py

退出码 0 = 全部一致；1 = 有差异（差异明细打印在 stdout）。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime

sys.path.insert(0, '.')

from adapters.inbound.fastapi_app.daily_jobs import gate as old_gate  # noqa: E402
from application.services import trading_day_gate as new_gate  # noqa: E402


@dataclass(frozen=True)
class _Verdict:
    day: date
    is_trading_day: bool
    source: str
    degraded: bool
    reason: str


class _Guard:
    def __init__(self, v):
        self._v = v

    def check(self, now=None):
        return self._v


class _Boom:
    @staticmethod
    def check(now=None):
        raise RuntimeError('boom')


#: (场景, 判定注解, 是否让判定器抛异常)
SCENARIOS = [
    ('休市日(法定节假日)', (False, 'trading-calendar-holiday', False), False),
    ('周末', (False, 'weekend', False), False),
    ('交易日', (True, 'trading-calendar', False), False),
    ('降级:工作日回退', (False, 'weekday_fallback', True), False),
    ('降级:日历不可用', (False, 'unavailable', True), False),
    ('未来日期', (False, 'future', False), False),
    ('判定器自身异常', None, True),
]


def _install(module, spec, boom):
    if boom:
        module.TradingDayGuard = _Boom
        return
    itd, source, degraded = spec
    module.TradingDayGuard = _Guard(_Verdict(date(2026, 10, 7), itd, source, degraded, f'stub:{source}'))


def main() -> int:
    diffs = []
    for name, spec, boom in SCENARIOS:
        _install(old_gate, spec, boom)
        _install(new_gate, spec, boom)
        old_skip, old_info = old_gate.skip_non_trading_day()
        new_skip, new_info = new_gate.skip_non_trading_day()
        same = (old_skip == new_skip) and (old_info == new_info)
        print(f'[{"OK " if same else "DIFF"}] {name}: skip={new_skip} source={new_info.get("source")}'
              f' degraded={new_info.get("degraded")}')
        if not same:
            diffs.append((name, old_skip, old_info, new_skip, new_info))

    # is_non_trading_day / verdict_info 两个兼容入口同样比对
    for fn_name in ('is_non_trading_day', 'verdict_info'):
        for name, spec, boom in SCENARIOS:
            _install(old_gate, spec, boom)
            _install(new_gate, spec, boom)
            old_v = getattr(old_gate, fn_name)()
            new_v = getattr(new_gate, fn_name)()
            if old_v != new_v:
                diffs.append((f'{fn_name}·{name}', old_v, '', new_v, ''))

    print()
    if diffs:
        print(f'❌ 发现 {len(diffs)} 处差异：')
        for d in diffs:
            print('  -', d)
        return 1
    print(f'✅ 全部一致：{len(SCENARIOS)} 个场景 × 3 个入口（skip_non_trading_day / '
          f'is_non_trading_day / verdict_info）逐字相同')
    return 0


if __name__ == '__main__':
    sys.exit(main())
