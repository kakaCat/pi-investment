"""Tests for strategy execution models"""
import pytest
from adapters.outbound.repositories.models.strategy_execution import (
    StrategyExecuteRequest,
    StrategyBatchExecuteRequest,
    StrategyPipelineExecuteRequest
)

def test_strategy_execute_request_validation():
    """测试单股执行请求验证"""
    # 有效请求
    req = StrategyExecuteRequest(
        symbol="000001.SH",
        strategy_name="Turtle",
        persist=True
    )
    assert req.symbol == "000001.SH"
    assert req.strategy_name == "Turtle"
    assert req.persist is True

    # 缺少必需字段
    with pytest.raises(ValueError):
        StrategyExecuteRequest(symbol="000001.SH")

def test_batch_execute_request_validation():
    """测试批量执行请求验证"""
    req = StrategyBatchExecuteRequest(
        symbols=["000001.SH", "000001.SZ"],
        strategy_name="Turtle",
        min_confidence=0.6
    )
    assert len(req.symbols) == 2
    assert req.min_confidence == 0.6

    # 空列表
    with pytest.raises(ValueError):
        StrategyBatchExecuteRequest(symbols=[], strategy_name="Turtle")
