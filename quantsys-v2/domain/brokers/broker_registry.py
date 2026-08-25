"""
Broker Registry - Singleton registry for broker discovery and management

Inspired by FinceptTerminal's BrokerRegistry pattern.
"""

from typing import Dict, List, Optional
import logging

from .base_broker import BaseBroker


logger = logging.getLogger(__name__)


class BrokerRegistry:
    """
    券商注册表（单例模式）

    职责：
    1. 启动时注册所有券商实现
    2. 提供按 ID 查找券商的能力
    3. 列举所有可用券商

    Usage:
        registry = BrokerRegistry.instance()
        broker = registry.get('akshare')
        all_brokers = registry.list_brokers()
    """

    _instance: Optional['BrokerRegistry'] = None
    _brokers: Dict[str, BaseBroker] = {}
    _initialized: bool = False

    def __init__(self):
        """私有构造函数，使用 instance() 获取单例"""
        if BrokerRegistry._initialized:
            raise RuntimeError(
                "BrokerRegistry is a singleton. Use BrokerRegistry.instance() instead."
            )
        self._brokers = {}
        BrokerRegistry._initialized = True

    @classmethod
    def instance(cls) -> 'BrokerRegistry':
        """
        获取单例实例

        Returns:
            BrokerRegistry: 全局唯一的注册表实例

        Note:
            Brokers must be registered by infrastructure layer after creation.
            Use infrastructure.brokers.setup.setup_brokers() to register implementations.
        """
        if cls._instance is None:
            cls._instance = cls()
            logger.info("BrokerRegistry instance created (empty, waiting for infrastructure setup)")
        return cls._instance

    def register(self, broker: BaseBroker):
        """
        注册一个券商实现

        Args:
            broker: 券商实例

        Raises:
            ValueError: 如果券商 ID 已存在
        """
        broker_id = broker.get_id()
        if broker_id in self._brokers:
            raise ValueError(f"Broker '{broker_id}' is already registered")

        self._brokers[broker_id] = broker
        logger.debug(f"Registered broker: {broker_id} ({broker.get_name()})")

    def get(self, broker_id: str) -> Optional[BaseBroker]:
        """
        根据 ID 获取券商实例

        Args:
            broker_id: 券商 ID，如 "akshare"

        Returns:
            Optional[BaseBroker]: 券商实例，不存在则返回 None
        """
        return self._brokers.get(broker_id)

    def has(self, broker_id: str) -> bool:
        """
        检查券商是否已注册

        Args:
            broker_id: 券商 ID

        Returns:
            bool: 是否存在
        """
        return broker_id in self._brokers

    def list_brokers(self) -> List[str]:
        """
        列举所有已注册的券商 ID

        Returns:
            List[str]: 券商 ID 列表
        """
        return list(self._brokers.keys())

    def list_broker_profiles(self) -> List[Dict[str, str]]:
        """
        列举所有券商的基本信息

        Returns:
            List[Dict]: 券商信息列表，每项包含 id, name, region, currency
        """
        profiles = []
        for broker_id, broker in self._brokers.items():
            profile = broker.get_profile()
            profiles.append({
                'id': broker_id,
                'name': broker.get_name(),
                'region': profile.region,
                'currency': profile.currency,
                'is_trading': broker.is_trading_broker(),
            })
        return profiles

    def get_trading_brokers(self) -> List[BaseBroker]:
        """
        获取所有支持交易的券商

        Returns:
            List[BaseBroker]: 交易券商列表
        """
        return [
            broker for broker in self._brokers.values()
            if broker.is_trading_broker()
        ]

    def get_data_brokers(self) -> List[BaseBroker]:
        """
        获取所有数据源券商（不支持交易）

        Returns:
            List[BaseBroker]: 数据源券商列表
        """
        return [
            broker for broker in self._brokers.values()
            if not broker.is_trading_broker()
        ]

    def clear(self):
        """
        清空注册表（仅用于测试）
        """
        self._brokers.clear()
        logger.debug("Broker registry cleared")

    @classmethod
    def reset(cls):
        """
        重置单例（仅用于测试）
        """
        cls._instance = None
        cls._initialized = False
        logger.debug("Broker registry reset")

    def __repr__(self) -> str:
        """字符串表示"""
        return f"<BrokerRegistry brokers={len(self._brokers)}>"
