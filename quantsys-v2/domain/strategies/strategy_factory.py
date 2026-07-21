"""
策略工厂

负责创建和管理所有策略实例
"""
from typing import Optional
from domain.strategies.base_strategy import BaseStrategy
from domain.strategies.strategy_272 import Strategy272
from domain.strategies.strategy_273 import Strategy273
import logging

logger = logging.getLogger(__name__)


class StrategyFactory:
    """策略工厂"""

    # 策略注册表
    _strategies = {}

    @classmethod
    def register_strategy(cls, strategy: BaseStrategy):
        """
        注册策略

        Args:
            strategy: 策略实例
        """
        cls._strategies[strategy.strategy_id] = strategy
        logger.info(f'注册策略：{strategy.strategy_id} - {strategy.name}')

    @classmethod
    def get_strategy(cls, strategy_id: int) -> Optional[BaseStrategy]:
        """
        获取策略实例

        Args:
            strategy_id: 策略ID

        Returns:
            策略实例，如果不存在返回None
        """
        return cls._strategies.get(strategy_id)

    @classmethod
    def list_strategies(cls) -> list:
        """
        列出所有已注册的策略

        Returns:
            策略列表
        """
        return [
            {
                'id': strategy.strategy_id,
                'name': strategy.name,
                'description': strategy.description
            }
            for strategy in cls._strategies.values()
        ]

    @classmethod
    def initialize(cls):
        """初始化并注册所有策略"""
        # 注册规则策略
        cls.register_strategy(Strategy272())
        cls.register_strategy(Strategy273())

        # TODO: 添加ML策略时在这里注册
        # cls.register_strategy(Strategy274ML())

        logger.info(f'策略工厂初始化完成，共注册 {len(cls._strategies)} 个策略')


# 自动初始化
StrategyFactory.initialize()
