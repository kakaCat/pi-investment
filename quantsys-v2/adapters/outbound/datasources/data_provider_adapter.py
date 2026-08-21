"""
数据提供者管理器适配器

封装现有的 DataProviderManager，提供统一的数据源访问接口。
"""
import logging
from typing import Any, Optional, List, Dict
import pandas as pd

from domain.ports.data_provider_port import (
    IDataProvider,
    IDataProviderManager,
    IDataQualityMonitor
)
from adapters.outbound.datasources.manager import DataProviderManager as DataProviderManagerImpl

logger = logging.getLogger(__name__)


class DataProviderAdapter(IDataProviderManager):
    """数据提供者管理器适配器

    适配器模式：将现有的 DataProviderManager 封装为端口接口实现
    """

    def __init__(self, ds=None):
        """初始化数据提供者管理器

        Args:
            ds: 可选的数据服务实例（用于 DatabaseKlineProvider）
        """
        self._manager = DataProviderManagerImpl(ds)

    def get_provider(self, provider_name: str) -> Any:
        """获取指定的数据提供者

        Args:
            provider_name: 提供者名称

        Returns:
            数据提供者实例

        Raises:
            ProviderNotFoundError: 提供者不存在
        """
        # DataProviderManager 没有直接的 get_provider 方法
        # 这里返回管理器本身，因为它提供了所有必要的方法
        logger.warning(
            f"get_provider({provider_name}) called on adapter, "
            "returning manager instance"
        )
        return self._manager

    def get_available_providers(self) -> List[str]:
        """获取可用的数据提供者列表

        Returns:
            提供者名称列表
        """
        providers = []

        # 收集所有 provider 的名称
        for provider in self._manager.quote_providers:
            providers.append(provider.__class__.__name__)

        for provider in self._manager.kline_providers:
            providers.append(provider.__class__.__name__)

        for provider in self._manager.stock_providers:
            providers.append(provider.__class__.__name__)

        return list(set(providers))  # 去重

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
            provider: 指定提供者（当前忽略，使用默认优先级）
            fallback: 是否在主提供者失败时降级（DataProviderManager 自动处理）

        Returns:
            股票数据DataFrame

        Raises:
            DataFetchError: 所有提供者都失败时抛出
        """
        # DataProviderManager 自动处理降级逻辑
        # 这里简单委托给 manager
        logger.info(
            f"Fetching stock data for {symbol} "
            f"from {start_date} to {end_date}"
        )

        # 注意：DataProviderManager 的实际方法可能不同
        # 这里提供一个通用的实现模式
        raise NotImplementedError(
            "get_stock_data needs to be implemented based on "
            "DataProviderManager's actual API"
        )

    def register_provider(self, provider: IDataProvider) -> None:
        """注册数据提供者

        Args:
            provider: 数据提供者实例
        """
        logger.warning("register_provider not implemented in current adapter")
        # DataProviderManager 使用固定的 provider 列表
        # 如果需要动态注册，需要扩展 DataProviderManager

    def set_default_provider(self, provider_name: str) -> None:
        """设置默认数据提供者

        Args:
            provider_name: 提供者名称
        """
        logger.warning("set_default_provider not implemented in current adapter")
        # DataProviderManager 使用优先级列表而非单一默认提供者

    def get_default_provider(self) -> str:
        """获取默认数据提供者名称

        Returns:
            默认提供者名称
        """
        # 返回优先级列表中的第一个
        if self._manager.quote_providers:
            return self._manager.quote_providers[0].__class__.__name__
        return "Unknown"

    def health_check(self) -> Dict[str, bool]:
        """健康检查所有数据提供者

        Returns:
            {提供者名称: 是否健康} 字典
        """
        health_status = {}

        # 检查所有 quote providers
        for provider in self._manager.quote_providers:
            provider_name = provider.__class__.__name__
            # 简单检查：看是否在统计中有记录
            stats = self._manager.provider_stats.get(provider_name, {})
            success_count = stats.get('success', 0)
            failure_count = stats.get('failure', 0)

            # 如果成功率 > 50%，认为健康
            total = success_count + failure_count
            if total > 0:
                health_status[provider_name] = (success_count / total) > 0.5
            else:
                health_status[provider_name] = True  # 未使用过，假设健康

        return health_status


class SimpleDataQualityMonitor(IDataQualityMonitor):
    """简单的数据质量监控实现

    提供基本的数据质量监控功能
    """

    def __init__(self):
        """初始化监控器"""
        self._fetch_records: List[Dict[str, Any]] = []

    def record_fetch(
        self,
        provider: str,
        symbol: str,
        success: bool,
        duration_ms: float,
        error: Optional[str] = None
    ) -> None:
        """记录数据获取事件"""
        record = {
            'provider': provider,
            'symbol': symbol,
            'success': success,
            'duration_ms': duration_ms,
            'error': error,
            'timestamp': pd.Timestamp.now()
        }
        self._fetch_records.append(record)

        # 保留最近 1000 条记录
        if len(self._fetch_records) > 1000:
            self._fetch_records = self._fetch_records[-1000:]

    def get_provider_stats(
        self,
        provider: str,
        time_range: str = '1d'
    ) -> Dict[str, Any]:
        """获取提供者统计信息"""
        # 过滤时间范围
        now = pd.Timestamp.now()
        if time_range == '1h':
            cutoff = now - pd.Timedelta(hours=1)
        elif time_range == '1d':
            cutoff = now - pd.Timedelta(days=1)
        elif time_range == '7d':
            cutoff = now - pd.Timedelta(days=7)
        elif time_range == '30d':
            cutoff = now - pd.Timedelta(days=30)
        else:
            cutoff = now - pd.Timedelta(days=1)

        # 筛选记录
        records = [
            r for r in self._fetch_records
            if r['provider'] == provider and r['timestamp'] >= cutoff
        ]

        if not records:
            return {
                'total_requests': 0,
                'success_rate': 0.0,
                'avg_duration_ms': 0.0,
                'error_count': 0,
                'last_error': None
            }

        total = len(records)
        success_count = sum(1 for r in records if r['success'])
        error_count = total - success_count
        avg_duration = sum(r['duration_ms'] for r in records) / total

        last_error = None
        for r in reversed(records):
            if r['error']:
                last_error = r['error']
                break

        return {
            'total_requests': total,
            'success_rate': success_count / total,
            'avg_duration_ms': avg_duration,
            'error_count': error_count,
            'last_error': last_error
        }

    def get_data_completeness(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> float:
        """检查数据完整性"""
        # 简化实现：返回 1.0（假设完整）
        # 实际实现需要检查交易日数据是否完整
        logger.warning("get_data_completeness not fully implemented")
        return 1.0

    def alert_on_quality_issue(
        self,
        provider: str,
        issue_type: str,
        details: dict
    ) -> None:
        """数据质量告警"""
        logger.warning(
            f"Data quality issue detected: provider={provider}, "
            f"type={issue_type}, details={details}"
        )
