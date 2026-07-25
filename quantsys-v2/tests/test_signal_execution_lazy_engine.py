"""SignalExecutionScheduler 懒加载 PaperTradingEngine 测试"""
from unittest.mock import patch
from application.services.signal_execution_scheduler import SignalExecutionScheduler


def test_engine_not_created_on_init():
    """构造时不应创建 PaperTradingEngine（避免无关路径绑定 rotation_main）"""
    with patch('application.services.signal_execution_scheduler.DataService'), \
         patch('application.services.signal_execution_scheduler.StrategyCodeService'), \
         patch('application.services.signal_execution_scheduler.RiskCheckService'), \
         patch('application.services.signal_execution_scheduler.SignalORMRepository'), \
         patch('application.services.signal_execution_scheduler.SignalExecutionLogORMRepository'), \
         patch('application.services.signal_execution_scheduler.StrategyORMRepository'), \
         patch('application.services.signal_execution_scheduler.PaperTradingEngine') as MockEngine:
        scheduler = SignalExecutionScheduler()
        MockEngine.assert_not_called()
        assert scheduler._paper_engine is None


def test_engine_created_lazily_on_access():
    """首次访问 paper_engine 属性时才创建，且复用同一实例"""
    with patch('application.services.signal_execution_scheduler.DataService'), \
         patch('application.services.signal_execution_scheduler.StrategyCodeService'), \
         patch('application.services.signal_execution_scheduler.RiskCheckService'), \
         patch('application.services.signal_execution_scheduler.SignalORMRepository'), \
         patch('application.services.signal_execution_scheduler.SignalExecutionLogORMRepository'), \
         patch('application.services.signal_execution_scheduler.StrategyORMRepository'), \
         patch('application.services.signal_execution_scheduler.PaperTradingEngine') as MockEngine:
        scheduler = SignalExecutionScheduler()
        engine1 = scheduler.paper_engine
        engine2 = scheduler.paper_engine
        MockEngine.assert_called_once_with(
            account_name='rotation_main', initial_capital=1_000_000)
        assert engine1 is engine2
