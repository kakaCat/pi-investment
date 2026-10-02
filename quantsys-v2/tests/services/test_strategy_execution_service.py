"""Tests for strategy execution service"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from application.services.strategy_execution_service import StrategyExecutionService
from adapters.outbound.repositories.models.strategy_execution import (
    StrategyExecuteRequest,
    StrategyBatchExecuteRequest,
    StrategyPipelineExecuteRequest
)


# 2026-10-02（REQ-261001145152-3982 审查）：本文件的 patch 目标集体失效——
# 原 fixture patch 的是 `strategy_execution_service.SignalORMRepository`，而该模块
# **已不再导入这个类**：依赖改为按端口经 ServiceFactory.resolve(...) 解析
# （见模块内 kline_repo/stock_repo/_strategy_repo 的延迟加载属性）。
# 于是 patch 抛 AttributeError，本文件 6 条测试**全部 ERROR**。
# 下面改为 patch 真实解析点，并按端口分派（只让信号仓库带定制行为，
# 其余端口给通用 MagicMock，避免顺手把 kline/stock 也 mock 坏）。
from domain.ports import (  # noqa: E402
    IKlineRepository,
    ISignalRepository,
    IStockRepository,
    IStrategyRepository,
)


def _fake_resolve(signal_repo):
    def _resolve(port):
        if port is ISignalRepository:
            return signal_repo
        return MagicMock()

    return _resolve


@pytest.fixture
def mock_signal_repo():
    fake_signal = MagicMock()
    fake_signal.create_signal.return_value = 123  # Mock signal ID
    with patch(
        'infrastructure.services.service_factory.ServiceFactory.resolve',
        side_effect=_fake_resolve(fake_signal),
    ):
        yield fake_signal


@pytest.fixture
def service(mock_signal_repo):
    return StrategyExecutionService()


@pytest.fixture
def mock_strategy_engine():
    with patch('application.services.strategy_execution_service.StrategyEngine') as mock:
        yield mock


def test_execute_single_strategy(service, mock_strategy_engine, mock_signal_repo):
    """测试单股策略执行"""
    # Mock 策略引擎返回
    mock_engine = Mock()
    mock_engine.execute.return_value = {
        'symbol': '000001.SH',
        'signal_type': 'BUY',
        'confidence': 0.85,
        'entry_price': 1850.0,
        'stop_loss': 1750.0,
        'target_price': 2050.0
    }
    mock_strategy_engine.return_value = mock_engine

    request = StrategyExecuteRequest(
        symbol="000001.SH",
        strategy_name="Turtle",
        persist=True
    )

    result = service.execute_single(request)

    assert result['symbol'] == '000001.SH'
    assert result['signal_type'] == 'BUY'
    assert result['confidence'] == 0.85
    assert 'signal_id' in result  # 持久化后应有 signal_id


def test_execute_single_without_persist(service, mock_strategy_engine, mock_signal_repo):
    """测试不持久化的单股执行"""
    mock_engine = Mock()
    mock_engine.execute.return_value = {
        'symbol': '000001.SH',
        'signal_type': 'HOLD',
        'confidence': 0.55,
        'entry_price': 1850.0
    }
    mock_strategy_engine.return_value = mock_engine

    request = StrategyExecuteRequest(
        symbol="000001.SH",
        strategy_name="Turtle",
        persist=False
    )

    result = service.execute_single(request)

    assert 'signal_id' not in result  # 不持久化不应有 signal_id


def test_execute_batch_strategies(service, mock_strategy_engine, mock_signal_repo):
    """测试批量策略执行"""
    mock_engine = Mock()
    mock_engine.execute.side_effect = [
        {'symbol': '000001.SH', 'signal_type': 'BUY', 'confidence': 0.85, 'entry_price': 1850.0},
        {'symbol': '000001.SZ', 'signal_type': 'HOLD', 'confidence': 0.55, 'entry_price': 12.5}
    ]
    mock_strategy_engine.return_value = mock_engine

    request = StrategyBatchExecuteRequest(
        symbols=["000001.SH", "000001.SZ"],
        strategy_name="Turtle",
        persist=True
    )

    results = list(service.execute_batch(request))

    # 应该返回 2 个信号 + 1 个摘要
    assert len(results) == 3
    assert results[0]['type'] == 'signal'
    assert results[1]['type'] == 'signal'
    assert results[2]['type'] == 'summary'
    assert results[2]['data']['total'] == 2


def test_execute_batch_with_errors(service, mock_strategy_engine, mock_signal_repo):
    """测试批量执行时的错误隔离"""
    mock_engine = Mock()
    mock_engine.execute.side_effect = [
        {'symbol': '000001.SH', 'signal_type': 'BUY', 'confidence': 0.85, 'entry_price': 1850.0},
        Exception("数据不足"),
        {'symbol': '000002.SZ', 'signal_type': 'SELL', 'confidence': 0.75, 'entry_price': 8.5}
    ]
    mock_strategy_engine.return_value = mock_engine

    request = StrategyBatchExecuteRequest(
        symbols=["000001.SH", "000001.SZ", "000002.SZ"],
        strategy_name="Turtle"
    )

    results = list(service.execute_batch(request))

    # 应该有 2 个成功信号 + 1 个错误 + 1 个摘要
    signals = [r for r in results if r['type'] == 'signal']
    errors = [r for r in results if r['type'] == 'error']
    summary = [r for r in results if r['type'] == 'summary'][0]

    assert len(signals) == 2
    assert len(errors) == 1
    assert summary['data']['success'] == 2
    assert summary['data']['failed'] == 1


def test_execute_pipeline_with_orders(service, mock_strategy_engine, mock_signal_repo):
    """测试完整流程执行 - 创建订单"""
    # Mock 策略引擎
    mock_engine = Mock()
    mock_engine.execute.side_effect = [
        {'symbol': '000001.SH', 'signal_type': 'BUY', 'confidence': 0.85, 'entry_price': 1850.0},
        {'symbol': '000001.SZ', 'signal_type': 'BUY', 'confidence': 0.75, 'entry_price': 12.5}
    ]
    mock_strategy_engine.return_value = mock_engine

    request = StrategyPipelineExecuteRequest(
        symbols=["000001.SH", "000001.SZ"],
        strategy_name="Turtle",
        create_orders=True,
        risk_check=False  # Disable risk check for simplicity
    )

    result = service.execute_pipeline(request)

    assert result['signals_generated'] == 2
    assert result['signals_approved'] == 2
    assert result['signals_rejected'] == 0
    assert result['orders_created'] == 2


def test_execute_pipeline_without_orders(service, mock_strategy_engine, mock_signal_repo):
    """测试完整流程执行 - 不创建订单"""
    mock_engine = Mock()
    mock_engine.execute.return_value = {
        'symbol': '000001.SH',
        'signal_type': 'BUY',
        'confidence': 0.85,
        'entry_price': 1850.0
    }
    mock_strategy_engine.return_value = mock_engine

    request = StrategyPipelineExecuteRequest(
        symbols=["000001.SH"],
        strategy_name="Turtle",
        create_orders=False
    )

    result = service.execute_pipeline(request)

    assert result['signals_generated'] == 1
    assert result['signals_approved'] == 1
    assert result['orders_created'] == 0
