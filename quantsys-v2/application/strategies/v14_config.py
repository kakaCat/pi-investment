# 2026-10-21（w-5d46d252 重应用）：必须从 qs_strategy 导入，避免 shim 双类身份
from qs_strategy.domain.strategies.value_objects import StrategyConfig
from qs_kernel.infrastructure.config.constants.trading.strategy import V14StrategyDefaults

# 使用配置类管理默认参数
_DEFAULTS = V14StrategyDefaults()

V14_CONFIG = StrategyConfig(
    name="xgboost_optimized",
    version="V14",
    rebalance_days=_DEFAULTS.REBALANCE_DAYS,
    max_positions=_DEFAULTS.MAX_POSITIONS,
    max_position_pct=_DEFAULTS.MAX_POSITION_PCT,
    stop_loss_pct=_DEFAULTS.STOP_LOSS_PCT,
    trailing_stop_pct=_DEFAULTS.TRAILING_STOP_PCT,
    portfolio_stop_loss_pct=_DEFAULTS.PORTFOLIO_STOP_LOSS_PCT,
    model_path="live_trading/models/v14_p0_model.json",
    factors_path="config/v14_factors.json",
)
