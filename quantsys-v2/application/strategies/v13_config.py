from domain.strategies.value_objects import StrategyConfig

V13_CONFIG = StrategyConfig(
    name="xgboost_multi_factor",
    version="V13",
    rebalance_days=5,
    max_positions=8,
    max_position_pct=0.85,
    stop_loss_pct=-0.12,
    trailing_stop_pct=-0.08,
    portfolio_stop_loss_pct=-0.20,
    model_path="live_trading/models/xgboost_multi_factor_model.json",
    factors_path="config/v13_factors.json",
)
