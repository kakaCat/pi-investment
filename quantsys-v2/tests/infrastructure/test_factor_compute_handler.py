"""_handle_factor_compute 修复测试（2026-08-04）

根因：get_daily_klines 自 ORM 重构后返回 polars DataFrame，handler 按 list-of-dicts
写（`if not klines` 对 DataFrame 抛 TypeError）→ 5528 只全 error 却报 success（假成功）。
"""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from infrastructure.scheduler.scheduler import SchedulerService


def _fake_klines_df(days=30):
    """构造 polars DataFrame 形式的 K 线（与 get_daily_klines 契约一致）"""
    base = date(2026, 7, 1)
    return pl.DataFrame({
        'trade_date': [base + timedelta(days=i) for i in range(days)],
        'open': [10.0 + i * 0.1 for i in range(days)],
        'high': [10.2 + i * 0.1 for i in range(days)],
        'low': [9.8 + i * 0.1 for i in range(days)],
        'close': [10.1 + i * 0.1 for i in range(days)],
        'volume': [1000000] * days,
        'amount': [1e7] * days,
    })


def _make_ds(klines):
    ds = MagicMock()
    ds.kline.get_daily_klines = MagicMock(return_value=klines)
    ds.factor.save_factors = MagicMock(return_value=True)
    return ds


class TestFactorComputeHandler:
    def test_polars_dataframe_input_computes_factors(self):
        svc = SchedulerService(ds=_make_ds(_fake_klines_df()))
        with patch('domain.quantlib.stages.factor_stage.FactorStage') as MockStage:
            MockStage.return_value.process.return_value = {'factors': {'rsi14': 55.0, 'ma5': 10.5}}
            result = svc._handle_factor_compute({'symbols': ['600000', '000001']})

        assert result['symbols_computed'] == 2
        assert result['errors'] == 0
        assert result['factor_count'] == 4
        assert result['status'] == 'success'
        # save_factors 收到的是 list-of-dicts 适配后的最新交易日
        svc.ds.factor.save_factors.assert_called()

    def test_list_input_still_works(self):
        """兼容旧的 list-of-dicts 返回"""
        ds = _make_ds([{'trade_date': date(2026, 7, 31), 'close': 10.0, 'open': 9.9,
                        'high': 10.2, 'low': 9.8, 'volume': 1000}] * 25)
        svc = SchedulerService(ds=ds)
        with patch('domain.quantlib.stages.factor_stage.FactorStage') as MockStage:
            MockStage.return_value.process.return_value = {'factors': {'rsi14': 55.0}}
            result = svc._handle_factor_compute({'symbols': ['600000']})
        assert result['symbols_computed'] == 1
        assert result['errors'] == 0

    def test_total_failure_marks_status_failed(self):
        """全部失败时必须显式 failed（假成功修复）"""
        ds = _make_ds(_fake_klines_df())
        ds.kline.get_daily_klines = MagicMock(side_effect=RuntimeError('boom'))
        svc = SchedulerService(ds=ds)
        result = svc._handle_factor_compute({'symbols': ['600000', '000001']})
        assert result['symbols_computed'] == 0
        assert result['errors'] == 2
        assert result['status'] == 'failed'

    def test_insufficient_klines_not_error(self):
        """数据不足是正常跳过（新上市/停牌），不计 error"""
        svc = SchedulerService(ds=_make_ds(_fake_klines_df(days=5)))
        result = svc._handle_factor_compute({'symbols': ['600000']})
        assert result['symbols_computed'] == 0
        assert result['errors'] == 0
        assert result['status'] == 'success'


class TestDataServiceFactory:
    def test_injected_ds_is_reused(self):
        """显式注入的 ds（测试/调用方提供）被复用"""
        ds = _make_ds(_fake_klines_df())
        svc = SchedulerService(ds=ds)
        assert svc._create_data_service() is ds

    def test_lazy_ds_not_shared_across_threads(self):
        """未注入时每次返回新实例——防止 lazy property 缓存后 8 线程共享
        （2026-08-04 全量回填 IllegalStateChangeError 根因）"""
        svc = SchedulerService()
        with patch('application.services.data_service.DataService') as MockDS:
            MockDS.side_effect = lambda: MagicMock(name='ds')
            _ = svc.ds          # 模拟 handler 选股时触发 lazy 缓存
            cached = svc._ds
            b = svc._create_data_service()
        assert b is not cached   # 工作线程必须拿新实例，不是缓存的共享实例
