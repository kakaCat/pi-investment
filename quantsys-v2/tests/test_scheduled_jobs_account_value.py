# -*- coding: utf-8 -*-
"""
回归测试：调度 job 不得调用已移除的 SimulationORMRepository.get_account_total_value

背景（2026-07-28 事故）：
多账户域重构后 SimulationORMRepository 移除了 get_account_total_value()，
但 risk_check_job / verification_job 仍在调用，导致
v13_risk_check（每日 16:00）与 v13_verification（每日 15:30）连续失败：
    'SimulationORMRepository' object has no attribute 'get_account_total_value'

修复方向：账户总资产直接读取 account.total_value（由 update_position_prices 维护）。
本测试用一个【没有】get_account_total_value 方法的假仓库驱动 job.run()，
若 job 再次调用该方法即抛 AttributeError，测试失败。
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from infrastructure.jobs.risk_check_job import RiskCheckJob
from infrastructure.jobs.verification_job import VerificationJob


class FakeSimulationRepo:
    """只暴露多账户重构后真实存在的方法——刻意不含 get_account_total_value"""

    def __init__(self, account):
        self._account = account

    def get_account(self, account_name: str = 'default'):
        return self._account

    # verification_job 用例需要
    def get_trades_by_date(self, account_name: str, trade_date):
        return [SimpleNamespace(symbol='300001', direction='buy')]

    def count_rebalances(self, account_name: str = 'default') -> int:
        return 1


def _make_account():
    return SimpleNamespace(
        account_name='default',
        initial_capital=Decimal('1000000.00'),
        total_value=Decimal('1050000.00'),
        cumulative_return=Decimal('0.05'),
        last_rebalance_date=date(2026, 7, 21),
        created_at=date(2026, 7, 1),
    )


class TestRiskCheckJobAccountValue:
    def test_run_without_get_account_total_value(self):
        job = RiskCheckJob.__new__(RiskCheckJob)
        job.repo = FakeSimulationRepo(_make_account())
        job.feishu_notifier = None
        job.stop_loss_threshold = -0.10
        job.underperform_threshold = 0.10
        # 隔离外部依赖：指数收益
        job._get_index_return_since_start = lambda: 0.0

        # 修复前：AttributeError: get_account_total_value
        job.run()


class TestVerificationJobAccountValue:
    def test_run_without_get_account_total_value(self):
        job = VerificationJob.__new__(VerificationJob)
        job.repo = FakeSimulationRepo(_make_account())
        job.feishu_notifier = None
        job.config = {'strategy': {'rebalance_days': 7}}
        # 隔离外部依赖：交易日判断、K线收益
        job._is_trading_day = lambda date_str: True
        job._count_trading_days_between = lambda start, end: 5
        job._get_stock_return = lambda symbol, start, end: 0.10
        job._get_index_return = lambda start, end: 0.01

        # 修复前：AttributeError: get_account_total_value
        job.run()


# ============================================================
# handle_factor_compute 接口脱节回归测试
# ============================================================
# 背景（2026-07-28）：scheduler_tasks.handle_factor_compute 调用
# FactorAnalysisService.compute_factors() —— 该方法不存在
# （FactorAnalysisService 是 IC/收益分析服务，不是批量因子计算入口），
# 导致 daily_orchestrator 盘后 factor_compute 永远 failed：
#   'FactorAnalysisService' object has no attribute 'compute_factors'
# 修复方向：与 adapters/inbound/api/routes/jobs.py 的 compute_factors 一致，
# 走 FactorStage 计算 + ds.factor.save_factors 落库。
# ============================================================

from application.services import task_handlers as scheduler_tasks


class _FakeKlineDF:
    def is_empty(self):
        return False

    def to_dicts(self):
        return [{'trade_date': '2026-07-28', 'close': 10.5}] * 80


class _FakeFactorStage:
    def __init__(self, name, factor_names=None):
        self.factor_names = factor_names

    def process(self, stage_input):
        assert stage_input['klines'], 'klines 不能为空'
        return {'factors': {'rsi': 55.0, 'ma20': 10.2}}


class TestHandleFactorCompute:
    def test_compute_and_persist_via_factor_stage(self, monkeypatch):
        saved = []

        fake_ds = SimpleNamespace(
            kline=SimpleNamespace(get_daily_klines=lambda sym, s, e: _FakeKlineDF()),
            factor=SimpleNamespace(
                save_factors=lambda sym, dt, factors: saved.append((sym, dt, factors))
            ),
        )

        import infrastructure.services.service_factory as sf
        import domain.quantlib.stages.factor_stage as fs_mod

        monkeypatch.setattr(sf, 'get_data_service', lambda: fake_ds)
        monkeypatch.setattr(fs_mod, 'FactorStage', _FakeFactorStage)

        result = scheduler_tasks.handle_factor_compute({'symbols': ['300001']})

        # 修复前：status=failed, error="'FactorAnalysisService' object has no attribute 'compute_factors'"
        assert result['status'] == 'success', result
        assert result['factors_computed'] == 1
        assert saved == [('300001', '2026-07-28', {'rsi': 55.0, 'ma20': 10.2})]
