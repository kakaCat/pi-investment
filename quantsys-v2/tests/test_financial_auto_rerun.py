"""财报自动重跑 / 自动补救 与 跨日补跑 回归（2026-09-13，w-32314d00）

背景（用户指令「需要自动重跑」）：
- quant.balance_sheets 此前**没有任何写入通道**（最新停 2026-03-31），
  而财报时效性巡检/数据契约以它为口径 → 每天 09:00 判"超期"却永远修不了；
  用户手动跑 financial_data_update_job 也只刷 quant.stocks 指标列，修不到这张表。
- 本文件锁：①资产负债表映射（报告日/口径/空行丢弃）；②逾期自动触发重跑（每天一次、可冷却）；
  ③宿主跨日补跑（失败过的任务不必等下一个排班日）。
"""
from datetime import datetime, time as dtime, timedelta

import pytest

from infrastructure.jobs.financial_statement_update_job import _map_balance_rows
from infrastructure.jobs import financial_timeliness_check_job as tj
from adapters.inbound.fastapi_app.daily_jobs_bootstrap import JobDef, catchup_due


# ---------------------------------------------------------------------------
# ① 资产负债表映射
# ---------------------------------------------------------------------------

def _row(**kw):
    base = {'报告日': '20260630', '资产总计': 100.0, '负债合计': 40.0,
            '所有者权益(或股东权益)合计': 60.0, '流动资产合计': 30.0, '流动负债合计': 20.0}
    base.update({k: v for k, v in kw.items() if v is not None})
    for k, v in kw.items():
        if v is None:
            base.pop(k, None)
    return base


def test_map_balance_rows_normalizes_report_date_and_period_type():
    recs = _map_balance_rows('600519', [_row()])
    assert len(recs) == 1
    r = recs[0]
    assert r['symbol'] == '600519'
    assert r['report_date'] == '2026-06-30'
    assert r['period_type'] == 'Q'
    assert r['total_assets'] == 100.0 and r['total_liabilities'] == 40.0
    assert r['total_equity'] == 60.0


def test_map_balance_rows_marks_annual_report():
    recs = _map_balance_rows('600519', [_row(**{'报告日': '20251231'})])
    assert recs[0]['report_date'] == '2025-12-31'
    assert recs[0]['period_type'] == 'Y'


def test_map_balance_rows_drops_empty_rows():
    """关键金额全空的行不写空壳（避免"有行无数据"污染覆盖率统计）。"""
    empty = {'报告日': '20260630', '资产总计': None, '负债合计': None,
             '所有者权益(或股东权益)合计': None, '流动资产合计': None, '流动负债合计': None}
    assert _map_balance_rows('600519', [empty]) == []


def test_map_balance_rows_does_not_compute_ratios():
    """debt_ratio/current_ratio 单位口径未统一 → 留 NULL（宁缺勿猜）。"""
    r = _map_balance_rows('600519', [_row()])[0]
    assert 'debt_ratio' not in r and 'current_ratio' not in r


def test_map_balance_rows_tolerates_missing_optional_fields():
    """部分标的缺「非流动负债合计」——不能因此整行丢弃（实测 5 只里 2 只如此）。"""
    r = _map_balance_rows('600036', [_row(**{'非流动负债合计': None})])[0]
    assert r['non_current_liabilities'] is None
    assert r['total_assets'] == 100.0


# ---------------------------------------------------------------------------
# ② 逾期自动触发重跑
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_auto_state(monkeypatch):
    monkeypatch.setattr(tj, '_last_auto_attempt_at', None)
    monkeypatch.setattr(tj, '_already_attempted_today', lambda: False)


def test_auto_remediation_triggers_once(monkeypatch):
    calls = []
    monkeypatch.setattr(tj, '_run_statement_update', lambda: calls.append(1))
    status = tj._maybe_auto_remediate({'is_overdue': True})
    assert status == 'triggered'
    for _ in range(50):          # 后台线程启动需要一点时间
        if calls:
            break
        import time as _t
        _t.sleep(0.02)
    assert calls == [1]


def test_auto_remediation_cools_down(monkeypatch):
    monkeypatch.setattr(tj, '_run_statement_update', lambda: None)
    assert tj._maybe_auto_remediate({'is_overdue': True}) == 'triggered'
    assert tj._maybe_auto_remediate({'is_overdue': True}) == 'cooling_down'


def test_auto_remediation_skips_when_host_already_ran_today(monkeypatch):
    monkeypatch.setattr(tj, '_already_attempted_today', lambda: True)
    monkeypatch.setattr(tj, '_run_statement_update',
                        lambda: pytest.fail('宿主今天已跑过，不应重复触发'))
    assert tj._maybe_auto_remediate({'is_overdue': True}) == 'already_today'


def test_auto_remediation_respects_disable_flag(monkeypatch):
    monkeypatch.setattr(tj, '_run_statement_update',
                        lambda: pytest.fail('显式关闭时不应触发'))
    assert tj._maybe_auto_remediate({'auto_remediate': False}) == 'disabled'
    assert tj._maybe_auto_remediate({'dry_run': True}) == 'disabled'


def test_alert_text_mentions_auto_remediation():
    assert 'triggered' in tj._REMEDIATION_TEXT
    assert '自动触发' in tj._REMEDIATION_TEXT['triggered']


# ---------------------------------------------------------------------------
# ③ 宿主跨日补跑
# ---------------------------------------------------------------------------

SAT_JOB = JobDef('financial_statements', dtime(20, 0), (5,), lambda: {}, '周六任务')


def test_catchup_runs_on_non_scheduled_day_after_failure():
    """周六失败 → 周日 20:10 补跑（原来要等下周六，一周空窗）。"""
    sunday = datetime(2026, 9, 13, 20, 10)   # 周日
    assert catchup_due(SAT_JOB, sunday, has_recent_failure=True) is True


def test_no_catchup_without_recent_failure():
    sunday = datetime(2026, 9, 13, 20, 10)
    assert catchup_due(SAT_JOB, sunday, has_recent_failure=False) is False


def test_no_catchup_before_scheduled_time_of_day():
    sunday = datetime(2026, 9, 13, 9, 0)     # 未到 20:00
    assert catchup_due(SAT_JOB, sunday, has_recent_failure=True) is False


def test_no_catchup_on_scheduled_day():
    """排班日交给 is_due（含 2h 失败重试），避免双跑。"""
    saturday = datetime(2026, 9, 12, 20, 10)
    assert catchup_due(SAT_JOB, saturday, has_recent_failure=True) is False


def test_weekday_job_also_catches_up_on_weekend():
    job = JobDef('evening_pipeline', dtime(20, 30), (0, 1, 2, 3, 4), lambda: {}, '工作日任务')
    sunday = datetime(2026, 9, 13, 21, 0)
    assert catchup_due(job, sunday, has_recent_failure=True) is True
