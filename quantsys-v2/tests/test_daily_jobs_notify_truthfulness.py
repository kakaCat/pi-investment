"""每日任务完成通知的如实性回归锁（REQ-261005210015-1603 t-cef289）

覆盖：耗时量级（FR-1）、摘要带状态分布且不再 dump 内部字段（FR-2）、
零有效产出改 ⚠️（FR-3）、空转连续次数与降级（FR-5）、
失败判定不变式与台账 status 不动（FR-6）、其他任务摘要逐字不变（FR-2/FR-7）。

**打桩点铁律**（REQ-261003150739-b98d 的教训）：`_run_job` 读的是 **runtime 模块自己的全局名**
（文件内 `from ...alerting import _send_feishu, _summarize_result`），所以桩必须打在 `runtime`；
打在 `alerting` 或转发壳 `daily_jobs_bootstrap` 上会**静默失效、真函数照发**（4 张假卡片的来源）。
"""
from datetime import date, time as dtime

import pytest

from adapters.inbound.fastapi_app.daily_jobs import alerting, pipeline, runtime
from adapters.inbound.fastapi_app.daily_jobs.defs import JobDef
from infrastructure.scheduler.job_executor import find_result_failure

# 2026-10-05 生产现场的真实计数：5 行全 NULL（2 条 insufficient_sample + 3 条 no_trades）
REAL_DETAIL = {'window_end': '2026-10-05', 'accounts_total': 5, 'computed': 5,
               'computed_ok': 0, 'insufficient_sample': 2, 'no_trades': 3,
               'data_gap': 0, 'other': 0, 'aligned_days': 14}
JOB_DESC = 'B链账户行为双侧捕获 fitness 续采（RFC 012 P3，8/14 断点恢复；账户行为域，非策略参数进化）'


def _result(computed_ok: int = 0, **over) -> dict:
    """按 interfaces.md 契约 B 造 handler 返回值（默认 = 零有效产出的真实形态）。"""
    detail = dict(REAL_DETAIL, computed_ok=computed_ok, **over)
    summary = (f"有效 {computed_ok}（样本不足 {detail['insufficient_sample']}"
               f" / 无成交 {detail['no_trades']} / 数据缺口 {detail['data_gap']}）")
    return {'detail': detail, 'summary': summary, 'no_output': computed_ok == 0,
            'note': '账户行为 fitness（非策略参数进化）'}


def _job(handler) -> JobDef:
    return JobDef('evolution_fitness', dtime(20, 35), (0, 1, 2, 3, 4), handler, JOB_DESC)


class _Capture:
    def __init__(self):
        self.texts = []
        self.marks = []


@pytest.fixture
def sent(monkeypatch):
    """捕获宿主发出的通知文本；台账写入换成桩（不碰库），桩打在 runtime 模块。"""
    cap = _Capture()
    monkeypatch.setattr(runtime, '_send_feishu',
                        lambda text: (cap.texts.append(text), True)[1])
    monkeypatch.setattr(runtime, '_mark_running', lambda *a, **k: None)
    monkeypatch.setattr(runtime, '_mark_done', lambda *a, **k: cap.marks.append((a, k)))
    return cap


@pytest.fixture
def handler_env(monkeypatch):
    """把 handler 依赖的服务与仓储换成桩（不碰生产库），返回 (Service, Repo) 类以便逐例改写。"""
    from adapters.outbound.repositories.evolution_fitness_repository import (
        EvolutionFitnessORMRepository as R,
    )
    from application.services.evolution.evolution_fitness_service import (
        EvolutionFitnessService as S,
    )
    monkeypatch.setattr(S, '__init__',
                        lambda self, **kw: setattr(self, 'fitness_repo', kw.get('fitness_repo')))
    monkeypatch.setattr(S, 'compute_all_accounts', lambda self, **kw: dict(REAL_DETAIL))
    monkeypatch.setattr(R, 'list_recent_window_ok_counts',
                        lambda self, limit=20: [(date(2026, 10, 5), 0),
                                                (date(2026, 10, 2), 0),
                                                (date(2026, 9, 12), 3)])
    monkeypatch.setattr(R, 'get_last_ok_window_end', lambda self, window_days=20: date(2026, 9, 12))
    return S, R


class TestElapsedFormat:
    """FR-1：耗时必须反映真实量级（1.21 秒曾印成「0.0 分钟」）。"""

    def test_format_elapsed_seconds_below_minute(self):
        assert alerting._format_elapsed(1.21) == '1.2 秒'
        assert alerting._format_elapsed(59.96) == '60.0 秒'
        assert alerting._format_elapsed(-1) == '0.0 秒'      # 时钟回拨兜底

    def test_format_elapsed_minutes_above_minute(self):
        assert alerting._format_elapsed(60.0) == '1.0 分钟'
        assert alerting._format_elapsed(125.0) == '2.1 分钟'


class TestSummaryTruthfulness:
    """FR-2：摘要要含状态分布，且不得是内部字段名的原样 dump。"""

    def test_summary_shows_state_distribution(self):
        text = alerting._summarize_result(_result())
        assert '有效 0' in text
        assert '样本不足 2' in text and '无成交 3' in text and '数据缺口 0' in text
        assert 'detail[computed=' not in text

    def test_other_job_summary_unchanged(self):
        """无 summary 的任务输出逐字不变；但 handler 忘写 summary 时零产出仍要看得见。"""
        legacy = {'kline_sync': {'status': 'success', 'updated': 3}}
        assert alerting._summarize_result(legacy) == 'kline_sync[updated=3, status=success]'
        fallback = alerting._summarize_result({'computed_ok': 0, 'no_output': True, 'detail': {}})
        assert '无有效产出=True' in fallback


