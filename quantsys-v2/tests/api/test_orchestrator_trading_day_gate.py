"""REQ-261006130750-0654 · 编排线程 / 盘中监控的交易日门回归锁（T1–T13）

回归背景：cron 的 `1-5` 不认节假日。② 库表调度与 ③ DailyJobs 已先后补门，
第 ④ 条路径（`orchestrator_bootstrap._monitor_loop` 的两条常驻线程）此前仍按「周几」判日 ——
休市日照调 `IntradayMonitor.check()`（有持仓时会按冻结收盘价判止损止盈并写市值），
`daily_orchestrator_tick()` 每分钟空转一次。

打桩点（本仓 CLAUDE.md 规则）：判定在 `application/services/trading_day_gate.py` 的模块全局名
`TradingDayGuard` 上取值 —— 桩**必须**打在那里（`tdg.TradingDayGuard`）；
打在各调用方模块的同名符号上不生效（本文件 `test_stub_point_is_the_gate_module` 专门证伪）。

设计对齐：docs/requirements/REQ-261006130750-0654/design/test-cases.md（T1–T13）。
日期用例一律**桩定结论**，不依赖被测机器当天是不是交易日、也不依赖测试库的日历是否被填过。
"""
from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from application.services import intraday_monitor as im
from application.services import trading_day_gate as tdg
from application.services.trading_day_guard import (
    SOURCE_CALENDAR,
    SOURCE_CALENDAR_HOLIDAY,
    SOURCE_FUTURE,
    SOURCE_UNAVAILABLE,
    TradingDayGuard,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

#: 国庆休市（周二）与一个普通交易日（周三）
HOLIDAY = datetime(2026, 10, 6, 10, 30)
TRADING = datetime(2026, 9, 30, 10, 30)


# ============================================================
# 工具：桩
# ============================================================

class _Verdict:
    """与 `TradingDayVerdict` 同形的判定注解（只暴露 gate 用到的五个字段）。"""

    def __init__(self, day: date, is_trading_day: bool, source: str,
                 degraded: bool = False, reason: str = 'stub'):
        self.day = day
        self.is_trading_day = is_trading_day
        self.source = source
        self.degraded = degraded
        self.reason = reason


def _stub_gate(monkeypatch, *, is_trading_day: bool, source: str,
               degraded: bool = False, reason: str = 'stub') -> None:
    """把判定真源换成固定结论（桩打在 `trading_day_gate` 模块的 `TradingDayGuard` 上）。"""

    class _Guard:
        @classmethod
        def check(cls, day=None, **kwargs):
            d = day
            if isinstance(d, datetime):
                d = d.date()
            elif isinstance(d, str):
                d = date.fromisoformat(d)
            elif d is None:
                d = datetime.now().date()
            return _Verdict(d, is_trading_day, source, degraded, reason)

    monkeypatch.setattr(tdg, 'TradingDayGuard', _Guard)


def _stub_gate_raises(monkeypatch) -> None:
    class _Guard:
        @classmethod
        def check(cls, day=None, **kwargs):
            raise RuntimeError('gate boom')

    monkeypatch.setattr(tdg, 'TradingDayGuard', _Guard)


class _Recorder:
    """万能记录器：任何属性访问都返回记录函数（用于断言"没有被调用"）。"""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def _f(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return None
        return _f


def _patch_engine(monkeypatch, calls: list):
    """把 `PaperTradingEngine` 换成"零持仓"的假引擎（桩打在被调函数所在模块）。"""
    from application.trading import paper_trading_engine as pte

    class _FakeEngine:
        def __init__(self, account_name=None, *args, **kwargs):
            calls.append(account_name)

        def get_current_positions(self):
            return []

    monkeypatch.setattr(pte, 'PaperTradingEngine', _FakeEngine)


def _run_loop_briefly(monkeypatch, *, until, timeout: float = 3.0) -> None:
    """把 `_monitor_loop` 跑在后台线程里，直到 `until()` 成立或超时，然后优雅停止。"""
    from adapters.inbound.fastapi_app import orchestrator_bootstrap as ob

    monkeypatch.setattr(ob, '_TICK_INTERVAL_SEC', 0.02)
    stop_event = threading.Event()
    thread = threading.Thread(target=ob._monitor_loop, args=(stop_event,), daemon=True)
    thread.start()
    deadline = datetime.now().timestamp() + timeout
    try:
        while not until() and datetime.now().timestamp() < deadline:
            stop_event.wait(0.02)
    finally:
        stop_event.set()
        thread.join(timeout=3)


# ============================================================
# T1–T3：盘中监控（B 层权威门）
# ============================================================

def test_intraday_holiday_skips_without_touching_positions(monkeypatch):
    """T1：休市日 → `check()` 返回 non-trading-day，且**不构造**引擎、不发通知。"""
    _stub_gate(monkeypatch, is_trading_day=False, source=SOURCE_CALENDAR_HOLIDAY,
               reason='交易日历判定为非交易日（来源 calendar_table）')
    engine_calls: list = []
    _patch_engine(monkeypatch, engine_calls)
    notifier = _Recorder()
    monkeypatch.setattr(im, 'agent_service', notifier)
    monkeypatch.setattr(im, 'logger', _Recorder())

    result = im.IntradayMonitor().check(now=HOLIDAY)

    assert result['status'] == 'skipped'
    assert result['reason'] == im.SKIP_REASON_NON_TRADING_DAY
    assert result['trading_day']['source'] == SOURCE_CALENDAR_HOLIDAY
    assert result['trading_day']['is_trading_day'] is False
    assert set(result['trading_day']) >= {'day', 'is_trading_day', 'source', 'degraded', 'reason'}
    assert engine_calls == []       # 不取持仓 → 不读价格 → 不判止损止盈 → 不写市值
    assert notifier.calls == []     # T13：跳过路径零通知


def test_intraday_trading_day_still_runs(monkeypatch):
    """T2：交易日 → 照旧走到既有流程（对照，证明门没有把交易日也拦掉）。"""
    _stub_gate(monkeypatch, is_trading_day=True, source=SOURCE_CALENDAR)
    engine_calls: list = []
    _patch_engine(monkeypatch, engine_calls)

    result = im.IntradayMonitor().check(now=TRADING)

    assert result['status'] == 'no_positions'          # 假引擎零持仓 → 既有早退分支
    assert result.get('reason') != im.SKIP_REASON_NON_TRADING_DAY
    assert engine_calls == ['rotation_main']           # 引擎被构造恰好一次


def test_intraday_degraded_is_fail_open(monkeypatch):
    """T3：日历链降级 → 照跑（fail-open），注解里带 degraded（不许静默停摆）。"""
    _stub_gate(monkeypatch, is_trading_day=False, source=SOURCE_UNAVAILABLE, degraded=True,
               reason='日历不可用 → 工作日口径')
    engine_calls: list = []
    _patch_engine(monkeypatch, engine_calls)
    notifier = _Recorder()
    monkeypatch.setattr(im, 'agent_service', notifier)

    skip, info = tdg.should_skip('trading-days', HOLIDAY)
    assert skip is False and info['degraded'] is True

    result = im.IntradayMonitor().check(now=HOLIDAY)
    assert result['status'] != 'skipped'
    assert engine_calls == ['rotation_main']
    assert notifier.calls == []


def test_gate_own_exception_is_fail_open(monkeypatch):
    """T4：门自身异常 → 照跑（gate-error 且 degraded=True），且不得把异常抛给线程。"""
    _stub_gate_raises(monkeypatch)
    from adapters.inbound.fastapi_app import orchestrator_bootstrap as ob

    run, info = ob._should_run_today(HOLIDAY, path=ob.PATH_ORCHESTRATOR_TICK)
    assert run is True and info['degraded'] is True and info['source'] == tdg.SOURCE_GATE_ERROR

    engine_calls: list = []
    _patch_engine(monkeypatch, engine_calls)
    assert im.IntradayMonitor().check(now=HOLIDAY)['status'] != 'skipped'
    assert engine_calls == ['rotation_main']


# ============================================================
# T5：口径反例锁（未来日不得当休市日判据）
# ============================================================

def test_future_date_is_not_a_holiday_verdict():
    """T5：未来日期走 `source='future'`（写入型路径刻意保守）——
    谁拿它的 `is_trading_day=False` 当"休市日"判据，谁就把好代码判成 bug。

    本用例用**动态**未来日（今天 +400 天后的首个工作日），避免写死日期后随时间失效；
    该分支在 `TradingDayGuard._compute` 里位于日历链**之前**，故不依赖数据库。
    """
    future = datetime.now().date() + timedelta(days=400)
    while future.weekday() >= 5:
        future += timedelta(days=1)

    verdict = TradingDayGuard.check(future)

    assert verdict.source == SOURCE_FUTURE
    assert verdict.is_trading_day is False
    assert verdict.degraded is False


# ============================================================
# T6–T7：编排循环（A 层预过滤）
# ============================================================

def test_orchestrator_loop_silent_on_holiday(monkeypatch):
    """T6：休市日 → 两条 tick 都不被调用（而时段窗口仍为真，证明拦它的是日级门）。"""
    from adapters.inbound.fastapi_app import orchestrator_bootstrap as ob

    _stub_gate(monkeypatch, is_trading_day=False, source=SOURCE_CALENDAR_HOLIDAY)
    ticks = {'orch': 0, 'intraday': 0}
    monkeypatch.setattr('infrastructure.jobs.monitor_jobs.daily_orchestrator_tick',
                        lambda: ticks.__setitem__('orch', ticks['orch'] + 1))
    monkeypatch.setattr('infrastructure.jobs.monitor_jobs.intraday_monitor_check',
                        lambda: ticks.__setitem__('intraday', ticks['intraday'] + 1))
    monkeypatch.setattr(ob, '_in_orchestrator_window', lambda now: True)
    monkeypatch.setattr(ob, '_in_intraday_window', lambda now: True)
    monkeypatch.setattr(ob, '_LAST_SKIP_LOG', {})

    _run_loop_briefly(
        monkeypatch,
        until=lambda: set(ob._LAST_SKIP_LOG) == {ob.PATH_ORCHESTRATOR_TICK, ob.PATH_INTRADAY_MONITOR},
    )

    assert ob._in_orchestrator_window(datetime(2026, 10, 6, 12, 30)) is True  # 时段层没拦
    assert ticks['orch'] == 0
    assert ticks['intraday'] == 0
    assert ob._LAST_SKIP_LOG == {ob.PATH_ORCHESTRATOR_TICK: '2026-10-06',
                                 ob.PATH_INTRADAY_MONITOR: '2026-10-06'}


def test_orchestrator_loop_runs_on_trading_day(monkeypatch):
    """T7：交易日 → 编排 tick 照调（净效果 = 只少了休市日那些调用）。"""
    from adapters.inbound.fastapi_app import orchestrator_bootstrap as ob

    _stub_gate(monkeypatch, is_trading_day=True, source=SOURCE_CALENDAR)
    ticks = {'orch': 0}
    monkeypatch.setattr('infrastructure.jobs.monitor_jobs.daily_orchestrator_tick',
                        lambda: ticks.__setitem__('orch', ticks['orch'] + 1))
    monkeypatch.setattr('infrastructure.jobs.monitor_jobs.intraday_monitor_check', lambda: None)
    monkeypatch.setattr(ob, '_in_orchestrator_window', lambda now: True)
    monkeypatch.setattr(ob, '_in_intraday_window', lambda now: False)
    monkeypatch.setattr(ob, '_LAST_SKIP_LOG', {})

    _run_loop_briefly(monkeypatch, until=lambda: ticks['orch'] >= 1)

    assert ticks['orch'] >= 1
    assert ob._LAST_SKIP_LOG == {}


# ============================================================
# T8 / T9：源码纪律与打桩点
# ============================================================

def test_static_single_source_of_truth():
    """T8：唯一真源 —— 判据只在 gate 模块；调用方不得自带日历/星期判定。"""
    ob_src = (REPO_ROOT / 'adapters/inbound/fastapi_app/orchestrator_bootstrap.py').read_text('utf-8')
    im_src = (REPO_ROOT / 'application/services/intraday_monitor.py').read_text('utf-8')

    assert ob_src.count('should_skip') >= 2          # 两条路径各一次
    assert 'weekday(' not in im_src                  # 盘中监控不得自带日级判定
    assert 'trading_calendar' not in ob_src and 'trading_calendar' not in im_src
    assert 'force' not in im_src                     # 不做"休市日人工强制"后门（use-cases §7）


def test_stub_point_is_the_gate_module(monkeypatch):
    """T9：桩打在真源（`trading_day_gate.TradingDayGuard`）上两个调用点都变；
    打在调用方模块的同名名字上只影响该模块自己 —— 这就是"打错地方仍以为通过"的证伪。"""
    from adapters.inbound.fastapi_app import orchestrator_bootstrap as ob

    _stub_gate(monkeypatch, is_trading_day=False, source=SOURCE_CALENDAR_HOLIDAY)
    assert ob._should_run_today(HOLIDAY, path=ob.PATH_ORCHESTRATOR_TICK)[0] is False
    assert im.IntradayMonitor().check(now=HOLIDAY)['reason'] == im.SKIP_REASON_NON_TRADING_DAY

    # 反向：把桩打在**调用方**（ob）的 `should_skip` 名字上 → 只有 ob 受影响
    monkeypatch.setattr(ob, 'should_skip', lambda policy, now=None: (False, {'day': '2026-10-06'}))
    assert ob._should_run_today(HOLIDAY, path=ob.PATH_ORCHESTRATOR_TICK)[0] is True
    assert im.IntradayMonitor().check(now=HOLIDAY)['reason'] == im.SKIP_REASON_NON_TRADING_DAY


# ============================================================
# T10–T12：去噪、窗口语义、时段优先
# ============================================================

def test_skip_log_is_deduped_per_path_and_day(monkeypatch):
    """T10：同一 path + 同一天只留一条跳过日志；换一天恢复记录（休市日 600 次/天不刷屏）。"""
    from adapters.inbound.fastapi_app import orchestrator_bootstrap as ob

    _stub_gate(monkeypatch, is_trading_day=False, source=SOURCE_CALENDAR_HOLIDAY)
    recorder = _Recorder()
    monkeypatch.setattr(ob, 'logger', recorder)
    monkeypatch.setattr(ob, '_LAST_SKIP_LOG', {})

    assert ob._should_run_today(HOLIDAY, path=ob.PATH_ORCHESTRATOR_TICK)[0] is False
    assert ob._should_run_today(HOLIDAY.replace(minute=31), path=ob.PATH_ORCHESTRATOR_TICK)[0] is False
    assert [c[0] for c in recorder.calls] == ['info']
    assert recorder.calls[0][1][0] == 'orchestrator_trading_day_skip'
    assert recorder.calls[0][2]['day'] == '2026-10-06'
    assert recorder.calls[0][2]['source'] == SOURCE_CALENDAR_HOLIDAY
    assert recorder.calls[0][2]['degraded'] is False

    # 次日：key 变了 → 再留一条
    _stub_gate(monkeypatch, is_trading_day=False, source=SOURCE_CALENDAR_HOLIDAY)
    recorder.calls.clear()
    monkeypatch.setattr(ob, '_LAST_SKIP_LOG', {'orchestrator_tick': '2026-10-05'})
    assert ob._should_run_today(HOLIDAY.replace(day=7), path=ob.PATH_ORCHESTRATOR_TICK)[0] is False
    assert [c[0] for c in recorder.calls] == ['info']


def test_window_semantics_unchanged():
    """T11：窗口函数的时段语义逐条不变（既有契约面，本需求只加日级门、不动时段）。"""
    from adapters.inbound.fastapi_app.orchestrator_bootstrap import (
        _in_intraday_window,
        _in_orchestrator_window,
    )

    assert _in_orchestrator_window(datetime(2026, 8, 13, 9, 25)) is True
    assert _in_orchestrator_window(datetime(2026, 8, 13, 17, 59)) is True
    assert _in_orchestrator_window(datetime(2026, 8, 13, 7, 59)) is False
    assert _in_orchestrator_window(datetime(2026, 8, 13, 18, 0)) is False
    assert _in_orchestrator_window(datetime(2026, 8, 15, 10, 0)) is False   # 周六

    assert _in_intraday_window(datetime(2026, 8, 13, 9, 30)) is True
    assert _in_intraday_window(datetime(2026, 8, 13, 11, 30)) is True
    assert _in_intraday_window(datetime(2026, 8, 13, 14, 30)) is True
    assert _in_intraday_window(datetime(2026, 8, 13, 15, 0)) is True
    assert _in_intraday_window(datetime(2026, 8, 13, 9, 31)) is False       # 非 :00/:30
    assert _in_intraday_window(datetime(2026, 8, 13, 12, 0)) is False       # 午休
    assert _in_intraday_window(datetime(2026, 8, 15, 10, 0)) is False       # 周六


def test_intraday_time_check_precedes_day_gate(monkeypatch):
    """T12：严格增量 —— 时段外仍返回既有的 `not trading time`（不是 non-trading-day），
    即新分支只覆盖"原本会真干活"的时刻，既有返回形状一字不改。"""
    _stub_gate(monkeypatch, is_trading_day=False, source=SOURCE_CALENDAR_HOLIDAY)
    engine_calls: list = []
    _patch_engine(monkeypatch, engine_calls)

    result = im.IntradayMonitor().check(now=HOLIDAY.replace(hour=20, minute=0))

    assert result == {'status': 'skipped', 'reason': 'not trading time'}
    assert engine_calls == []
