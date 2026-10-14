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

from application.services import scheduler_tasks


class _FakeKlineDF:
    def is_empty(self):
        return False

    def to_dicts(self):
        return [{'trade_date': '2026-07-28', 'close': 10.5}] * 80


class _FakeFactorStage:
    # handle_factor_compute 会读 stage.DEFAULT_TECHNICAL_FACTORS 做缺失因子统计，
    # 替身必须提供；否则 AttributeError 会被逐标的 except 吞成 failed
    # （表现成"算不出因子"，与真实缺陷一模一样，无法区分）
    DEFAULT_TECHNICAL_FACTORS = ('rsi', 'ma20')

    def __init__(self, name, factor_names=None):
        self.factor_names = factor_names

    def process(self, stage_input):
        assert stage_input['klines'], 'klines 不能为空'
        return {'factors': {'rsi': 55.0, 'ma20': 10.2}}


class TestHandleFactorCompute:
    """handle_factor_compute 的接口脱节回归

    ⚠️ 2026-09-14（w-32314d00）修测试与实现的**脱节**：本用例原先把
    monkeypatch 打在 infrastructure.services.service_factory.get_data_service 上，
    而该函数**根本不存在**（AttributeError 直接让用例失败）。handle_factor_compute
    现已改为直接走仓储 —— KlineORMRepository.get_daily_klines /
    FactorORMRepository.save_factors（2026-09-03 R1 与 2026-09-10 C 两次修复之后），
    不再经过任何 data_service。故 patch 点必须落回真实调用链；
    否则这个用例测的是一条早已不存在的路径（就算不报错也是 false green）。
    """

    def test_compute_and_persist_via_factor_stage(self, monkeypatch):
        saved = []

        import application.services.scheduler_tasks as st
        import domain.backtest.stages.factor_stage as fs_mod
        import adapters.outbound.repositories as repos

        # 预筛会查库里每只标的的 K 线根数——本用例只测编排，直接放行。
        # 2026-10-02（REQ-261001145152-3982 审查）：**打到真调用点**。
        # 该函数的定义与**内部调用**都在 `application.services.scheduler_tasks_factors`
        # （`scheduler_tasks.py` 只是把它**再导出**）；原先 patch `st._filter_factor_universe`
        # 改的是再导出的那个名字，**调用点看不见** → 真实预筛照样执行 → 测试库里标的 K 线不足
        # → 全被筛掉 → `symbols_count: 0` / `factors_computed: 0` → 断言失败
        # （报错只显示"0 == 1"，**看不出是打桩打偏了**）。故两处都打，避免再被搬家坑到。
        _pass = lambda syms, s, e: (list(syms), {  # noqa: E731
            'delisted': 0, 'st': 0, 'non_equity': 0,
            'insufficient_bars': 0, 'unknown': [], 'examples': []})
        import application.services.scheduler_tasks_factors as stf
        monkeypatch.setattr(stf, '_filter_factor_universe', _pass)
        monkeypatch.setattr(st, '_filter_factor_universe', _pass)
        monkeypatch.setattr(repos.KlineORMRepository, 'get_daily_klines',
                            lambda self, sym, s, e: _FakeKlineDF())
        monkeypatch.setattr(repos.FactorORMRepository, 'save_factors',
                            lambda self, sym, dt, factors: saved.append((sym, dt, factors)))
        # 资金流注入/提取会打库或外部源，与本用例无关。
        # 注意：这两个是在 handle_factor_compute 的**函数体内**从
        # adapters.shared.fund_flow_helpers 导入的，所以要 patch 源模块而非 scheduler_tasks。
        import adapters.shared.fund_flow_helpers as ff
        monkeypatch.setattr(ff, '_inject_fund_flow_to_klines', lambda klines, sym: klines)
        monkeypatch.setattr(ff, '_extract_fund_flow_factors', lambda klines: {})
        monkeypatch.setattr(fs_mod, 'FactorStage', _FakeFactorStage)

        result = scheduler_tasks.handle_factor_compute({'symbols': ['300001']})

        # 修复前：status=failed, error="'FactorAnalysisService' object has no attribute 'compute_factors'"
        assert result['status'] == 'success', result
        assert result['factors_computed'] == 1, result
        assert saved == [('300001', '2026-07-28', {'rsi': 55.0, 'ma20': 10.2})]


# ── 假仓库的「幽灵方法」门禁（REQ-261004154902-a7cd t13 / FR-1、FR-2）──────────
#
# 背景：本文件的 FakeSimulationRepo 提供了 `get_trades_by_date` 与 `count_rebalances`，
# 而**真实** `SimulationORMRepository` 并没有这两个方法（2026-10-04 实测）。
# 于是用例里 job 调它们「成功」，生产里同一行代码却是 AttributeError。
# 这正是「测试绿灯、链路必炸」的第三种假绿灯形态：Fake 比真实实现更宽松。
#
# 本断言的作用：①把已知缺口写死在明处；②从此禁止再往 Fake 里加第三个别处不存在的方法。
# 缺口本身（risk_check_job / verification_job 调不存在的仓储方法 + 硬编码 default 账户
# + 用不存在的 trade.direction 列）是**已登记的缺陷**（需求证据 E15），修它需要改那两个
# job，属独立工作量，不在本卡范围。

#: Fake 提供、真实仓储**没有**的方法（存量缺口，只许减不许增）
KNOWN_PHANTOM_REPO_METHODS = {"get_trades_by_date", "count_rebalances"}


def test_fake_repo_does_not_invent_repository_methods():
    from adapters.outbound.repositories.simulation_repository import (
        SimulationORMRepository,
    )

    real_methods = {name for name in dir(SimulationORMRepository) if not name.startswith("_")}
    fake_methods = {
        name for name in vars(FakeSimulationRepo) if not name.startswith("_")
    }

    phantom = fake_methods - real_methods

    assert phantom == KNOWN_PHANTOM_REPO_METHODS, (
        "假仓库凭空造出了真实仓储没有的方法（会让用例绿灯、生产 AttributeError）。\n"
        f"  新增的幽灵方法: {sorted(phantom - KNOWN_PHANTOM_REPO_METHODS)}\n"
        f"  已登记缺口（E15，只许减不许增）: {sorted(KNOWN_PHANTOM_REPO_METHODS)}\n"
        "  修法：要么把 Fake 换成真实存在的方法，要么把缺口登记进 KNOWN_PHANTOM_REPO_METHODS "
        "并在需求证据里写清为什么。"
    )


def test_phantom_repo_methods_are_still_absent_from_real_repository():
    """反向锁：一旦真实仓储补上了这些方法，就把它们从缺口清单里删掉。"""
    from adapters.outbound.repositories.simulation_repository import (
        SimulationORMRepository,
    )

    real_methods = {name for name in dir(SimulationORMRepository) if not name.startswith("_")}
    already_implemented = sorted(KNOWN_PHANTOM_REPO_METHODS & real_methods)

    assert not already_implemented, (
        f"真实仓储已经有这些方法了：{already_implemented} —— "
        "请从 KNOWN_PHANTOM_REPO_METHODS 中删除（缺口已闭合），并把 E15 的对应条目划掉。"
    )
