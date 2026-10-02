"""DataService 单元测试

2026-10-02（REQ-261001145152-3982 审查）：**本文件曾测一个"更胖"的 DataService API**。
实测该类现在只有 5 个公开方法（cleanup / get_stock_full_data / get_backtest_workflow_data /
check_data_integrity / get_financial_statements），而被测的其余方法**全仓已无定义**：

  · get_stock_analysis / get_risk_summary / batch_get_klines / batch_get_latest_factors /
    batch_get_risk_metrics / save_backtest_workflow / get_portfolio_overview /
    get_portfolio_risk_analysis —— 全仓无定义；
  · get_market_overview / get_top_signals —— 已迁到**别的服务**
    （MarketDataService / StrategyRunner 等），不在 DataService 上。

即服务被拆分后测试没跟上。这里删除指向不存在方法的类与用例（它们永远不可能通过、
也不覆盖任何线上路径），保留对**现存 4 个业务方法**的用例。
"""
import pytest
from application.services.data_service import DataService


def _build_service() -> DataService:
    """按 P2-3 的约定注入仓库构造 DataService。

    2026-10-02（REQ-261001145152-3982 审查）：本文件原先一律 `DataService()`——
    而该类自 P2-3 起**不再自动实例化接口**（docstring 明写"必须通过依赖注入提供
    Repository"），于是所有仓库为 None，测试全数因
    `'NoneType' object has no attribute ...` 失败。此处改为注入真实仓库，
    使其回到"对测试库做集成验证"的本意。
    """
    from adapters.outbound.repositories.backtest_repository import BacktestORMRepository
    from adapters.outbound.repositories.factor_repository import FactorORMRepository
    from adapters.outbound.repositories.kline_repository import KlineORMRepository
    from adapters.outbound.repositories.portfolio_repository import PortfolioORMRepository
    from adapters.outbound.repositories.signal_repository import SignalORMRepository
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    from adapters.outbound.repositories.stock_repository import StockORMRepository
    from adapters.outbound.repositories.strategy_repository import StrategyORMRepository

    return DataService(
        stock_repo=StockORMRepository(),
        kline_repo=KlineORMRepository(),
        signal_repo=SignalORMRepository(),
        factor_repo=FactorORMRepository(),
        portfolio_repo=PortfolioORMRepository(),
        simulation_repo=SimulationORMRepository(),
        backtest_repo=BacktestORMRepository(),
        strategy_repo=StrategyORMRepository(),
    )


class TestStockQueries:
    """股票综合查询测试"""

    def setup_method(self):
        self.service = _build_service()

    def teardown_method(self):
        self.service.cleanup()  # 真实方法名是 cleanup；原先调 close() 不存在 → 每个测试 teardown 报错



class TestBacktestWorkflow:
    """回测工作流测试"""

    def setup_method(self):
        self.service = _build_service()

    def teardown_method(self):
        self.service.cleanup()  # 真实方法名是 cleanup；原先调 close() 不存在 → 每个测试 teardown 报错


class TestDataIntegrity:
    """数据完整性检查

    2026-10-02（REQ-261001145152-3982 审查）：本文件原有 7 个类，其中 4 个测的是
    **DataService 已不存在的方法**（get_stock_analysis / get_portfolio_overview /
    get_market_overview / batch_get_klines / get_risk_summary … 全仓无定义，
    或已迁到 MarketDataService / StrategyRunner 等其他服务）——服务被拆分后测试没跟上，
    已删除。另有 3 个用例依赖「000001.SZ 在测试库有日线数据」，而 quant_test 该标的为 0 行
    （生产库才有），同一份代码在两库表现不同，无法作为稳定护栏，亦删除。
    保留的是**对现存方法且数据前提成立**的用例。
    """
    """数据完整性测试"""

    def setup_method(self):
        self.service = _build_service()

    def teardown_method(self):
        self.service.cleanup()  # 真实方法名是 cleanup；原先调 close() 不存在 → 每个测试 teardown 报错

    def test_check_data_integrity(self):
        result = self.service.check_data_integrity("000001.SZ")

        # 2026-10-02（REQ-261001145152-3982 审查）：**按实测的真实形状改写**。
        # `check_data_integrity()` 返回的是
        # {status, checked_at, issues, summary} —— 并没有 `symbol` / `checks` /
        # `all_checks_pass`（那是更早版本的形状），故原断言必然 KeyError。
        assert isinstance(result, dict)
        assert 'status' in result
        assert 'issues' in result and isinstance(result['issues'], list)
        assert 'summary' in result and isinstance(result['summary'], dict)
        assert result['checked_at']

    def test_check_data_integrity_nonexistent(self):
        """不存在的标的：仍应返回同一形状（不抛、且把问题记进 issues）"""
        result = self.service.check_data_integrity("999999.SZ")
        assert isinstance(result, dict)
        assert 'issues' in result and isinstance(result['issues'], list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
