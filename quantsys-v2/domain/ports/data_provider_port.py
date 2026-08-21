"""
数据提供者端口接口

定义数据源管理的抽象接口，用于：
- 多数据源统一访问
- 数据源降级和容错
- 数据质量监控

依赖倒置：应用层依赖此接口，适配器层实现此接口
"""
from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict
import pandas as pd
from datetime import datetime


class IDataProvider(ABC):
    """单个数据提供者接口"""

    @abstractmethod
    def get_stock_kline(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        freq: str = 'daily'
    ) -> pd.DataFrame:
        """获取股票K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            freq: 频率 ('daily', 'weekly', 'monthly')

        Returns:
            K线数据DataFrame

        Raises:
            DataFetchError: 数据获取失败
        """
        pass

    @abstractmethod
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """获取股票基本信息

        Args:
            symbol: 股票代码

        Returns:
            股票信息字典

        Raises:
            DataFetchError: 数据获取失败
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用

        Returns:
            数据源是否可用
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """获取数据提供者名称

        Returns:
            提供者名称
        """
        pass


class IDataProviderManager(ABC):
    """数据提供者管理器接口

    负责管理多个数据源，提供：
    - 数据源选择和切换
    - 降级策略
    - 数据质量监控
    """

    @abstractmethod
    def get_provider(self, provider_name: str) -> IDataProvider:
        """获取指定的数据提供者

        Args:
            provider_name: 提供者名称 ('akshare', 'tushare', 'eastmoney'等)

        Returns:
            数据提供者实例

        Raises:
            ProviderNotFoundError: 提供者不存在
        """
        pass

    @abstractmethod
    def get_available_providers(self) -> List[str]:
        """获取可用的数据提供者列表

        Returns:
            提供者名称列表
        """
        pass

    @abstractmethod
    def get_stock_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        provider: Optional[str] = None,
        fallback: bool = True
    ) -> pd.DataFrame:
        """获取股票数据（带降级）

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            provider: 指定提供者，如果为None则使用默认提供者
            fallback: 是否在主提供者失败时降级到备用提供者

        Returns:
            股票数据DataFrame

        Raises:
            DataFetchError: 所有提供者都失败时抛出
        """
        pass

    @abstractmethod
    def register_provider(self, provider: IDataProvider) -> None:
        """注册数据提供者

        Args:
            provider: 数据提供者实例
        """
        pass

    @abstractmethod
    def set_default_provider(self, provider_name: str) -> None:
        """设置默认数据提供者

        Args:
            provider_name: 提供者名称

        Raises:
            ProviderNotFoundError: 提供者不存在
        """
        pass

    @abstractmethod
    def get_default_provider(self) -> str:
        """获取默认数据提供者名称

        Returns:
            默认提供者名称
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, bool]:
        """健康检查所有数据提供者

        Returns:
            {提供者名称: 是否健康} 字典
        """
        pass


class IDataQualityMonitor(ABC):
    """数据质量监控接口

    监控数据源的质量指标：
    - 数据完整性
    - 响应时间
    - 错误率
    """

    @abstractmethod
    def record_fetch(
        self,
        provider: str,
        symbol: str,
        success: bool,
        duration_ms: float,
        error: Optional[str] = None
    ) -> None:
        """记录数据获取事件

        Args:
            provider: 提供者名称
            symbol: 股票代码
            success: 是否成功
            duration_ms: 耗时（毫秒）
            error: 错误信息（如果失败）
        """
        pass

    @abstractmethod
    def get_provider_stats(
        self,
        provider: str,
        time_range: str = '1d'
    ) -> Dict[str, Any]:
        """获取提供者统计信息

        Args:
            provider: 提供者名称
            time_range: 时间范围 ('1h', '1d', '7d', '30d')

        Returns:
            统计信息字典：
            {
                'total_requests': int,
                'success_rate': float,
                'avg_duration_ms': float,
                'error_count': int,
                'last_error': str
            }
        """
        pass

    @abstractmethod
    def get_data_completeness(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> float:
        """检查数据完整性

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            完整性比例 (0.0 - 1.0)
        """
        pass

    @abstractmethod
    def alert_on_quality_issue(
        self,
        provider: str,
        issue_type: str,
        details: dict
    ) -> None:
        """数据质量告警

        Args:
            provider: 提供者名称
            issue_type: 问题类型 ('high_error_rate', 'slow_response', 'data_gap')
            details: 详细信息
        """
        pass
