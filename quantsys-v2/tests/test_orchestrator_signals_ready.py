"""orchestrator MARKET_OPEN 阶段改造测试：推送 signals_ready，不下单"""
from datetime import date
from unittest.mock import patch, MagicMock

from application.services.daily_orchestrator import DailyOrchestrator


def _make_orchestrator():
    orch = DailyOrchestrator.__new__(DailyOrchestrator)
    orch.name = 'test'
    orch.session = MagicMock()
    return orch


def _make_state():
    state = MagicMock()
    state.trade_date = date(2026, 7, 24)
    state.context = {}
    return state


def test_market_open_pushes_signals_ready_without_executing():
    orch = _make_orchestrator()
    state = _make_state()
    fake_signals = [
        {'id': 1, 'symbol': '600519.SH', 'signal_type': '买入', 'strength': 85},
        {'id': 2, 'symbol': '000858.SZ', 'signal_type': '买入', 'strength': 78},
    ]

    with patch('application.services.signal_execution_scheduler.SignalExecutionScheduler') as MockSched, \
         patch('application.services.daily_orchestrator.agent_service') as mock_agent, \
         patch('adapters.outbound.repositories.SimulationORMRepository') as MockRepo:
        MockSched.return_value._collect_signals.return_value = fake_signals

        result = orch._phase_market_open(state)

    # 不再自动下单
    MockSched.return_value.execute_daily_signals.assert_not_called()
    # 开盘前先 T+1 结转（前日持仓开盘即可卖）
    MockRepo.return_value.settle_t1.assert_called_once_with('agent_virtual')
    # 推送 signals_ready
    mock_agent.notify_agent.assert_called_once()
    event, data = mock_agent.notify_agent.call_args[0]
    assert event == 'signals_ready'
    assert data['account'] == 'agent_virtual'
    assert data['signal_count'] == 2
    assert data['signals'] == fake_signals
    assert 'trade_date' in data
    assert result['status'] == 'signals_pushed'
    assert result['signal_count'] == 2


def test_market_open_with_zero_signals_still_notifies():
    """0 信号也推送（agent 需要知道"今日无信号"而不是静默）"""
    orch = _make_orchestrator()
    state = _make_state()

    with patch('application.services.signal_execution_scheduler.SignalExecutionScheduler') as MockSched, \
         patch('application.services.daily_orchestrator.agent_service') as mock_agent, \
         patch('adapters.outbound.repositories.SimulationORMRepository'):
        MockSched.return_value._collect_signals.return_value = []

        result = orch._phase_market_open(state)

    mock_agent.notify_agent.assert_called_once()
    event, data = mock_agent.notify_agent.call_args[0]
    assert event == 'signals_ready'
    assert data['signal_count'] == 0
    assert result['signal_count'] == 0
