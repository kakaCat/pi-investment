"""Enhanced strategy base — StrategyBase + all mixins."""
from domain.backtest.engine.strategy_base import StrategyBase
from domain.backtest.engine.mixins.indicator_mixin import IndicatorMixin
from domain.backtest.engine.mixins.factor_mixin import FactorMixin


class EnhancedStrategyBase(StrategyBase, IndicatorMixin, FactorMixin):
    """Enhanced strategy base combining StrategyBase with mixins.

    New strategies should inherit from this class to get automatic access to:
    - Technical indicators via ``self.calculate_indicator()``
    - FactorRegistry via ``self.calculate_factors()``
    - (MLMixin can be added separately for ML strategies)

    Existing strategies inheriting from ``StrategyBase`` continue to work
    unchanged.
    """

    def __init__(self, name: str = None):
        StrategyBase.__init__(self, name)
        FactorMixin.__init__(self)
        IndicatorMixin.__init__(self)
