"""
AkShare Broker Adapter

本适配器将 DataProviderManager 封装为统一的券商接口。
（Phase 3 数据访问治理：内部委托 DataProviderManager，消除 akshare 直接依赖）

注意：仅提供数据，不支持交易功能。
"""

import logging
from typing import List, Optional
from datetime import datetime
import pandas as pd

from ..base_broker import BaseBroker
from ..trading_types import (
    BrokerProfile,
    ApiResponse,
    BrokerQuote,
    BrokerCandle,
    CredentialFieldDef,
    CredentialField,
)

logger = logging.getLogger(__name__)


class AkshareBroker(BaseBroker):
    """
    AkShare 数据源适配器（委托 DataProviderManager）

    特点：
    - 内部使用 DataProviderManager 统一数据层
    - 自动 failover（DB → akshare → tencent → baostock）
    - 不支持交易功能
    """

    def __init__(self):
        """初始化 AkShare 适配器"""
        self._manager = None

    def _get_manager(self):
        """延迟加载 DataProviderManager"""
        if self._manager is None:
            from adapters.outbound.datasources import get_data_provider_manager
            self._manager = get_data_provider_manager()
            logger.info("DataProviderManager loaded for AkshareBroker")
        return self._manager

    # ========================================================================
    # Identity & Configuration
    # ========================================================================

    def get_id(self) -> str:
        """返回券商 ID"""
        return "akshare"

    def get_name(self) -> str:
        """返回券商名称"""
        return "AkShare"

    def get_profile(self) -> BrokerProfile:
        """返回券商配置"""
        return BrokerProfile(
            id="akshare",
            display_name="AkShare (开源数据)",
            region="CN",
            currency="CNY",
            credential_fields=[],  # 无需凭证
            supported_exchanges=["SSE", "SZSE", "BSE"],  # 上交所、深交所、北交所
            product_types=[],
            supports_intraday=True,
            supports_margin=False,
            supports_options=False,
            has_native_paper=False,
            default_paper_balance=1000000.0,
            default_watchlist=[
                "600000",  # 浦发银行
                "000001",  # 平安银行
                "600036",  # 招商银行
                "000858",  # 五粮液
                "601318",  # 中国平安
            ],
            default_symbol="600000",
            default_exchange="SSE",
            brokerage_info="免费开源数据源",
        )

    # ========================================================================
    # Market Data
    # ========================================================================

    def get_quotes(self, symbols: List[str]) -> ApiResponse[List[BrokerQuote]]:
        """
        获取实时行情（委托 DataProviderManager）

        Args:
            symbols: 股票代码列表，支持格式：
                - "600000" (自动识别交易所)
                - "600000.SH"
                - "000001.SZ"

        Returns:
            ApiResponse[List[BrokerQuote]]: 行情数据
        """
        try:
            manager = self._get_manager()
            quotes = []
            
            for symbol in symbols:
                result = manager.get_quote(symbol)
                
                if not result.get('success'):
                    logger.warning(f"Failed to get quote for {symbol}: {result.get('error')}")
                    continue
                
                data = result['data']
                # 构建 BrokerQuote（假设 data 是 QuoteData 对象）
                quote = BrokerQuote(
                    symbol=symbol,
                    last_price=float(data.price),
                    open_price=float(data.open) if hasattr(data, 'open') else 0.0,
                    high_price=float(data.high) if hasattr(data, 'high') else 0.0,
                    low_price=float(data.low) if hasattr(data, 'low') else 0.0,
                    close_price=float(data.prev_close) if hasattr(data, 'prev_close') else 0.0,
                    volume=float(data.volume) if hasattr(data, 'volume') else 0.0,
                    turnover=float(data.turnover) if hasattr(data, 'turnover') else 0.0,
                    change=float(data.change) if hasattr(data, 'change') else 0.0,
                    change_pct=float(data.change_pct) if hasattr(data, 'change_pct') else 0.0,
                    timestamp=datetime.now(),
                )
                quotes.append(quote)

            if not quotes:
                return ApiResponse.fail(f"No quotes found for symbols: {symbols}")

            return ApiResponse.ok(quotes)

        except Exception as e:
            logger.error(f"Failed to get quotes: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to get quotes: {str(e)}")

    def get_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        frequency: str = "daily"
    ) -> ApiResponse[List[BrokerCandle]]:
        """
        获取历史K线数据（委托 DataProviderManager）

        Args:
            symbol: 股票代码
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"
            frequency: 频率，支持 "daily", "weekly", "monthly"

        Returns:
            ApiResponse[List[BrokerCandle]]: K线数据
        """
        try:
            manager = self._get_manager()
            
            # 标准化频率参数
            period_map = {
                "daily": "daily",
                "weekly": "weekly",
                "monthly": "monthly",
            }
            period = period_map.get(frequency, "daily")
            
            # 调用 manager（自动 failover: DB → akshare → tencent → baostock）
            result = manager.get_klines(symbol, period, start_date, end_date)
            
            if not result.get('success'):
                return ApiResponse.fail(f"Failed to get history: {result.get('error')}")
            
            klines_data = result['data']
            if not klines_data:
                return ApiResponse.fail(f"No history data for {symbol}")
            
            # 转换为 BrokerCandle
            candles = []
            for kline in klines_data:
                candle = BrokerCandle(
                    symbol=symbol,
                    timestamp=kline.timestamp,
                    open=float(kline.open),
                    high=float(kline.high),
                    low=float(kline.low),
                    close=float(kline.close),
                    volume=float(kline.volume),
                    turnover=float(kline.turnover) if kline.turnover else None,
                )
                candles.append(candle)

            return ApiResponse.ok(candles)

        except Exception as e:
            logger.error(f"Failed to get history: {e}", exc_info=True)
            return ApiResponse.fail(f"Failed to get history: {str(e)}")

    # ========================================================================
    # Symbol Search
    # ========================================================================

    def search_symbols(
        self,
        query: str,
        exchange: Optional[str] = None
    ) -> ApiResponse[List[dict]]:
        """
        搜索股票（简化版：manager 无全量股票列表，返回提示）

        Args:
            query: 搜索关键词（代码或名称）
            exchange: 交易所过滤，可选

        Returns:
            ApiResponse[List[dict]]: 搜索结果
        """
        # DataProviderManager 当前不提供全量股票搜索接口
        # 此功能需要全量股票列表，可考虑从 database 或添加专门 provider
        return ApiResponse.fail(
            "search_symbols not implemented in DataProviderManager mode. "
            "Use specific symbol queries via get_quotes() instead."
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _infer_exchange(self, symbol: str) -> str:
        """
        根据股票代码推断交易所

        Args:
            symbol: 股票代码

        Returns:
            str: 交易所代码 "SSE"/"SZSE"/"BSE"
        """
        if symbol.startswith('6'):
            return "SSE"  # 上交所
        elif symbol.startswith('0') or symbol.startswith('3'):
            return "SZSE"  # 深交所
        elif symbol.startswith('8') or symbol.startswith('4'):
            return "BSE"  # 北交所
        else:
            return "UNKNOWN"
