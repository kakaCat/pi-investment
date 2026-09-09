from domain.strategies.value_objects import StrategyConfig
from infrastructure.config.constants.trading.strategy import V13StrategyDefaults

# 使用配置类管理默认参数
_DEFAULTS = V13StrategyDefaults()

V13_CONFIG = StrategyConfig(
    name="xgboost_multi_factor",
    version="V13",
    rebalance_days=_DEFAULTS.REBALANCE_DAYS,
    max_positions=_DEFAULTS.MAX_POSITIONS,
    max_position_pct=_DEFAULTS.MAX_POSITION_PCT,
    stop_loss_pct=_DEFAULTS.STOP_LOSS_PCT,
    trailing_stop_pct=_DEFAULTS.TRAILING_STOP_PCT,
    portfolio_stop_loss_pct=_DEFAULTS.PORTFOLIO_STOP_LOSS_PCT,
    model_path="live_trading/models/xgboost_multi_factor_model.json",
    factors_path="config/v13_factors.json",
)
