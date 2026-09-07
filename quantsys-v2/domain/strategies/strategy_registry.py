"""
策略注册表

负责管理所有可用的交易策略
"""
from typing import Dict, Optional, List

from .base_strategy import BaseStrategy
from .value_objects import StrategyConfig
from .xgboost_strategy import XGBoostStrategy


class StrategyRegistry:
    """策略注册表（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._strategies = {}
        return cls._instance

    def register(self, strategy_id: str, strategy: BaseStrategy):
        """
        注册策略

        Args:
            strategy_id: 策略唯一标识（如 'v13', 'v14'）
            strategy: 策略实例
        """
        if strategy_id in self._strategies:
            raise ValueError(f"Strategy '{strategy_id}' already registered")
        
        self._strategies[strategy_id] = strategy
        print(f"✓ Registered strategy: {strategy_id} ({strategy.config.name} {strategy.config.version})")
    
    def get(self, strategy_id: str) -> Optional[BaseStrategy]:
        """
        获取策略实例
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            BaseStrategy: 策略实例，不存在则返回None
        """
        return self._strategies.get(strategy_id)
    
    def list_all(self) -> List[Dict]:
        """
        列出所有已注册策略
        
        Returns:
            List[Dict]: 策略元数据列表
        """
        result = []
        for strategy_id, strategy in self._strategies.items():
            metadata = strategy.get_metadata()
            metadata['id'] = strategy_id
            metadata['is_initialized'] = strategy.is_initialized
            result.append(metadata)
        return result
    
    def unregister(self, strategy_id: str):
        """
        注销策略
        
        Args:
            strategy_id: 策略ID
        """
        if strategy_id in self._strategies:
            del self._strategies[strategy_id]
            print(f"✓ Unregistered strategy: {strategy_id}")
    
    def clear(self):
        """清空所有注册的策略（仅用于测试）"""
        self._strategies.clear()


# 全局单例
registry = StrategyRegistry()


def get_registry() -> StrategyRegistry:
    """获取全局策略注册表"""
    return registry


class StrategyFactory:
    """Build :class:`XGBoostStrategy` instances for the supported versions.

    This factory replaces the legacy V13/V14 strategy classes (now archived)
    with the new pure-domain XGBoost algorithm, while preserving the same
    version identifiers for callers.
    """

    _configs: Dict[str, StrategyConfig] = {
        "v13": StrategyConfig(
            name="xgboost_multi_factor",
            version="V13",
            description="XGBoost multi-factor stock selection (legacy V13 config)",
            rebalance_days=5,
            max_positions=8,
            max_position_pct=0.85,
            stop_loss_pct=0.12,
            trailing_stop_pct=0.08,
            portfolio_stop_loss_pct=0.20,
            model_path="live_trading/models/v13_model.json",
            factors_path="live_trading/models/valid_factors.json",
            params={"top_n": 8, "min_score": 0.0},
        ),
        "v14": StrategyConfig(
            name="xgboost_optimized",
            version="V14",
            description="XGBoost optimized stock selection (legacy V14 config)",
            rebalance_days=30,
            max_positions=15,
            max_position_pct=0.95,
            stop_loss_pct=0.15,
            trailing_stop_pct=0.10,
            portfolio_stop_loss_pct=0.25,
            model_path="live_trading/models/v14_p0_model.json",
            factors_path="live_trading/models/v14_p0_valid_factors.json",
            params={"top_n": 15, "min_score": 0.0},
        ),
    }

    @classmethod
    def create(cls, version: str) -> XGBoostStrategy:
        """Create an :class:`XGBoostStrategy` for ``version``.

        Args:
            version: Strategy version identifier (``"v13"`` or ``"v14"``).

        Returns:
            A configured :class:`XGBoostStrategy` instance.

        Raises:
            ValueError: If ``version`` is not supported.
        """
        key = version.lower()
        config = cls._configs.get(key)
        if config is None:
            raise ValueError(
                f"Unknown strategy version: {version!r}. "
                f"Supported versions: {', '.join(sorted(cls._configs))}"
            )
        return XGBoostStrategy(config)

    @classmethod
    def supported_versions(cls) -> List[str]:
        """Return all supported version identifiers."""
        return list(cls._configs.keys())


def _register_builtin_strategies():
    """Register the built-in XGBoost strategies on module import."""
    for version in StrategyFactory.supported_versions():
        if registry.get(version) is None:
            registry.register(version, StrategyFactory.create(version))


_register_builtin_strategies()
