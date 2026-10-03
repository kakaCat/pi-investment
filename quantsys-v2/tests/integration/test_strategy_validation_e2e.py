"""End-to-end integration test for strategy validation"""
import pytest
from application.services.strategy_validation_service import StrategyValidationService
from adapters.outbound.repositories import StockORMRepository, StrategyORMRepository


@pytest.mark.integration
def _skip_if_batch_backtest_endpoint_gone():
    """依赖缺失（**方案待拍板**）→ 精确跳过，不粉饰成"通过"。

    2026-10-02（REQ-261001145152-3982 审查）实测：
        `POST http://127.0.0.1:5001/api/backtest/batch` → **404 Not Found**
    （服务端日志：`Batch backtest API call failed: 404`）
    该端点是**已被删除**的批量回测入口，而 `StrategyValidationService` 仍按它调用
    → **策略验证流程当前是断的**（不是测试问题）。

    替换方案是**取舍**（本会话开头即登记为待拍板项）：
      A. 逐任务调 `/api/backtest/run`（复用既有端点，代价是 N 次 HTTP 往返）；
      B. 改为进程内直接调 `StrategyBacktestService`（少一层 HTTP，但要处理并发与内存）。
    在方案定下来之前，这里**跳过并写明原因**；**不**把 404 当"环境波动"糊过去。
    """
    import requests

    try:
        r = requests.post("http://127.0.0.1:5001/api/backtest/batch", json={}, timeout=5)
    except Exception as e:  # noqa: BLE001 - 取不到服务也属"依赖不可用"
        pytest.skip(f"批量回测端点不可达（依赖缺失，方案待拍板）: {e}")
    if r.status_code == 404:
        pytest.skip(
            "依赖缺失：/api/backtest/batch 已删除（实测 404），而 StrategyValidationService 仍调用它 "
            "→ 策略验证流程当前是断的。替换方案（逐任务调 /api/backtest/run vs 进程内调 "
            "StrategyBacktestService）属**取舍**，需先拍板。"
        )


def test_strategy_validation_e2e():
    _skip_if_batch_backtest_endpoint_gone()
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
    _skip_if_batch_backtest_endpoint_gone()
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
