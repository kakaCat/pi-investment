"""数学和转换常量

包含项目中使用的数学常量和单位转换系数。
这些值是标准的数学或金融约定，通常不需要修改。
"""

from dataclasses import dataclass
from .base import ConfigBase


@dataclass(frozen=True)
class MathematicalConstants(ConfigBase):
    """数学和金融常量"""

    # ============ 时间常量 ============

    #: 每年交易日数（A 股市场标准）
    TRADING_DAYS_PER_YEAR: int = 252

    #: 每个交易日的分钟数（9:30-11:30 + 13:00-15:00）
    TRADING_MINUTES_PER_DAY: int = 390

    # ============ 单位转换 ============

    #: 万元转亿元的系数
    WAN_TO_YI: float = 10000.0

    #: 基点（Basis Points）乘数（1% = 100 bp）
    BASIS_POINTS_MULTIPLIER: int = 10000

    #: 股票交易手数（A 股 1 手 = 100 股）
    LOT_SIZE: int = 100

    # ============ Black-Scholes 公式常量 ============

    #: Black-Scholes d1 公式中的系数（数学常量，不应修改）
    BLACK_SCHOLES_D1_COEFFICIENT: float = 0.5

    # ============ 价格冲击模型 ============

    #: 平方根价格冲击模型指数（Almgren-Chriss 模型标准值）
    PRICE_IMPACT_EXPONENT: float = 0.5


# 全局单例实例
MATH_CONSTANTS = MathematicalConstants()
