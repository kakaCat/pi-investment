"""
测试信号执行调度器

验证完整的信号到订单流程编排
"""

import pytest
from datetime import date, datetime
from unittest.mock import Mock, patch, MagicMock

from application.services.signal_execution_scheduler import SignalExecutionScheduler


class TestSignalExecutionScheduler:
    """测试信号执行调度器"""

    @pytest.fixture
    def scheduler(self, mock_paper_engine):
        """创建调度器实例（注入 mock 模拟引擎，避免真实落库）"""
        s = SignalExecutionScheduler()
        s._paper_engine = mock_paper_engine
        return s

    @pytest.fixture
    def mock_strategy_service(self):
        """Mock策略服务"""
        with patch('application.services.signal_execution_scheduler.StrategyCodeService') as mock:
            yield mock.return_value

    @pytest.fixture
    def mock_risk_service(self):
        """Mock风控服务"""
        with patch('application.services.signal_execution_scheduler.RiskCheckService') as mock:
            yield mock.return_value

    @pytest.fixture
    def mock_signal_repo(self):
        """Mock信号仓库"""
        mock = MagicMock()
        mock.get_signals_by_date.return_value = []
        yield mock

    @pytest.fixture
    def mock_log_repo(self):
        """Mock日志仓库"""
        mock = MagicMock()
        mock.create_execution_log.return_value = 1
        yield mock

    @pytest.fixture
    def mock_strategy_repo(self):
        """Mock策略仓库"""
        mock = MagicMock()
        mock.get_all.return_value = []
        yield mock

    @pytest.fixture
    def mock_kline_repo(self):
        """Mock K线仓库"""
        mock = MagicMock()
        mock.get_latest_daily_kline.return_value = {'close': 1680.0}
        yield mock

    @pytest.fixture
    def mock_stock_repo(self):
        """Mock股票仓库"""
        mock = MagicMock()
        mock.get_by_symbol.return_value = {'name': '浦发银行'}
        mock.get_all.return_value = [{'symbol': '000001.SH', 'name': '浦发银行'}]
        yield mock

    @pytest.fixture
    def mock_portfolio_repo(self):
        """Mock持仓仓库"""
        mock = MagicMock()
        yield mock

    @pytest.fixture
    def mock_paper_engine(self):
        """Mock 模拟交易引擎

        2026-09-14（REQ-24e15d B4-c2）：legacy create_order 已随 quant.orders
        归档一并删除；orders_created 现由模拟引擎的实际成交结果决定。
        """
        mock = MagicMock()
        result = MagicMock()
        result.success = True
        result.signal.signal_id = '1'
        mock.execute_signals.return_value = [result]
        yield mock

    def test_execute_daily_signals_success(
        self,
        scheduler,
        mock_strategy_repo,
        mock_strategy_service,
        mock_signal_repo,
        mock_risk_service,
        mock_log_repo,
        mock_kline_repo,
        mock_stock_repo,
        mock_portfolio_repo,
        mock_paper_engine
    ):
        """测试完整的每日信号执行流程"""
        # 准备测试数据
        execution_date = date.today().strftime('%Y-%m-%d')

        # Mock策略列表
        mock_strategy_repo.get_all.return_value = [
            {
                'id': 1,
                'strategy_name': '双均线策略',
                'is_active': True
            }
        ]

        # Mock策略生成信号
        mock_strategy_service.generate_signal.return_value = {
            'symbol': '000001.SH',
            'signal_type': 'buy',
            'price': 1680.0,
            'confidence': 0.85
        }

        # Mock信号创建
        mock_signal_repo.create_signal.return_value = 1

        # Mock待处理信号
        mock_signal_repo.get_signals_by_date.return_value = [
            {
                'id': 1,
                'symbol': '000001.SH',
                'action': 'BUY',
                'status': 'pending',
                'price': 1680.0,
                'confidence': 0.85
            }
        ]

        # Mock风控检查通过
        mock_risk_service.check_signal.return_value = {
            'passed': True,
            'quantity': 100,
            'warnings': []
        }

        # Mock K线数据
        mock_kline_repo.get_latest_daily_kline.return_value = {
            'close': 1680.0
        }

        # Mock股票信息
        mock_stock_repo.get_by_symbol.return_value = {
            'name': '浦发银行'
        }

        # Mock订单创建
        
        # Mock日志创建
        mock_log_repo.create_execution_log.return_value = 1

        # 替换调度器的依赖
        scheduler.strategy_repo = mock_strategy_repo
        scheduler.strategy_service = mock_strategy_service
        scheduler.signal_repo = mock_signal_repo
        scheduler.risk_service = mock_risk_service
        scheduler.log_repo = mock_log_repo
        scheduler.kline_repo = mock_kline_repo
        scheduler.stock_repo = mock_stock_repo
        scheduler.portfolio_repo = mock_portfolio_repo

        # 执行测试
        result = scheduler.execute_daily_signals()

        # 验证结果
        assert result['success'] is True
        assert result['execution_date'] == execution_date
        assert result['strategies_run'] == 1
        assert result['signals_generated'] >= 1
        assert result['signals_approved'] == 1
        assert result['signals_rejected'] == 0
        assert result['orders_created'] == 1
        assert 'log_id' in result

        # 验证调用
        mock_strategy_repo.get_all.assert_called_once_with(active_only=True)
        mock_strategy_service.generate_signal.assert_called()
        mock_signal_repo.create_signal.assert_called()
        mock_signal_repo.get_signals_by_date.assert_called_once_with(execution_date)
        mock_risk_service.check_signal.assert_called_once()
        mock_paper_engine.execute_signals.assert_called_once()
        mock_log_repo.create_execution_log.assert_called_once()
        mock_log_repo.update_execution_log.assert_called()

    def test_execute_daily_signals_with_rejection(
        self,
        scheduler,
        mock_strategy_repo,
        mock_strategy_service,
        mock_signal_repo,
        mock_risk_service,
        mock_log_repo,
        mock_stock_repo,
        mock_portfolio_repo,
        mock_paper_engine
    ):
        """测试信号被风控拒绝的情况"""
        execution_date = date.today().strftime('%Y-%m-%d')

        # Mock策略列表
        mock_strategy_repo.get_all.return_value = [
            {'id': 1, 'strategy_name': '测试策略', 'is_active': True}
        ]

        # Mock策略生成信号
        mock_strategy_service.generate_signal.return_value = {
            'symbol': '000001.SH',
            'signal_type': 'buy',
            'price': 1680.0,
            'confidence': 0.85
        }

        # Mock信号创建
        mock_signal_repo.create_signal.return_value = 1

        # Mock待处理信号
        mock_signal_repo.get_signals_by_date.return_value = [
            {
                'id': 1,
                'symbol': '000001.SH',
                'action': 'BUY',
                'status': 'pending',
                'price': 1680.0
            }
        ]

        # Mock风控检查拒绝
        mock_risk_service.check_signal.return_value = {
            'passed': False,
            'reason': '资金不足',
            'quantity': None
        }

        # Mock股票信息
        mock_stock_repo.get_by_symbol.return_value = {
            'name': '浦发银行'
        }

        # Mock日志创建
        mock_log_repo.create_execution_log.return_value = 1

        # 替换调度器的依赖
        scheduler.strategy_repo = mock_strategy_repo
        scheduler.strategy_service = mock_strategy_service
        scheduler.signal_repo = mock_signal_repo
        scheduler.risk_service = mock_risk_service
        scheduler.log_repo = mock_log_repo
        scheduler.stock_repo = mock_stock_repo
        scheduler.portfolio_repo = mock_portfolio_repo

        # 执行测试
        result = scheduler.execute_daily_signals()

        # 验证结果
        assert result['success'] is True
        assert result['signals_approved'] == 0
        assert result['signals_rejected'] == 1
        assert result['orders_created'] == 0

        # 验证订单创建未被调用
        mock_paper_engine.execute_signals.assert_not_called()

        # 验证信号状态更新为rejected
        update_calls = mock_signal_repo.update_signal.call_args_list
        assert any('rejected' in str(call) for call in update_calls)

    def test_execute_daily_signals_no_strategies(
        self,
        scheduler,
        mock_strategy_repo,
        mock_signal_repo,
        mock_log_repo
    ):
        """测试没有启用策略的情况"""
        execution_date = date.today().strftime('%Y-%m-%d')

        # Mock空策略列表
        mock_strategy_repo.get_all.return_value = []

        # Mock空信号列表
        mock_signal_repo.get_signals_by_date.return_value = []

        # Mock日志创建
        mock_log_repo.create_execution_log.return_value = 1

        # 替换调度器的依赖
        scheduler.strategy_repo = mock_strategy_repo
        scheduler.signal_repo = mock_signal_repo
        scheduler.log_repo = mock_log_repo

        # 执行测试
        result = scheduler.execute_daily_signals()

        # 验证结果
        assert result['success'] is True
        assert result['strategies_run'] == 0
        assert result['signals_generated'] == 0
        assert result['signals_approved'] == 0
        assert result['orders_created'] == 0

    def test_execute_daily_signals_strategy_error(
        self,
        scheduler,
        mock_strategy_repo,
        mock_strategy_service,
        mock_signal_repo,
        mock_log_repo,
        mock_stock_repo,
        mock_portfolio_repo
    ):
        """测试策略执行出错的情况"""
        execution_date = date.today().strftime('%Y-%m-%d')

        # Mock策略列表
        mock_strategy_repo.get_all.return_value = [
            {'id': 1, 'strategy_name': '错误策略', 'is_active': True}
        ]

        # Mock策略生成信号抛出异常
        mock_strategy_service.generate_signal.side_effect = Exception('策略执行失败')

        # Mock股票信息
        mock_stock_repo.get_by_symbol.return_value = {
            'name': '浦发银行'
        }

        # Mock空信号列表
        mock_signal_repo.get_signals_by_date.return_value = []

        # Mock日志创建
        mock_log_repo.create_execution_log.return_value = 1

        # 替换调度器的依赖
        scheduler.strategy_repo = mock_strategy_repo
        scheduler.strategy_service = mock_strategy_service
        scheduler.signal_repo = mock_signal_repo
        scheduler.log_repo = mock_log_repo
        scheduler.stock_repo = mock_stock_repo
        scheduler.portfolio_repo = mock_portfolio_repo

        # 执行测试
        result = scheduler.execute_daily_signals()

        # 验证结果 - 策略错误不应导致整个流程失败
        assert result['success'] is True
        assert result['strategies_run'] == 1  # 策略被尝试运行

    def test_get_stock_pool(self, scheduler):
        """测试获取股票池"""
        stock_pool = scheduler._get_stock_pool()

        assert isinstance(stock_pool, list)
        assert len(stock_pool) > 0
        assert all(isinstance(symbol, str) for symbol in stock_pool)

    def test_summarize_rejections(self, scheduler):
        """测试拒绝原因汇总"""
        rejected_signals = [
            {'reject_reason': '资金不足'},
            {'reject_reason': '资金不足'},
            {'reject_reason': '持仓集中度超限'},
            {'reject_reason': '资金不足'},
        ]

        summary = scheduler._summarize_rejections(rejected_signals)

        assert summary['资金不足'] == 3
        assert summary['持仓集中度超限'] == 1
        assert len(summary) == 2
