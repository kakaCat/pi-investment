"""orchestrator 各阶段账户统一为 agent_virtual 测试"""
from datetime import date
from unittest.mock import patch, MagicMock

from application.services.daily_orchestrator import DailyOrchestrator


def _make_orchestrator():
    orch = DailyOrchestrator.__new__(DailyOrchestrator)
    orch.name = 'test'
    orch.session = MagicMock()
    # 2026-09-11（w-f4aa1f6a）：__init__ 被绕过，须显式注入 _simulation_repo。
    # 各阶段（market_close/review）现走 self._simulation_repo if not None else
    # EnhancedServiceFactory.resolve(...)，只 patch 类路径已不再生效。
    orch._simulation_repo = MagicMock()
    return orch


def _make_state():
    state = MagicMock()
    state.trade_date = date(2026, 7, 24)
    state.context = {}
    return state


def test_market_close_settles_agent_virtual():
    orch = _make_orchestrator()
    state = _make_state()

    with patch('adapters.outbound.repositories.SimulationORMRepository') as MockRepo, \
         patch('application.trading.paper_trading_engine.PaperTradingEngine') as MockEngine:
        MockEngine.return_value.get_current_positions.return_value = []
        orch._phase_market_close(state)

    # 2026-09-05 起改为全 active 账户结算（settle_t1_all）；原硬编码
    # settle_t1('agent_virtual') 会让 agent_brain 等账户 T+1 永不结转
    orch._simulation_repo.settle_t1_all.assert_called_once_with()
    MockEngine.assert_called_once_with(account_name='agent_virtual')


def test_post_market_snapshot_uses_agent_virtual():
    orch = _make_orchestrator()
    state = _make_state()

    with patch('application.trading.paper_trading_engine.PaperTradingEngine') as MockEngine, \
         patch('application.services.scheduler_tasks.handle_factor_compute', return_value={'status': 'ok'}):
        MockEngine.return_value.take_daily_snapshot.return_value = {}
        MockEngine.return_value.get_performance_report.return_value = {}
        orch._phase_post_market(state)

    MockEngine.assert_called_once_with(account_name='agent_virtual')


def test_review_queries_agent_virtual_trades():
    orch = _make_orchestrator()
    state = _make_state()

    with patch('adapters.outbound.repositories.simulation_repository.SimulationORMRepository') as MockRepo, \
         patch('application.services.daily_orchestrator.agent_service') as mock_agent:
        orch._simulation_repo.get_trades_by_account.return_value = []
        orch._phase_review(state)

    orch._simulation_repo.get_trades_by_account.assert_called_once()
    assert orch._simulation_repo.get_trades_by_account.call_args[0][0] == 'agent_virtual'
    mock_agent.notify_agent.assert_called_once()
