"""
策略注册表

负责管理所有可用的交易策略
"""
import structlog
logger = structlog.get_logger(__name__)
from typing import Dict, Optional, List
from .base_strategy import BaseStrategy


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
        logger.info(f'✓ Registered strategy: {strategy_id} ({strategy.config.name} {strategy.config.version})')
    
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
            logger.info(f'✓ Unregistered strategy: {strategy_id}')
    
    def clear(self):
        """清空所有注册的策略（仅用于测试）"""
        self._strategies.clear()


# 全局单例
registry = StrategyRegistry()


def get_registry() -> StrategyRegistry:
    """获取全局策略注册表"""
    return registry
