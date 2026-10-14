"""DailyJobs 交易日门单测（REQ-261005203907-2b8c）

覆盖本卡（t-dd0d4d）的 TC-1 真值表 + `JobDef` 字段兼容；宿主接线（TC-2/TC-3）与
兼容判据（TC-5）由后续卡在同一文件追加。

## 打桩纪律（本仓踩过的坑）

- 桩必须打在被调函数**所在模块**：**`application.services.trading_day_gate.TradingDayGuard`**。
  `daily_jobs/gate.py` 自 REQ-261006093620-a315 t3 起是**转发壳**（判据已上移到 application 层，
  供 ② 库表调度共用），打在旧名字 `daily_jobs.gate.TradingDayGuard` 上**不会生效**——
  判定在新模块取值。`test_forwarding_shell_reads_patched_new_module` 是专锁这条的证伪用例。
- **零网络零 DB**：用假判定器替代真实日历链。真实日历/降级链本身由
  REQ-261004154902-a7cd 的 47 条用例覆盖（`tests/test_trading_day_guard.py`），
  本文件只验"给定判定 → 门的取舍与注解"。
- 假判定器**照真实语义**建模：2026 国庆 10-01~10-07 休市、10-08 复市、
  周末恒非交易日、其余工作日为交易日——这样断言的是门的映射，而不是我编的常量。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dtime
from unittest.mock import Mock

import pytest

from adapters.inbound.fastapi_app.daily_jobs import gate as gate_mod
from adapters.inbound.fastapi_app.daily_jobs.gate import (
    SOURCE_GATE_ERROR,
    is_non_trading_day,
    skip_non_trading_day,
    verdict_info,
)
from adapters.inbound.fastapi_app.daily_jobs.defs import JobDef

#: 判据真源所在模块（REQ-261006093620-a315 t3）：**桩必须打在这里**（见文件头「打桩纪律」）
from application.services import trading_day_gate as new_gate_mod

#: 2026 年国庆休市窗口（上证公告〔2026〕22 号：10-01（四）~ 10-07（三）休市，10-08（四）复市）
_HOLIDAYS = {f'2026-10-{d:02d}' for d in range(1, 8)}


@dataclass(frozen=True)
class _Verdict:
    """`TradingDayVerdict` 的最小替身（只带门用到的五个字段）。"""

    day: date
    is_trading_day: bool
    source: str
    degraded: bool
    reason: str


class _StubCalendarGuard:
    """照真实日历语义作答的假判定器（零 DB）。"""

    @staticmethod
    def check(now=None):
        d = (now or datetime.now()).date()
        if d.weekday() >= 5:
            return _Verdict(d, False, 'weekend', False, '周末')
        if d.isoformat() in _HOLIDAYS:
            return _Verdict(d, False, 'trading-calendar-holiday', False, '该日不在交易日历中')
        return _Verdict(d, True, 'trading-calendar', False, '日历答该日为交易日')


class _DegradedGuard:
    """降级判定器（日历链不可用 → 工作日回退），结论照用但 degraded=True。"""

    @staticmethod
    def check(now=None):
        d = (now or datetime.now()).date()
        return _Verdict(d, False, 'weekday_fallback', True, '日历不可用 → 按周一~周五口径判定')


class _BoomGuard:
    """判定器自身异常（模拟 gate 之外的意外，如 import/属性错误）。"""

    @staticmethod
    def check(now=None):
        raise RuntimeError('boom')


@pytest.fixture
def real_calendar(monkeypatch):
    monkeypatch.setattr(new_gate_mod, 'TradingDayGuard', _StubCalendarGuard)
    return _StubCalendarGuard


def test_forwarding_shell_reads_patched_new_module(monkeypatch):
    """证伪断言（REQ-261006093620-a315 t3）：转发壳必须真的走新模块的判定。

    ① 桩打到 `application.services.trading_day_gate.TradingDayGuard` → 经**转发壳**调用
       得到的结论随之改变（休市日 → 跳过）；
    ② 再把旧模块 `daily_jobs.gate.TradingDayGuard` 打成一个必然抛异常的替身 → 结论**不变**
       （证明壳里没有本地实现、判定不读旧模块的全局名）。

    若哪天有人把判定复制回壳里，②会红——那正是本仓 CLAUDE.md 记的「桩静默失效」形态。
    """
    monkeypatch.setattr(new_gate_mod, 'TradingDayGuard', _StubCalendarGuard)
    skip, info = skip_non_trading_day(datetime(2026, 10, 6, 19, 5))
    assert skip is True and info['source'] == 'trading-calendar-holiday'

    monkeypatch.setattr(gate_mod, 'TradingDayGuard', _BoomGuard, raising=False)
    skip2, info2 = skip_non_trading_day(datetime(2026, 10, 6, 19, 5))
    assert (skip2, info2['source']) == (True, 'trading-calendar-holiday')


class TestTruthTable:
    """TC-1：判定真值表"""

    @pytest.mark.parametrize('day', ['2026-10-05', '2026-10-06', '2026-10-07'])
    def test_holiday_truth_skips(self, real_calendar, day):
        """休市日（国庆工作日）→ 跳过，来源必须标明是日历判的、且未降级。"""
        now = datetime.strptime(day + ' 19:05', '%Y-%m-%d %H:%M')
        skip, info = skip_non_trading_day(now)
        assert skip is True
        assert info['day'] == day
        assert info['is_trading_day'] is False
        assert info['source'] == 'trading-calendar-holiday'
        assert info['degraded'] is False

    @pytest.mark.parametrize('day', ['2026-09-30', '2026-10-08'])
    def test_trading_day_truth_runs(self, real_calendar, day):
        """交易日（休市前最后一个交易日 / 复市首日）→ 照跑。"""
        now = datetime.strptime(day + ' 19:05', '%Y-%m-%d %H:%M')
        skip, info = skip_non_trading_day(now)
        assert skip is False
        assert info['is_trading_day'] is True
        assert info['source'] == 'trading-calendar'

    def test_weekend_truth_skips(self, real_calendar):
        """周末 → 跳过（与工作日排班叠加为双保险；防将来有人把任务改成含周末排班）。"""
        now = datetime(2026, 10, 3, 19, 5)  # 周六
        skip, info = skip_non_trading_day(now)
        assert skip is True
        assert info['source'] == 'weekend'
        assert info['degraded'] is False

    def test_returns_annotation_shape(self, real_calendar):
        """注解五键齐、类型正确（result 的契约字段）。"""
        info = verdict_info(datetime(2026, 10, 6, 19, 5))
        assert set(info) == {'day', 'is_trading_day', 'source', 'degraded', 'reason'}
        assert isinstance(info['day'], str) and len(info['day']) == 10
        assert isinstance(info['is_trading_day'], bool)
        assert isinstance(info['source'], str) and info['source']
        assert isinstance(info['degraded'], bool)
        assert isinstance(info['reason'], str) and info['reason']


class TestFailOpen:
    """TC-1 的 fail-open 两条：降级与自身异常都不许变成"不开火" """

    def test_degraded_runs_fail_open(self, monkeypatch):
        """判据是「and」不是「or」：is_trading_day=False 但 degraded=True → **照跑**。"""
        monkeypatch.setattr(new_gate_mod, 'TradingDayGuard', _DegradedGuard)
        skip, info = skip_non_trading_day(datetime(2026, 10, 6, 19, 5))
        assert skip is False, '降级绝不能被读成休市（那会让门成为静默停摆源）'
        assert info['degraded'] is True
        assert info['source'] == 'weekday_fallback'

    def test_gate_error_runs(self, monkeypatch):
        """判定器抛异常 → 门不许抛，且判「照跑」+ 标注 gate-error。"""
        monkeypatch.setattr(new_gate_mod, 'TradingDayGuard', _BoomGuard)
        skip, info = skip_non_trading_day(datetime(2026, 10, 6, 19, 5))
        assert skip is False
        assert info['source'] == SOURCE_GATE_ERROR
        assert info['degraded'] is True
        assert 'boom' in info['reason']
        # 三个入口都不许抛
        assert is_non_trading_day(datetime(2026, 10, 6, 19, 5)) is False
        assert verdict_info(datetime(2026, 10, 6, 19, 5))['source'] == SOURCE_GATE_ERROR

    def test_never_raises_on_bad_now(self, real_calendar):
        """脏入参（字符串/None）不许把调用方打挂——最坏退回今天。"""
        assert isinstance(is_non_trading_day('2026-10-06'), bool)
        assert isinstance(verdict_info('2026-10-06')['day'], str)


class TestJobDefField:
    """FR-1 字段契约：末尾新增 + 默认 False（位置参数构造兼容）"""

    def test_trading_days_only_defaults_false(self):
        assert JobDef('x', dtime(0, 0), (0,), lambda: {}, 'd').trading_days_only is False

    def test_positional_construction_still_works(self):
        """5 个位置参数构造（仓内既有写法）必须不炸，且仍是 JobDef。"""
        job = JobDef('evening_pipeline', dtime(20, 30), (0, 1, 2, 3, 4), lambda: {}, '工作日任务')
        assert isinstance(job, JobDef)
        assert job.job_id == 'evening_pipeline'

    def test_keyword_opt_in(self):
        assert JobDef('x', dtime(0, 0), (0,), lambda: {}, 'd',
                      trading_days_only=True).trading_days_only is True


# ---------------------------------------------------------------------------
# TC-2 / TC-3：宿主接线（t-075116）
# ---------------------------------------------------------------------------

_HOLIDAY_INFO = {
    'day': '2026-10-06',
    'is_trading_day': False,
    'source': 'trading-calendar-holiday',
    'degraded': False,
    'reason': '该日不在交易日历中',
}


class _FakeLogger:
    """记录日志调用（断言"降级不许静默"）。"""

    def __init__(self):
        self.infos, self.warnings, self.errors = [], [], []

    def info(self, event, **kw):
        self.infos.append((event, kw))

    def warning(self, event, **kw):
        self.warnings.append((event, kw))

    def error(self, event, *a, **kw):
        self.errors.append((event, kw))


class _FakeHistogram:
    """记录 observe 调用（断言跳过不污染耗时直方图）。"""

    def __init__(self):
        self.observed = []

    def labels(self, **kw):
        outer = self

        class _Labeled:
            def observe(self, value):
                outer.observed.append((kw, value))

        return _Labeled()


def _patch_host(monkeypatch, gate_result, handler):
    """按"桩打在被调函数所在模块"的纪律打桩 runtime 的四个符号。"""
    from adapters.inbound.fastapi_app.daily_jobs import runtime as host_runtime
    from infrastructure.monitoring import business_metrics as bm

    marks, sends = [], []
    logger = _FakeLogger()
    hist = _FakeHistogram()
    monkeypatch.setattr(host_runtime, '_mark_running', lambda *a, **k: None)
    monkeypatch.setattr(host_runtime, '_mark_done',
                        lambda job_id, run_date, status, **kw: marks.append((status, kw)))
    monkeypatch.setattr(host_runtime, '_send_feishu', lambda *a, **k: sends.append(a))
    monkeypatch.setattr(host_runtime, 'skip_non_trading_day', lambda *a, **k: gate_result)
    monkeypatch.setattr(host_runtime, 'logger', logger)
    monkeypatch.setattr(bm, 'scheduler_job_duration_seconds', hist)
    job = JobDef('flagged_job', dtime(19, 5), (0, 1, 2, 3, 4), handler, '带门任务',
                 trading_days_only=True)
    return host_runtime, job, marks, sends, logger, hist


class TestRunJobSkip:
    """TC-2：跳过 = 留痕 + 不打扰"""

    def test_skip_writes_skipped_row_and_no_notify(self, monkeypatch):
        handler = Mock(side_effect=AssertionError('休市日不许执行 handler'))
        host, job, marks, sends, logger, hist = _patch_host(
            monkeypatch, (True, dict(_HOLIDAY_INFO)), handler)

        host._run_job(job, '2026-10-06')

        assert marks and marks[0][0] == 'skipped', marks
        payload = marks[0][1].get('result') or {}
        assert payload.get('skipped') is True
        assert '非交易日' in payload.get('reason', '')
        assert payload.get('trading_day') == _HOLIDAY_INFO
        assert handler.call_count == 0
        assert sends == [], '跳过路径一条飞书都不许发'
        assert [e for e, _ in logger.infos if e == 'inprocess_job_skipped'], logger.infos

    def test_skip_does_not_observe_duration(self, monkeypatch):
        """跳过不是"执行耗时"：观测进去会污染耗时直方图的低分位。"""
        host, job, marks, sends, logger, hist = _patch_host(
            monkeypatch, (True, dict(_HOLIDAY_INFO)), lambda: {'ok': 1})
        host._run_job(job, '2026-10-06')
        assert hist.observed == []
        assert marks[0][0] == 'skipped'

    def test_unflagged_job_ignores_gate(self, monkeypatch):
        """未声明标志的任务：即便门判"该跳过"也照跑（缺省行为逐字不变）。"""
        from adapters.inbound.fastapi_app.daily_jobs import runtime as host_runtime

        marks, sends = [], []
        monkeypatch.setattr(host_runtime, '_mark_running', lambda *a, **k: None)
        monkeypatch.setattr(host_runtime, '_mark_done',
                            lambda job_id, run_date, status, **kw: marks.append((status, kw)))
        monkeypatch.setattr(host_runtime, '_send_feishu', lambda *a, **k: sends.append(a))
        monkeypatch.setattr(host_runtime, 'skip_non_trading_day',
                            lambda *a, **k: (True, dict(_HOLIDAY_INFO)))
        job = JobDef('plain_job', dtime(19, 5), (0, 1, 2, 3, 4), lambda: {'ok': 1}, '无门任务')

        host_runtime._run_job(job, '2026-10-06')

        assert marks and marks[0][0] == 'success'
        # REQ-261006165125-23a9（FR-2/FR-3）改了通知口径：开始消息不再无条件发出，
        # 有产出的任务只发一条完成消息。本用例的原意（"无门任务不受门影响 → 照跑"）不变，
        # 只把"2 条"改为"1 条完成"。
        assert len(sends) == 1, sends
        assert sends[0][0].startswith('✅ 每日任务完成：plain_job'), sends


class TestRunJobDegraded:
    """TC-2：照跑路径必须把降级事实带出去（不许静默）"""

    def test_degraded_run_annotates_result_and_warns(self, monkeypatch):
        degraded_info = {
            'day': '2026-10-06',
            'is_trading_day': False,
            'source': 'weekday_fallback',
            'degraded': True,
            'reason': '日历不可用 → 按周一~周五口径判定',
        }
        host, job, marks, sends, logger, hist = _patch_host(
            monkeypatch, (False, degraded_info), lambda: {'updated': 3})

        host._run_job(job, '2026-10-06')

        assert marks and marks[0][0] == 'success', marks
        payload = marks[0][1].get('result') or {}
        assert payload['trading_day'] == degraded_info
        assert payload['updated'] == 3
        assert [e for e, _ in logger.warnings if e == 'inprocess_job_trading_day_degraded'], logger.warnings
        # REQ-261006165125-23a9：有产出 → 只发一条完成消息（开始消息已取消）
        assert len(sends) == 1, sends
        assert sends[0][0].startswith('✅ 每日任务完成：flagged_job'), sends

    def test_degraded_annotation_does_not_trip_failure_classifier(self, monkeypatch):
        """注解里没有 success/status 键，不该被内层失败分类器下钻误判。"""
        from infrastructure.scheduler.job_executor import find_result_failure

        degraded_info = dict(_HOLIDAY_INFO, degraded=True, source='weekday_fallback')
        assert find_result_failure({'updated': 3, 'trading_day': degraded_info}) is None


class TestRegistryScope:
    """TC-3：逐任务范围——恰好 3 个任务带门"""

    def test_registry_flags_exactly_three(self):
        from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS

        flagged = {j.job_id for j in JOBS if j.trading_days_only}
        assert flagged == {'pool_daily_refresh', 'chip_distribution', 'evolution_fitness'}, flagged

    def test_evening_pipeline_not_flagged(self):
        """evening_pipeline 走 handler 内局部判定（K 线段必须留在休市日跑）。"""
        from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS

        job = next(j for j in JOBS if j.job_id == 'evening_pipeline')
        assert job.trading_days_only is False

    def test_other_jobs_unflagged(self):
        from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS

        others = {j.job_id for j in JOBS if not j.trading_days_only}
        assert others == {'watch_rule_health', 'event_calendar_check', 'freshness_guard',
                          'evening_pipeline', 'financial_statements', 'pool_weekly_review'}, others


# ---------------------------------------------------------------------------
# TC-5：兼容与回滚核验（t-dbb9d0）——`skipped` 对既有消费者的行为
# ---------------------------------------------------------------------------

class TestSkippedRowCompatibility:
    """新增状态值不改变任何既有消费者的判定（设计 interfaces.md §5 的兼容矩阵）"""

    def _job(self, weekdays=(0, 1, 2, 3, 4)):
        return JobDef('compat_job', dtime(19, 5), weekdays, lambda: {}, '兼容核验',
                      trading_days_only=True)

    def test_skipped_row_blocks_rerun_same_day(self):
        """`is_due` 对未知状态落 return False → 当天不重跑（幂等）。"""
        from adapters.inbound.fastapi_app.daily_jobs.runtime import is_due

        now = datetime(2026, 10, 6, 19, 10)
        assert is_due(self._job(), now, {'status': 'skipped', 'started_at': now}) is False

    def test_skipped_row_is_not_failed_or_running_semantics(self):
        """对照：三方支语义未被挤掉（success / running / failed 仍是原判据）。"""
        from adapters.inbound.fastapi_app.daily_jobs.runtime import is_due

        now = datetime(2026, 10, 6, 19, 10)
        job = self._job()
        assert is_due(job, now, {'status': 'success', 'started_at': now}) is False
        assert is_due(job, now, {'status': 'running', 'started_at': now}) is False
        assert is_due(job, now, {'status': 'failed', 'started_at': now}) is False

    def test_skipped_row_not_catchup(self):
        """补跑只认 failed：排班日 catchup_due 恒 False；非排班日则由 failed 决定。"""
        from adapters.inbound.fastapi_app.daily_jobs.runtime import catchup_due

        now = datetime(2026, 10, 6, 19, 10)  # 周二（排班日内）
        assert catchup_due(self._job(), now, has_recent_failure=True) is False
        # 非排班日：只有"近 3 日有 failed"才补跑 —— skipped 不参与该判据
        sat = datetime(2026, 10, 10, 19, 10)  # 周六
        assert catchup_due(self._job(), sat, has_recent_failure=False) is False
        assert catchup_due(self._job(), sat, has_recent_failure=True) is True

    def test_trigger_job_allows_skipped_but_refuses_success(self, monkeypatch):
        """人工触发：skipped 不是"今日已有记录"的拒绝理由；success 仍然是。"""
        from adapters.inbound.fastapi_app.daily_jobs import runtime as host_runtime

        monkeypatch.setattr(host_runtime, '_run_job', lambda *a, **k: None)
        job_id = 'pool_daily_refresh'

        monkeypatch.setattr(host_runtime, '_get_run',
                            lambda *_a, **_k: {'status': 'skipped', 'started_at': None})
        allowed = host_runtime.trigger_job(job_id, force=False)
        assert allowed.get('success') is True, allowed

        monkeypatch.setattr(host_runtime, '_get_run',
                            lambda *_a, **_k: {'status': 'success', 'started_at': None})
        refused = host_runtime.trigger_job(job_id, force=False)
        assert refused.get('success') is False and '今日已有记录' in refused.get('error', '')

    def test_skipped_true_is_not_a_failure(self):
        """显式 skipped=True 不算失败（job_executor.py:157 的既有约定）。"""
        from infrastructure.scheduler.job_executor import find_result_failure

        assert find_result_failure({'skipped': True, 'reason': '非交易日'}) is None

    def test_int_skipped_count_is_not_misread_as_bool(self):
        """命名撞车防呆：kline_sync.skipped 是"跳过只数"（int），不是布尔跳过。"""
        from infrastructure.scheduler.job_executor import find_result_failure

        assert find_result_failure({'kline_sync': {'status': 'success', 'skipped': 12}}) is None
        # 反向：真·布尔跳过在任何层级都不算失败
        assert find_result_failure({'kline_sync': {'status': 'success', 'skipped': True}}) is None


# ---------------------------------------------------------------------------
# 卡 C（REQ-261006190953-fc43）：EquitySnapshotJob 的两段判据
#   ① 是不是交易日 → `trading_day_gate`（唯一真源，本文件用桩给出结论）
#   ② 当日是否已收盘 → `_has_bar`（**辅助**判据，不再是交易日代理）
# 两个用例都显式传目标日 + 打桩判据 → 与"今天是不是交易日"无关。
# ---------------------------------------------------------------------------

_SNAPSHOT_DAY = date(2026, 10, 6)     # 国庆休市（真实判据下亦为非交易日；此处一律打桩）

_HOLIDAY_GATE = (True, {
    'day': '2026-10-06',
    'is_trading_day': False,
    'source': 'trading-calendar-holiday',
    'degraded': False,
    'reason': '交易日历判定为非交易日（该日不在交易日历中）',
})
_TRADING_GATE = (False, {
    'day': '2026-10-06',
    'is_trading_day': True,
    'source': 'trading-calendar',
    'degraded': False,
    'reason': '交易日历判定为交易日',
})


def _snapshot_job(monkeypatch, gate_result, has_bar, service=None):
    """装配 EquitySnapshotJob：零 DB（关掉服务注册）+ 门打桩 + `_has_bar` 打桩。

    桩位（本仓纪律）：`skip_non_trading_day` 打在**被调函数所在模块**
    `application.services.trading_day_gate` 上——job 是惰性 import + 按模块属性取值，
    故桩生效（打在 job 模块的全局名上不会有这个符号）。`register_all_services` 同理：
    `run()` 内 import，取值发生在 `infrastructure.services.service_registry`。
    """
    from application.services.evolution.daily_snapshot_service import EquitySnapshotJob
    from infrastructure.services import service_registry as registry_mod

    monkeypatch.setattr(new_gate_mod, 'skip_non_trading_day', lambda *a, **k: gate_result)
    monkeypatch.setattr(registry_mod, 'register_all_services', lambda *a, **k: None)
    bar_calls = []
    monkeypatch.setattr(EquitySnapshotJob, '_has_bar',
                        lambda self, target: (bar_calls.append(target), has_bar)[1])
    return EquitySnapshotJob(service=service), bar_calls


class TestEquitySnapshotJobTradingDayGate:
    """④⑤：休市日跳过（即使有 K 线）／交易日未收盘跳过，两段理由可区分"""

    def test_holiday_skips_with_non_trading_reason(self, monkeypatch):
        """④ 休市日 → skipped=True，理由说的是「非交易日」。"""
        job, _ = _snapshot_job(monkeypatch, _HOLIDAY_GATE, has_bar=True)

        out = job.run(_SNAPSHOT_DAY)

        assert out['skipped'] is True
        assert '非交易日' in out['reason']
        assert '尚未收盘' not in out['reason']
        assert out['trading_day'] == _HOLIDAY_GATE[1]
        assert out['trading_day_source'] == 'trading-calendar-holiday'

    def test_bar_exists_on_holiday_still_skips(self, monkeypatch):
        """⑤ 该日 K 线存在（`_has_bar=True`）也照跳：`_has_bar` 已**不是**交易日判据。

        证伪方向：谁把 `_has_bar` 重新当"是不是交易日"用，本用例立刻变红
        （有 K 线 → 判交易日 → 不跳 → 写出"旧价标新日"的假快照）。
        """
        job, _ = _snapshot_job(monkeypatch, _HOLIDAY_GATE, has_bar=True)

        out = job.run(_SNAPSHOT_DAY)

        assert out['skipped'] is True
        assert '非交易日' in out['reason']

    def test_trading_day_without_bar_skips_as_not_closed(self, monkeypatch):
        """④ 交易日但当日 K 线未落库（尚未收盘）→ 跳，理由说的是「尚未收盘」。"""
        job, bar_calls = _snapshot_job(monkeypatch, _TRADING_GATE, has_bar=False)

        out = job.run(_SNAPSHOT_DAY)

        assert out['skipped'] is True
        assert '尚未收盘' in out['reason']
        assert '非交易日' not in out['reason']
        assert bar_calls == [_SNAPSHOT_DAY], '交易日才轮到收盘辅助判据'

    def test_two_skip_reasons_are_distinguishable(self, monkeypatch):
        """把两段文案摆在一起比：混成一句「非交易日或尚未收盘」等于没判。"""
        holiday_job, _ = _snapshot_job(monkeypatch, _HOLIDAY_GATE, has_bar=True)
        holiday = holiday_job.run(_SNAPSHOT_DAY)
        not_closed_job, _ = _snapshot_job(monkeypatch, _TRADING_GATE, has_bar=False)
        not_closed = not_closed_job.run(_SNAPSHOT_DAY)

        assert holiday['reason'] != not_closed['reason']
        assert ('非交易日' in holiday['reason']) and ('尚未收盘' not in holiday['reason'])
        assert ('尚未收盘' in not_closed['reason']) and ('非交易日' not in not_closed['reason'])

    def test_trading_day_with_bar_runs_snapshot(self, monkeypatch):
        """正路：交易日 + K 线已落库 → 交给服务，且目标日原样传入（不许回落成"今天"）。"""
        svc = Mock()
        svc.snapshot_all_accounts.return_value = {'written': 2, 'refused': 0}
        job, bar_calls = _snapshot_job(monkeypatch, _TRADING_GATE, has_bar=True, service=svc)

        out = job.run(_SNAPSHOT_DAY)

        assert out['skipped'] is False
        assert out['result']['written'] == 2
        assert out['trading_day'] == _TRADING_GATE[1]
        svc.snapshot_all_accounts.assert_called_once_with(target_date=_SNAPSHOT_DAY)
        assert bar_calls == [_SNAPSHOT_DAY]

    def test_skipped_annotation_reaches_job_result(self, monkeypatch):
        """`execute()` 把门注解带进 JobResult.details（调度留痕里看得见降级/休市事实）。"""
        import asyncio

        job, _ = _snapshot_job(monkeypatch, _HOLIDAY_GATE, has_bar=True)

        res = asyncio.run(job.execute())

        assert res.success is True
        # `result_from_dict` 既有口径：payload 落在 details['details']（JobResult.ok 的 **details 形参）
        payload = res.details['details']
        assert payload['skipped'] is True
        assert payload['trading_day'] == _HOLIDAY_GATE[1]
        assert payload['trading_day_source'] == 'trading-calendar-holiday'

