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


def test_load_model_uses_instance_paths(tmp_path):
    """load_model 必须读 self.model_path/self.factors_path（回归：此前硬编码 v13 模型）"""
    import json
    import numpy as np
    import xgboost as xgb
    from live_trading.simulation_trader import SimulationTrader

    # 构造一个可加载的临时模型与因子文件（save_model 要求先 fit）
    model_file = tmp_path / 'test_model.json'
    factors_file = tmp_path / 'test_factors.json'
    m = xgb.XGBRegressor(n_jobs=1, n_estimators=2)
    m.fit(np.array([[0.0], [1.0]]), np.array([0.0, 1.0]))
    m.save_model(str(model_file))
    factors_file.write_text(json.dumps(['__test_factor_a__', '__test_factor_b__']))

    trader = object.__new__(SimulationTrader)
    trader.model = None
    trader.valid_factors = None
    trader.model_path = str(model_file)
    trader.factors_path = str(factors_file)
    trader.load_model()

    assert trader.valid_factors == ['__test_factor_a__', '__test_factor_b__']
    assert trader.model is not None


def test_create_trader_uses_strategy_config():
    """_create_trader 必须把账户/因子计算器注入构造函数，且风控/调仓参数真正生效"""
    from types import SimpleNamespace
    from application.services.strategy_service import StrategyService

    service = StrategyService.__new__(StrategyService)
    service._configs_cache = {}
    from pathlib import Path
    service.config_dir = Path('live_trading/configs/strategies')

    mock_trader = MagicMock()
    mock_trader.config = {'strategy': {'rebalance_days': 5}}
    mock_trader.risk_controller = SimpleNamespace(single_stop_loss=-0.10)

    with patch('application.services.strategy_service.SimulationTrader',
               return_value=mock_trader) as MockTrader:
        config = service.get_config('v14')
        trader = service._create_trader(config)

    # 账户与因子计算器通过构造函数注入（不是事后赋值）
    _, kwargs = MockTrader.call_args
    assert kwargs.get('account_name') == 'v14_simulation'
    assert kwargs.get('factor_calculator') == 'v14'

    # 调仓周期与止损阈值写入 trader 真正读取的位置
    assert trader.config['strategy']['rebalance_days'] == 7
    assert trader.risk_controller.single_stop_loss == -0.12

    # 模型路径按策略配置覆盖
    assert trader.model_path == 'live_trading/models/v14_p0_model.json'
    assert trader.factors_path == 'live_trading/models/v14_p0_valid_factors.json'
    trader.load_model.assert_called_once()


def test_manual_rebalance_passes_current_date():
    """manual_rebalance 必须传 current_date（回归：此前调用必 TypeError）"""
    from application.services.strategy_service import StrategyService

    service = StrategyService.__new__(StrategyService)
    service._configs_cache = {}
    from pathlib import Path
    service.config_dir = Path('live_trading/configs/strategies')

    mock_trader = MagicMock()
    mock_trader.account_name = 'v13_simulation'
    mock_trader.rebalance.return_value = {'success': True}

    with patch.object(service, '_create_trader', return_value=mock_trader), \
         patch.object(service, 'get_config', return_value={'strategy': {'account_name': 'v13_simulation'}}):
        result = service.manual_rebalance('v13')

    args, kwargs = mock_trader.rebalance.call_args
    current_date = kwargs.get('current_date') or (args[0] if args else None)
    assert current_date is not None  # 形如 '2026-07-28'
    assert result['status'] == 'success'
