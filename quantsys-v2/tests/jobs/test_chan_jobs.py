"""ChanScanJob / ChanKnowledgeDistillJob 测试——假成功壳修复（Fix⑥ 2026-09-05）

验证：
1. ChanScanJob.execute 委托真实 ChanScanService（注入三个 ORM repo），
   返回 JobResult.ok + 真实 summary（scanned/written/skipped/dup/err），
   不再假成功（scanned:0「待实现」）。
2. ChanKnowledgeDistillJob.execute 委托 ChanKnowledgeDistiller（注入三个
   ORM repo，params.window_days/lookback_days 正确透传），返回真实蒸馏计数。

修复背景：analysis_jobs.py 两 execute 原为占位空壳（恒 scanned:0 / distilled:0
报 ok），自 09-02 JobRegistry 接管后每日假成功落库；真实 ChanScanService /
ChanKnowledgeDistiller 08-21 P2-1 DI 改造后须显式注入 repo（legacy 无参构造
pool_repo=None 会崩）。本测试用 mock 服务验证 execute 委托与契约，不触 DB。
"""
from unittest.mock import MagicMock, patch
import pytest

from application.jobs.analysis_jobs import ChanScanJob, ChanKnowledgeDistillJob


class TestChanScanJob:
    @pytest.mark.asyncio
    async def test_delegates_chan_scan_service_and_reports_real_summary(self):
        summary = {
            'scanned': 66, 'signals_written': 2,
            'duplicates': 0, 'skipped': 13, 'errors': 0,
        }
        mock_scan = MagicMock()
        mock_scan.scan.return_value = summary

        with patch('application.services.chan_scan_service.ChanScanService', return_value=mock_scan), \
             patch('application.services.chan_service.ChanService'), \
             patch('adapters.outbound.repositories.kline_repository.KlineORMRepository'), \
             patch('adapters.outbound.repositories.stock_pool_repository.StockPoolRepository'), \
             patch('adapters.outbound.repositories.signal_repository.SignalORMRepository'):
            result = await ChanScanJob().execute({})

        assert result.success is True
        assert result.action == 'chan_scan'
        assert result.details['scanned'] == 66
        assert result.details['signals_written'] == 2
        assert result.details['errors'] == 0
        assert '待实现' not in result.message
        assert 'scanned=66' in result.message
        # 注入链：ChanService(kline_repo=KlineORMRepository()) 显式传 repo
        mock_scan.scan.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_fails_honestly_on_exception(self):
        mock_scan = MagicMock()
        mock_scan.scan.side_effect = RuntimeError('repo 连接失败')

        with patch('application.services.chan_scan_service.ChanScanService', return_value=mock_scan), \
             patch('application.services.chan_service.ChanService'), \
             patch('adapters.outbound.repositories.kline_repository.KlineORMRepository'), \
             patch('adapters.outbound.repositories.stock_pool_repository.StockPoolRepository'), \
             patch('adapters.outbound.repositories.signal_repository.SignalORMRepository'):
            result = await ChanScanJob().execute({})

        assert result.success is False
        assert 'repo 连接失败' in result.error
        assert result.action == 'chan_scan'


class TestChanKnowledgeDistillJob:
    @pytest.mark.asyncio
    async def test_delegates_distiller_with_params(self):
        distill_result = {
            'strategies_distilled': 6, 'signals_total': 33, 'signals_excluded': 1,
        }
        mock_distill = MagicMock()
        mock_distill.distill.return_value = distill_result

        captured_kwargs = {}

        def _fake_init(self, **kwargs):
            captured_kwargs.update(kwargs)
            self._kwargs = kwargs

        with patch('application.services.chan_knowledge_distiller.ChanKnowledgeDistiller', autospec=True) as mock_cls:
            mock_cls.return_value = mock_distill
            # autospec 下直接验证构造 kwargs
            result = await ChanKnowledgeDistillJob().execute({'window_days': 25, 'lookback_days': 120})
            call_kwargs = mock_cls.call_args.kwargs

        assert result.success is True
        assert result.action == 'chan_knowledge_distill'
        assert result.details['strategies_distilled'] == 6
        assert result.details['signals_total'] == 33
        assert '待实现' not in result.message
        # params 透传 + 默认值兜底
        assert call_kwargs['window_days'] == 25
        assert call_kwargs['lookback_days'] == 120
        # 三个 repo 都注入（DI 改造后无参构造不可用）
        for key in ('signal_repo', 'kline_repo', 'knowledge_repo'):
            assert key in call_kwargs, f"缺失注入依赖 {key}"

    @pytest.mark.asyncio
    async def test_uses_default_window_days_when_params_empty(self):
        distill_result = {'strategies_distilled': 0, 'signals_total': 0, 'signals_excluded': 0}
        mock_distill = MagicMock()
        mock_distill.distill.return_value = distill_result

        with patch('application.services.chan_knowledge_distiller.ChanKnowledgeDistiller', autospec=True) as mock_cls:
            mock_cls.return_value = mock_distill
            result = await ChanKnowledgeDistillJob().execute({})
            call_kwargs = mock_cls.call_args.kwargs

        assert result.success is True
        assert call_kwargs['window_days'] == 20
        assert call_kwargs['lookback_days'] == 90

    @pytest.mark.asyncio
    async def test_fails_honestly_on_exception(self):
        mock_distill = MagicMock()
        mock_distill.distill.side_effect = RuntimeError('kline repo 数据不足')

        with patch('application.services.chan_knowledge_distiller.ChanKnowledgeDistiller', autospec=True) as mock_cls:
            mock_cls.return_value = mock_distill
            result = await ChanKnowledgeDistillJob().execute({})

        assert result.success is False
        assert 'kline repo' in result.error
        assert result.action == 'chan_knowledge_distill'
