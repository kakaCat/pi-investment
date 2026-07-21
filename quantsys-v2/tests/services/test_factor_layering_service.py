"""
测试因子分层回测服务
"""

import pytest
from application.services.factor_layering_service import FactorLayeringService


class TestFactorLayeringService:
    """因子分层回测服务测试"""

    def test_service_initialization(self):
        """测试服务初始化"""
        service = FactorLayeringService()
        assert service is not None
        assert service.kline_repo is not None
        assert service.stock_pool_service is not None

    def test_run_layering_backtest_structure(self):
        """测试分层回测返回结构（不实际执行回测）"""
        service = FactorLayeringService()

        # 测试参数验证
        # 注意：这里只测试基本结构，实际回测需要真实数据

        # 验证服务有必要的方法
        assert hasattr(service, 'run_layering_backtest')
        assert hasattr(service, 'run_batch_layering_backtest')
        assert hasattr(service, '_prepare_factor_data')
        assert hasattr(service, '_prepare_return_data')
        assert hasattr(service, '_prepare_chart_data')

    def test_batch_layering_backtest_structure(self):
        """测试批量回测返回结构"""
        service = FactorLayeringService()

        # 验证批量回测方法存在
        assert callable(service.run_batch_layering_backtest)

    # 注意：完整的端到端测试需要：
    # 1. 真实的股票数据
    # 2. 足够的历史数据（至少1年）
    # 3. 可能需要较长的执行时间
    #
    # 这些测试更适合在集成测试环境中运行
