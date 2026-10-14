from domain.strategies.value_objects import StrategyConfig
from infrastructure.config.constants.trading.strategy import V14StrategyDefaults

# 使用配置类管理默认参数
_DEFAULTS = V14StrategyDefaults()

# 账户本金（元）：与 live_trading/config_simulation.yaml:initial_capital 一致。
# 2026-10-04（REQ-261004154902-a7cd · FR-6）：改前该值硬编码在
# domain/strategies/xgboost_strategy.py:generate_orders（1_000_000），比真实本金大 10 倍
# → 下单量 10 倍超买。现在只在配置里声明一次，由 params 注入给算法。
REFERENCE_CAPITAL = 100_000.0

V14_CONFIG = StrategyConfig(
    name="xgboost_optimized",
    version="V14",
    rebalance_days=_DEFAULTS.REBALANCE_DAYS,
    max_positions=_DEFAULTS.MAX_POSITIONS,
    max_position_pct=_DEFAULTS.MAX_POSITION_PCT,
    stop_loss_pct=_DEFAULTS.STOP_LOSS_PCT,
    trailing_stop_pct=_DEFAULTS.TRAILING_STOP_PCT,
    portfolio_stop_loss_pct=_DEFAULTS.PORTFOLIO_STOP_LOSS_PCT,
    # 真实存在的训练产物（改前指向 config/v14_factors.json —— 磁盘上不存在）
    model_path="live_trading/models/v14_p0_model.json",
    factors_path="live_trading/models/v14_p0_valid_factors.json",
    params={"reference_capital": REFERENCE_CAPITAL},
)
