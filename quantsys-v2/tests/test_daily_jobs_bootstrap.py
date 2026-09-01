"""daily_jobs_bootstrap 调度逻辑单测

覆盖（2026-09-02 工程纪律：故障路径必须故障注入实测）：
- is_due 全分支：工作日/周末/未到点/已成功/运行中/僵死重跑/失败不自动重跑
- _last_trading_day 边界：盘中/盘后/周末/周一
"""
from datetime import datetime, timedelta, time as dtime

from adapters.inbound.fastapi_app.daily_jobs_bootstrap import (
    JobDef, is_due, _last_trading_day, _RUNNING_STALE_HOURS,
)


def _job(run_at=dtime(15, 40), weekdays=(0, 1, 2, 3, 4)):
    return JobDef('test_job', run_at, weekdays, lambda: {}, '测试任务')


class TestIsDue:
    def test_due_when_past_time_and_no_run(self):
        # 周二 16:00，无记录 → 应跑
        now = datetime(2026, 9, 1, 16, 0)  # 周二
        assert is_due(_job(), now, None) is True

    def test_not_due_before_time(self):
        now = datetime(2026, 9, 1, 15, 39)  # 周二 15:39，未到 15:40
        assert is_due(_job(), now, None) is False

    def test_not_due_on_weekend(self):
        now = datetime(2026, 9, 5, 16, 0)  # 周六
        assert is_due(_job(), now, None) is False

    def test_saturday_job_runs_on_saturday(self):
        job = _job(run_at=dtime(20, 0), weekdays=(5,))
        assert is_due(job, datetime(2026, 9, 5, 20, 1), None) is True
        assert is_due(job, datetime(2026, 9, 1, 20, 1), None) is False

    def test_not_due_after_success(self):
        now = datetime(2026, 9, 1, 16, 0)
        last = {'status': 'success', 'started_at': now}
        assert is_due(_job(), now, last) is False

    def test_not_due_while_running_fresh(self):
        now = datetime(2026, 9, 1, 16, 0)
        last = {'status': 'running', 'started_at': now - timedelta(minutes=30)}
        assert is_due(_job(), now, last) is False

    def test_due_when_running_stale(self):
        """僵死恢复：running 超阈值（进程死在任务里）允许重跑"""
        now = datetime(2026, 9, 1, 20, 0)
        last = {'status': 'running',
                'started_at': now - timedelta(hours=_RUNNING_STALE_HOURS + 1)}
        assert is_due(_job(), now, last) is True

    def test_not_due_after_failed(self):
        """失败不自动重跑（等告警人工处理/手动 force），防止失败风暴"""
        now = datetime(2026, 9, 1, 16, 0)
        last = {'status': 'failed', 'started_at': now - timedelta(minutes=10)}
        assert is_due(_job(), now, last) is False

    def test_catchup_after_late_process_start(self):
        """漏跑补跑：进程 17:00 才启动，15:40 的任务应补跑"""
        now = datetime(2026, 9, 1, 17, 0)
        assert is_due(_job(), now, None) is True


class TestLastTradingDay:
    def test_weekday_after_close(self):
        # 周二 16:00 → 今天
        assert _last_trading_day(datetime(2026, 9, 1, 16, 0)) == '2026-09-01'

    def test_weekday_before_close(self):
        # 周二 10:00 → 前一工作日（周一）
        assert _last_trading_day(datetime(2026, 9, 1, 10, 0)) == '2026-08-31'

    def test_weekend(self):
        # 周六任意时间 → 周五
        assert _last_trading_day(datetime(2026, 9, 5, 18, 0)) == '2026-09-04'

    def test_monday_morning(self):
        # 周一 9:20 → 上周五
        assert _last_trading_day(datetime(2026, 9, 7, 9, 20)) == '2026-09-04'
