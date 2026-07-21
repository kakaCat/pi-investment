"""
实时行情服务 - 委托给 DataProviderManager

这个服务现在是一个轻量级包装器，将所有逻辑委托给统一的 DataProviderManager。
这保持了向后兼容性，同时使用统一的数据提供者架构。
"""
import structlog
from typing import Optional
from adapters.outbound.datasources import get_data_provider_manager, QuoteData

logger = structlog.get_logger(__name__)


class RealtimeQuoteService:
    """实时行情服务

    委托给 DataProviderManager，保持向后兼容的API。

    Attributes:
        provider_manager: 统一的数据提供者管理器
    """

    def __init__(self):
        """初始化服务"""
        self.provider_manager = get_data_provider_manager()
        logger.info("RealtimeQuoteService initialized (using DataProviderManager)")

    def get_realtime_quote(self, symbol: str) -> Optional[QuoteData]:
        """获取实时行情

        依次尝试各个数据源，返回第一个成功的结果。

        Args:
            symbol: 股票代码

        Returns:
            QuoteData 或 None（所有数据源都失败时）
        """
        logger.info(f"Fetching quote for {symbol}")

        result = self.provider_manager.get_quote(symbol)

        if result['success']:
            quote_data = result['data']
            logger.info(
                f"Successfully fetched quote for {symbol} from {quote_data.source} "
                f"(price={quote_data.price})"
            )
            return quote_data

        logger.warning(f"Failed to fetch quote for {symbol}: {result.get('error')}")
        return None

    def get_provider_health(self):
        """获取数据源健康状态

        Returns:
            Dict[str, Dict[str, int]]: 各数据源的统计信息
        """
        return self.provider_manager.get_provider_health()
