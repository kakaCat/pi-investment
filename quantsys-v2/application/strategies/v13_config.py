from domain.strategies.value_objects import StrategyConfig
from infrastructure.config.constants.trading.strategy import V13StrategyDefaults

# 使用配置类管理默认参数
_DEFAULTS = V13StrategyDefaults()

# 账户本金（元）：与 live_trading/config_simulation.yaml:initial_capital 及
# live_trading/configs/strategies/v13.yaml:initial_capital（均为 100000）一致。
#
# 2026-10-04（REQ-261004154902-a7cd · FR-6）：改前该值硬编码在
# domain/strategies/xgboost_strategy.py:generate_orders（1_000_000），而账户本金是 10 万
# ——0.17 权重 × 10 元 ⇒ 17,000 股，10 倍超买。现在本金只在本配置里声明一次，
# 由 params 注入给算法；算法侧只保留一个显式保守兜底（见 xgboost_strategy）。
REFERENCE_CAPITAL = 100_000.0

V13_CONFIG = StrategyConfig(
    name="xgboost_multi_factor",
    version="V13",
    rebalance_days=_DEFAULTS.REBALANCE_DAYS,
    max_positions=_DEFAULTS.MAX_POSITIONS,
    max_position_pct=_DEFAULTS.MAX_POSITION_PCT,
    stop_loss_pct=_DEFAULTS.STOP_LOSS_PCT,
    trailing_stop_pct=_DEFAULTS.TRAILING_STOP_PCT,
    portfolio_stop_loss_pct=_DEFAULTS.PORTFOLIO_STOP_LOSS_PCT,
    # 真实存在的训练产物（改前指向 live_trading/models/xgboost_multi_factor_model.json
    # 与 config/v13_factors.json，两个文件都不存在 → 加载结果恒为 model=None, factors=[]）
    model_path="live_trading/models/v13_model.json",
    factors_path="live_trading/models/valid_factors.json",
    params={"reference_capital": REFERENCE_CAPITAL},
)
