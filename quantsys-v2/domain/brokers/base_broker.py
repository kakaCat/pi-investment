"""
Base Broker - Abstract base class for all broker implementations

Inspired by FinceptTerminal's IBroker interface, this defines the contract
that all broker adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from .trading_types import (
    BrokerProfile,
    UnifiedOrder,
    OrderPlaceResponse,
    ApiResponse,
    BrokerQuote,
    BrokerCandle,
    BrokerPosition,
    BrokerHolding,
    BrokerFunds,
    BrokerCredentials,
)


class BaseBroker(ABC):
    """
    券商抽象基类

    所有券商实现必须继承此类并实现所有抽象方法。
    可选功能可以返回 ApiResponse.fail("Not supported")

    设计原则：
    1. 必需方法 = 抽象方法，强制实现
    2. 可选方法 = 带默认实现，返回 "Not supported"
    3. 统一返回类型 ApiResponse[T]
    4. 所有跨券商代码使用 UnifiedOrder 等统一类型
    """

    # ========================================================================
    # Identity & Configuration (必需实现)
    # ========================================================================

    @abstractmethod
    def get_id(self) -> str:
        """
        返回券商唯一标识符

        Returns:
            str: 券商 ID，如 "akshare", "eastmoney", "tushare"
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        返回券商显示名称

        Returns:
            str: 显示名称，如 "AkShare", "东方财富"
        """
        pass

    @abstractmethod
    def get_profile(self) -> BrokerProfile:
        """
        返回券商配置元数据

        UI 层根据此配置动态生成表单和选项

        Returns:
            BrokerProfile: 券商配置信息
        """
        pass

    # ========================================================================
    # Authentication (可选实现)
    # ========================================================================

    def authenticate(self, credentials: BrokerCredentials) -> ApiResponse[bool]:
        """
        认证并获取访问令牌

        Args:
            credentials: 券商凭证

        Returns:
            ApiResponse[bool]: 认证结果
        """
        return ApiResponse.fail("Authentication not supported for this broker")

    def refresh_token(self, credentials: BrokerCredentials) -> ApiResponse[str]:
        """
        刷新访问令牌

        Args:
            credentials: 券商凭证

        Returns:
            ApiResponse[str]: 新的访问令牌
        """
        return ApiResponse.fail("Token refresh not supported for this broker")

    # ========================================================================
    # Market Data (必需实现)
    # ========================================================================

    @abstractmethod
    def get_quotes(self, symbols: List[str]) -> ApiResponse[List[BrokerQuote]]:
        """
        获取实时行情

        Args:
            symbols: 股票代码列表，如 ["600000.SH", "000001.SZ"]

        Returns:
            ApiResponse[List[BrokerQuote]]: 行情数据列表
        """
        pass

    @abstractmethod
    def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        frequency: str = "daily"
    ) -> ApiResponse[List[BrokerCandle]]:
        """
        获取历史K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"
            frequency: 频率，"daily"/"weekly"/"monthly"/"1min"/"5min"等

        Returns:
            ApiResponse[List[BrokerCandle]]: K线数据列表
        """
        pass

    # ========================================================================
    # Trading (可选实现 - 仅交易券商需要)
    # ========================================================================

    def place_order(
        self,
        credentials: BrokerCredentials,
        order: UnifiedOrder
    ) -> OrderPlaceResponse:
        """
        下单

        Args:
            credentials: 券商凭证
            order: 统一订单结构

        Returns:
            OrderPlaceResponse: 下单结果
        """
        return OrderPlaceResponse.fail("Trading not supported for this broker")

    def cancel_order(
        self,
        credentials: BrokerCredentials,
        order_id: str
    ) -> ApiResponse[Dict[str, Any]]:
        """
        撤单

        Args:
            credentials: 券商凭证
            order_id: 订单ID

        Returns:
            ApiResponse[Dict]: 撤单结果
        """
        return ApiResponse.fail("Trading not supported for this broker")

    def modify_order(
        self,
        credentials: BrokerCredentials,
        order_id: str,
        modifications: Dict[str, Any]
    ) -> ApiResponse[Dict[str, Any]]:
        """
        改单

        Args:
            credentials: 券商凭证
            order_id: 订单ID
            modifications: 修改内容

        Returns:
            ApiResponse[Dict]: 改单结果
        """
        return ApiResponse.fail("Trading not supported for this broker")

    def get_orders(
        self,
        credentials: BrokerCredentials
    ) -> ApiResponse[List[Dict[str, Any]]]:
        """
        查询订单

        Args:
            credentials: 券商凭证

        Returns:
            ApiResponse[List[Dict]]: 订单列表
        """
        return ApiResponse.fail("Trading not supported for this broker")

    # ========================================================================
    # Portfolio (可选实现 - 仅交易券商需要)
    # ========================================================================

    def get_positions(
        self,
        credentials: BrokerCredentials
    ) -> ApiResponse[List[BrokerPosition]]:
        """
        查询持仓

        Args:
            credentials: 券商凭证

        Returns:
            ApiResponse[List[BrokerPosition]]: 持仓列表
        """
        return ApiResponse.fail("Trading not supported for this broker")

    def get_holdings(
        self,
        credentials: BrokerCredentials
    ) -> ApiResponse[List[BrokerHolding]]:
        """
        查询持股（长期持仓）

        Args:
            credentials: 券商凭证

        Returns:
            ApiResponse[List[BrokerHolding]]: 持股列表
        """
        return ApiResponse.fail("Trading not supported for this broker")

    def get_funds(
        self,
        credentials: BrokerCredentials
    ) -> ApiResponse[BrokerFunds]:
        """
        查询资金

        Args:
            credentials: 券商凭证

        Returns:
            ApiResponse[BrokerFunds]: 资金信息
        """
        return ApiResponse.fail("Trading not supported for this broker")

    # ========================================================================
    # Advanced Features (可选实现)
    # ========================================================================

    def get_margin_info(
        self,
        credentials: BrokerCredentials,
        order: UnifiedOrder
    ) -> ApiResponse[Dict[str, Any]]:
        """
        查询保证金要求

        Args:
            credentials: 券商凭证
            order: 订单信息

        Returns:
            ApiResponse[Dict]: 保证金信息
        """
        return ApiResponse.fail("Margin calculation not supported for this broker")

    def search_symbols(
        self,
        query: str,
        exchange: Optional[str] = None
    ) -> ApiResponse[List[Dict[str, Any]]]:
        """
        搜索股票

        Args:
            query: 搜索关键词（代码或名称）
            exchange: 交易所过滤，可选

        Returns:
            ApiResponse[List[Dict]]: 搜索结果
        """
        return ApiResponse.fail("Symbol search not supported for this broker")

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def is_trading_broker(self) -> bool:
        """
        判断是否为交易券商

        Returns:
            bool: True 表示支持交易，False 表示仅数据源
        """
        profile = self.get_profile()
        return len(profile.credential_fields) > 0

    def supports_feature(self, feature: str) -> bool:
        """
        检查是否支持特定功能

        Args:
            feature: 功能名称，如 "margin", "options", "futures"

        Returns:
            bool: 是否支持
        """
        profile = self.get_profile()
        feature_map = {
            'margin': profile.supports_margin,
            'options': profile.supports_options,
            'intraday': profile.supports_intraday,
        }
        return feature_map.get(feature, False)

    def __repr__(self) -> str:
        """字符串表示"""
        return f"<{self.__class__.__name__} id={self.get_id()} name={self.get_name()}>"
