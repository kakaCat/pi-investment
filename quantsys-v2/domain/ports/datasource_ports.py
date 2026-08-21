"""
数据源端口接口定义

定义应用层访问外部数据源的抽象接口，遵循依赖倒置原则。
适配器层实现这些接口，应用层依赖接口而非具体实现。
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from domain.models.market_data import (
    QuoteData,
    KlineData,
    FinancialData,
    DividendData,
    MarketData,
    StockData
)


# ==================== Provider 接口 ====================

class IQuoteProvider(ABC):
    """行情数据提供者接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称（如 'sina', 'tencent', 'eastmoney'）"""
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """获取单只股票的实时行情

        Args:
            symbol: 股票代码（如 '600519.SH'）

        Returns:
            QuoteData 或 None（失败时）
        """
        pass

    @abstractmethod
    def get_batch_quotes(self, symbols: List[str]) -> Dict[str, QuoteData]:
        """批量获取多只股票的实时行情

        Args:
            symbols: 股票代码列表

        Returns:
            字典 {symbol: QuoteData}，失败的股票不在字典中
        """
        pass


class IKlineProvider(ABC):
    """K线数据提供者接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass

    @abstractmethod
    def get_kline(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str = 'daily'
    ) -> List[Dict[str, Any]]:
        """获取K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'
            period: 周期 'daily' | 'weekly' | 'monthly'

        Returns:
            K线数据列表（字典格式）
        """
        pass


class IFinancialProvider(ABC):
    """财务数据提供者接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass

    @abstractmethod
    def get_financial(
        self,
        symbol: str,
        report_type: str = 'latest'
    ) -> Optional[FinancialData]:
        """获取财务数据

        Args:
            symbol: 股票代码
            report_type: 报告类型 'latest' | 'quarterly' | 'annual'

        Returns:
            FinancialData 或 None
        """
        pass


class IDividendProvider(ABC):
    """分红数据提供者接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass

    @abstractmethod
    def get_dividend(self, symbol: str) -> Optional[DividendData]:
        """获取分红数据

        Args:
            symbol: 股票代码

        Returns:
            DividendData 或 None
        """
        pass


class IMarketProvider(ABC):
    """市场数据提供者接口（板块、龙虎榜等）"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass

    @abstractmethod
    def get_market_data(self, data_type: str, **kwargs) -> Optional[MarketData]:
        """获取市场数据

        Args:
            data_type: 数据类型 'sector' | 'lhb' | 'fund_flow' | etc.
            **kwargs: 额外参数

        Returns:
            MarketData 或 None
        """
        pass


class IStockProvider(ABC):
    """股票基础数据提供者接口（公告、新闻等）"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称"""
        pass

    @abstractmethod
    def get_stock_data(
        self,
        symbol: str,
        data_type: str,
        **kwargs
    ) -> Optional[StockData]:
        """获取股票基础数据

        Args:
            symbol: 股票代码
            data_type: 数据类型 'announcement' | 'news' | etc.
            **kwargs: 额外参数

        Returns:
            StockData 或 None
        """
        pass


# ==================== Manager 接口 ====================

class IDataProviderManager(ABC):
    """数据提供者管理器接口

    统一管理多个数据源，支持：
    - 自动降级（主源失败切换备源）
    - 健康监控（provider 成功率统计）
    - 来源追溯（返回数据包含 source 字段）
    """

    @abstractmethod
    def get_quote(self, symbol: str, timeout: Optional[float] = None) -> Optional[QuoteData]:
        """通过最优 provider 获取实时行情

        自动尝试多个 provider，直到成功或全部失败

        Args:
            symbol: 股票代码
            timeout: 超时时间（秒），None 使用默认值

        Returns:
            QuoteData（含 source 字段）或 None
        """
        pass

    @abstractmethod
    def get_batch_quotes(
        self,
        symbols: List[str],
        timeout: Optional[float] = None
    ) -> Dict[str, QuoteData]:
        """批量获取实时行情

        Args:
            symbols: 股票代码列表
            timeout: 超时时间（秒）

        Returns:
            {symbol: QuoteData}
        """
        pass

    @abstractmethod
    def get_kline(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str = 'daily',
        timeout: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """通过最优 provider 获取K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 周期
            timeout: 超时时间（秒）

        Returns:
            K线数据列表
        """
        pass

    @abstractmethod
    def get_financial(
        self,
        symbol: str,
        report_type: str = 'latest',
        timeout: Optional[float] = None
    ) -> Optional[FinancialData]:
        """获取财务数据

        Args:
            symbol: 股票代码
            report_type: 报告类型
            timeout: 超时时间（秒）

        Returns:
            FinancialData 或 None
        """
        pass

    @abstractmethod
    def get_dividend(
        self,
        symbol: str,
        timeout: Optional[float] = None
    ) -> Optional[DividendData]:
        """获取分红数据

        Args:
            symbol: 股票代码
            timeout: 超时时间（秒）

        Returns:
            DividendData 或 None
        """
        pass

    @abstractmethod
    def get_market_data(
        self,
        data_type: str,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Optional[MarketData]:
        """获取市场数据

        Args:
            data_type: 数据类型
            timeout: 超时时间（秒）
            **kwargs: 额外参数

        Returns:
            MarketData 或 None
        """
        pass

    @abstractmethod
    def get_stock_data(
        self,
        symbol: str,
        data_type: str,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Optional[StockData]:
        """获取股票基础数据

        Args:
            symbol: 股票代码
            data_type: 数据类型
            timeout: 超时时间（秒）
            **kwargs: 额外参数

        Returns:
            StockData 或 None
        """
        pass

    @abstractmethod
    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有 provider 的健康状态

        Returns:
            {
                'provider_name': {
                    'success': int,
                    'failure': int,
                    'success_rate': float,
                    'is_healthy': bool
                }
            }
        """
        pass


# ==================== 基础设施接口 ====================

class ICacheService(ABC):
    """缓存服务接口"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值或 None（未命中或过期）
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值（可序列化对象）
            ttl: 过期时间（秒），默认 300 秒
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """删除缓存

        Args:
            key: 缓存键
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空所有缓存"""
        pass


class ICircuitBreaker(ABC):
    """熔断器接口

    保护外部服务调用，当失败率过高时自动熔断，避免雪崩
    """

    @abstractmethod
    def call(self, func, *args, **kwargs) -> Any:
        """执行受保护的调用

        Args:
            func: 要调用的函数
            *args, **kwargs: 函数参数

        Returns:
            函数返回值

        Raises:
            CircuitBreakerOpenError: 熔断器打开，拒绝调用
            原函数的异常: 调用失败时抛出
        """
        pass

    @abstractmethod
    def is_open(self) -> bool:
        """熔断器是否打开（熔断状态）

        Returns:
            True=熔断中，False=正常
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """手动重置熔断器"""
        pass


# ==================== 特定数据源接口 ====================

class ILhbDataSource(ABC):
    """龙虎榜数据源接口"""

    @abstractmethod
    def get_lhb_data(self, date: str) -> List[Dict[str, Any]]:
        """获取龙虎榜数据

        Args:
            date: 日期 'YYYY-MM-DD'

        Returns:
            龙虎榜记录列表
        """
        pass


class IFundFlowDataSource(ABC):
    """资金流向数据源接口"""

    @abstractmethod
    def get_fund_flow(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """获取资金流向数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            资金流向记录列表
        """
        pass


class INorthFlowDataSource(ABC):
    """北向资金/港股通数据源接口"""

    @abstractmethod
    def get_north_holdings(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取北向资金持股数据

        Args:
            symbol: 股票代码

        Returns:
            持股数据或 None
        """
        pass
