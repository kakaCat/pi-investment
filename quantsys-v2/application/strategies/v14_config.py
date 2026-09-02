from domain.strategies.value_objects import StrategyConfig

V14_CONFIG = StrategyConfig(
    name="xgboost_optimized",
    version="V14",
    rebalance_days=30,
    max_positions=15,
    max_position_pct=0.95,
    stop_loss_pct=-0.15,
    trailing_stop_pct=-0.10,
    portfolio_stop_loss_pct=-0.25,
    model_path="live_trading/models/v14_p0_model.json",
    factors_path="config/v14_factors.json",
)
