"""End-to-end integration test for strategy validation"""
import pytest
from application.services.strategy_validation_service import StrategyValidationService
from adapters.outbound.repositories import StockORMRepository, StrategyORMRepository


# 2026-10-02（REQ-261001145152-3982 · P1-8）：**移除"探测已删端点"的跳过守卫**。
#
# 该守卫此前的作用是：探测 `POST /api/backtest/batch` → 404 → 精确跳过，并写明
# "策略验证流程当前是断的，替换方案属取舍、需先拍板"。**方案已裁定为 B（进程内调服务）**
# 并已落地（见 `StrategyValidationService._call_batch_backtest` 的文档字符串），
# 故本测试不再依赖那个端点，守卫随之删除 —— 让用例真正跑**进程内**这条路径。


def test_strategy_validation_e2e():
    """
    End-to-end test: validate strategies with real database

    This test requires:
    - PostgreSQL running with test database
    - At least 2 strategies in quant.strategy_configs
    - K-line data for at least 2 stocks
    """
    # Arrange
    # 2026-10-02（REQ-261001145152-3982 审查）：**显式注入真仓储**。
    # 原为 `StrategyValidationService()` 空构造 —— 其内部走 `ServiceFactory.resolve(...)`，
    # 而测试环境未执行 `register_all_services()`，根 conftest 的容错层会把"未注册"兜成
    # **MagicMock** → 服务里 `len(strategies)` 得 **0**（MagicMock 的 `__len__` 就是 0）→
    # 报 `assert 0 >= 2`，**看起来像库里没策略**（实测库里策略 312 条）。
    # 该类支持构造注入，故直接注入真仓储，让用例测的是真路径。
    strategy_repo = StrategyORMRepository()
    validation_service = StrategyValidationService(
        strategy_repo=strategy_repo,
        stock_repo=StockORMRepository(),
    )

    # Get existing strategies
    strategies = strategy_repo.get_all(active_only=False)
    if len(strategies) < 2:
        pytest.skip("Need at least 2 strategies for integration test")

    # Act - dry run mode to avoid modifying database
    result = validation_service.validate_all_strategies(
        start_date='2025-05-01',
        end_date='2025-06-01',
        threshold=60.0,
        dry_run=True
    )

    # Assert
    assert result['total'] >= 2
    assert result['passed'] + result['failed'] == result['total']
    assert result['duration'] > 0
    assert len(result['details']) == result['total']

    # Verify detail structure
    for detail in result['details']:
        assert 'strategy_id' in detail
        assert 'strategy_name' in detail
        assert 'score' in detail
        assert 'status' in detail
        assert detail['status'] in ['passed', 'failed']
        assert 0 <= detail['score'] <= 100
        assert 'metrics' in detail
        assert 'backtest_count' in detail
        assert 'error_count' in detail


@pytest.mark.integration
def test_validation_report_persistence():
    """Test that validation reports are saved correctly"""
    # Arrange
    validation_service = StrategyValidationService()
    strategy_repo = StrategyORMRepository()

    strategies = strategy_repo.get_all(active_only=False)
    if len(strategies) < 1:
        pytest.skip("Need at least 1 strategy for integration test")

    # Act - run validation without dry_run
    result = validation_service.validate_all_strategies(
        start_date='2025-05-01',
        end_date='2025-06-01',
        threshold=60.0,
        dry_run=False
    )

    # Assert - verify reports were saved
    # Note: This test modifies the database, so it should clean up after itself
    # or run in a transaction that gets rolled back
    assert result['total'] > 0

    # Verify at least one strategy has validation_status set
    for detail in result['details']:
        strategy = strategy_repo.get_by_id(detail['strategy_id'])
        assert strategy is not None
        assert 'validation_status' in strategy
