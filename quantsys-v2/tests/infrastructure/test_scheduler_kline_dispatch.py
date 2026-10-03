"""SchedulerService._execute_command 分发修复测试（2026-08-02 kline_update 接管）

背景：scheduler_tasks 表的 gem-kline-update（command='kline_update'）每个工作日 16:00
失败「Unknown scheduler command」——静态 handler map 缺 kline_update，且应用层
_TASK_HANDLERS 里的命令（如 pool_refresh_daily）没有 fallback 通路。
"""
from unittest.mock import patch

import pytest

from infrastructure.scheduler.scheduler import SchedulerService


@pytest.fixture
def svc():
    return SchedulerService()


class TestKlineUpdateDispatch:
    def test_kline_update_dispatches_to_job_execute(self, svc):
        with patch('infrastructure.jobs.kline_update_job.execute') as mock_exec:
            mock_exec.return_value = {'action': 'kline_update', 'status': 'success'}
            result = svc._execute_command('kline_update', {'days': 5})
        mock_exec.assert_called_once_with(days=5)
        assert result['status'] == 'success'

    def test_kline_update_empty_params(self, svc):
        with patch('infrastructure.jobs.kline_update_job.execute') as mock_exec:
            mock_exec.return_value = {'action': 'kline_update', 'status': 'success'}
            svc._execute_command('kline_update', {})
        mock_exec.assert_called_once_with()


class TestApplicationHandlerFallback:
    # 2026-10-02（REQ-261001145152-3982 审查）：**删除 `test_pool_refresh_daily_is_unknown_command`**。
    # 它断言的是**某一时刻的状态**（原 docstring：「**当前** scheduler 未将 pool_refresh_daily
    # 注册为有效命令」），而这个状态**随导入顺序变化**：
    #   · 单跑本文件 → 该命令未知 → 抛 ValueError → 用例绿；
    #   · 跑全量前缀 → `application/jobs/trading_jobs.py`（其中定义
    #     `command_name = "pool_refresh_daily"` 并带真实 handler）已被导入/注册 → 命令变已知
    #     → 不抛错 → `DID NOT RAISE ValueError`（**报错看着像"未知命令没拦住"**）。
    # 而"未知命令必须报错"这条**契约**已由**同文件的下一条** `test_unknown_command_still_raises`
    # 用真正未知的命令名覆盖 → 本用例既脆弱又冗余，故删除。
    # ⚠️ **开放问题（不在本次范围）**：`pool_refresh_daily` 到底**应不应该**可被 scheduler 派发？
    #    它已有 handler（`scheduler_tasks.handle_pool_refresh_daily`）却在硬编码派发表之外 ——
    #    若应可派发，属**能力缺口**（应接线）；若不应，应显式登记为未知。留给后续按需裁定。

    def test_unknown_command_still_raises(self, svc):
        with pytest.raises(ValueError, match="Unknown scheduler command"):
            svc._execute_command('definitely_not_a_command', {})


class TestChipDistributionDispatch:
    def test_chip_update_dispatches_to_job_execute(self, svc):
        with patch('infrastructure.jobs.chip_distribution_update_job.execute') as mock_exec:
            mock_exec.return_value = {'pending': 0, 'updated': 0, 'failed': 0, 'days_applied': 0}
            result = svc._execute_command('chip_distribution_update', {})
        mock_exec.assert_called_once_with()
        assert result['failed'] == 0