class TestHostTone:
    """FR-3 / FR-6 旧口径已被 REQ-261006165125-23a9 改写（本需求 FR-2 / FR-7）：

    - 零有效产出 = "本次没有事情发生" → **默认一条消息都不发**（用户裁定 A / D-2），
      台账 status 必须仍是 success（静默只发生在消息层）；
    - 旧口径（⚠️ 语气、完成仍要发）只在**回滚态**（`DAILY_JOBS_NOTIFY_NOOP=true`）可达——
      它作为 FR-7 的回滚面被保留，不再是一般路径的默认行为。
    """

    def test_zero_output_is_silent_by_default(self, sent):
        runtime._run_job(_job(lambda: _result()), '2026-10-05')
        assert sent.texts == [], sent.texts
        assert sent.marks and sent.marks[-1][0][2] == 'success'

    def test_zero_output_warns_only_in_legacy_mode(self, sent, monkeypatch):
        monkeypatch.setenv('DAILY_JOBS_NOTIFY_NOOP', 'true')
        runtime._run_job(_job(lambda: _result()), '2026-10-05')
        assert len(sent.texts) == 2, sent.texts          # 回滚态：开始 + 完成
        assert sent.texts[-1].startswith('⚠️ 每日任务完成（无有效产出）：evolution_fitness')

    def test_nonzero_output_keeps_success_title(self, sent):
        runtime._run_job(
            _job(lambda: _result(computed_ok=3, no_trades=2, insufficient_sample=0)), '2026-10-05')
        assert sent.texts[-1].startswith('✅ 每日任务完成：evolution_fitness')

    def test_elapsed_line_rendered_by_formatter(self, sent):
        # 有产出才会有完成消息（无事默认静默），故此处构造有产出的结果
        runtime._run_job(
            _job(lambda: _result(computed_ok=3, no_trades=2, insufficient_sample=0)), '2026-10-05')
        line = [ln for ln in sent.texts[-1].split('\n') if ln.startswith('耗时: ')][0]
        assert line.endswith('秒'), line          # 秒级任务不得再印成「分钟」

    def test_mark_done_status_stays_success(self, sent):
        runtime._run_job(_job(lambda: _result()), '2026-10-05')
        assert sent.marks and sent.marks[-1][0][2] == 'success'

    def test_new_result_shape_not_judged_failed(self):
        """FR-6：新结果形状不得被失败判定误伤（含陷阱 1 的不变式）。"""
        assert find_result_failure(_result()) is None
        assert find_result_failure({'detail': dict(REAL_DETAIL), 'no_output': True}) is None


class TestIdleStreak:
    """FR-5：空转必须跨天可见；读数失败只降级、不判失败。"""

    def test_idle_streak_phrase_when_two_zero_windows(self, handler_env):
        r = pipeline._job_evolution_fitness()
        assert '已连续 2 次无有效产出（最近有效：2026-09-12）' in r['summary']
        assert r['no_output'] is True

    def test_no_streak_phrase_when_output_exists(self, handler_env, monkeypatch):
        S, _R = handler_env
        monkeypatch.setattr(S, 'compute_all_accounts',
                            lambda self, **kw: dict(REAL_DETAIL, computed_ok=3,
                                                    no_trades=2, insufficient_sample=0))
        r = pipeline._job_evolution_fitness()
        assert '无有效产出' not in r['summary']
        assert r['no_output'] is False

    def test_streak_capped_renders_ge_k(self, handler_env, monkeypatch):
        _S, R = handler_env
        monkeypatch.setattr(R, 'list_recent_window_ok_counts',
                            lambda self, limit=20: [(date(2026, 10, 5), 0)] * 20)
        r = pipeline._job_evolution_fitness()
        assert '已连续 ≥20 次无有效产出' in r['summary']

    def test_first_idle_window_wording(self, handler_env, monkeypatch):
        _S, R = handler_env
        monkeypatch.setattr(R, 'list_recent_window_ok_counts',
                            lambda self, limit=20: [(date(2026, 10, 5), 0)])
        monkeypatch.setattr(R, 'get_last_ok_window_end', lambda self, window_days=20: None)
        r = pipeline._job_evolution_fitness()
        assert '本次无有效产出（最近有效：从未）' in r['summary']

    def test_streak_query_failure_degrades_loudly(self, handler_env, monkeypatch, capsys, sent):
        _S, R = handler_env

        def boom(*a, **k):
            raise RuntimeError('db down')

        monkeypatch.setattr(R, 'list_recent_window_ok_counts', boom)
        r = pipeline._job_evolution_fitness()
        assert '空转统计不可用' in r['summary']
        captured = capsys.readouterr()
        assert 'evolution_fitness_idle_stats_failed' in (captured.out + captured.err)
        # 报告写不出来不许把一次成功的采集判失败：宿主仍记 success
        runtime._run_job(_job(lambda: r), '2026-10-05')
        assert sent.marks[-1][0][2] == 'success'
