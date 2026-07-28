"""统一策略每日检查架构测试（StrategyService + SimulationTrader 参数化）"""
from unittest.mock import patch, MagicMock

import pytest


def _make_trader(**kwargs):
    """在 mock 重依赖的前提下构造 SimulationTrader"""
    with patch('live_trading.simulation_trader.DataService'), \
         patch('live_trading.simulation_trader.get_engine', return_value=MagicMock()), \
         patch('live_trading.simulation_trader.SimulationORMRepository') as MockRepo, \
         patch('live_trading.simulation_trader.create_notifier_from_config', return_value=None):
        MockRepo.return_value.get_account.return_value = None
        from live_trading.simulation_trader import SimulationTrader
        trader = SimulationTrader(**kwargs)
    return trader, MockRepo


def test_account_name_injected_before_load():
    """account_name 必须在账户加载前生效（回归：此前硬编码 default 导致止损跳过）"""
    trader, MockRepo = _make_trader(account_name='v14_simulation')
    assert trader.account_name == 'v14_simulation'
    MockRepo.return_value.get_account.assert_called_once_with('v14_simulation')


def test_account_name_default_compatible():
    """不传 account_name 时保持 default（向后兼容）"""
    trader, MockRepo = _make_trader()
    assert trader.account_name == 'default'
    MockRepo.return_value.get_account.assert_called_once_with('default')


def test_factor_calculator_v14():
    """factor_calculator='v14' 时使用 V14FactorCalculator"""
    from live_trading.v14_factor_calculator import V14FactorCalculator
    trader, _ = _make_trader(factor_calculator='v14')
    assert isinstance(trader.factor_calc, V14FactorCalculator)


def test_factor_calculator_default_v13():
    """默认使用 V13FactorCalculator（保持现状）"""
    from live_trading.factor_calculator import V13FactorCalculator
    trader, _ = _make_trader()
    assert isinstance(trader.factor_calc, V13FactorCalculator)


def test_factor_calculator_unknown_raises():
    """未知的因子计算器键名应报错"""
    with pytest.raises(ValueError, match='factor_calculator'):
        _make_trader(factor_calculator='v99')
