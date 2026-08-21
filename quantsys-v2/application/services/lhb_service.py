"""
龙虎榜数据服务

提供龙虎榜数据查询、筛选、格式化等功能。
"""
from typing import List, Dict, Optional
import pandas as pd
import structlog
from datetime import datetime, timedelta
from domain.ports.datasource_ports import ILhbDataSource

from application.services.base_service import ServiceBase

logger = structlog.get_logger(__name__)


class LhbService(ServiceBase):
    """龙虎榜数据服务"""

    def __init__(self, data_source: Optional[LhbDataSource] = None):
        """
        初始化龙虎榜服务

        Args:
            data_source: 数据源实现，默认使用多数据源 LhbDataSource
        """
        super().__init__()
        self.data_source = data_source or LhbDataSource()

    def get_stock_lhb(self, symbol: str, days: int = 30) -> Dict:
        """
        获取个股龙虎榜记录

        Args:
            symbol: 股票代码（如 600737.SH 或 600737）
            days: 查询最近N天（用于过滤，默认 30）

        Returns:
            {
                "success": bool,
                "symbol": str,
                "name": str,
                "total_records": int,
                "records": List[Dict],
                "source": str
            }
        """
        logger.info(f"Fetching LHB for {symbol}, days={days}")

        # 直接调用多数据源，内部已实现 failover
        return self.data_source.get_stock_lhb(symbol, days)

    def get_daily_lhb(self, date: str) -> Dict:
        """
        获取某日全市场龙虎榜

        Args:
            date: 日期（格式 YYYYMMDD，如 20260531）

        Returns:
            {
                "success": bool,
                "date": str,
                "total_stocks": int,
                "stocks": List[Dict],
                "source": str
            }
        """
        logger.info(f"Fetching daily LHB for {date}")

        # 直接调用多数据源，内部已实现 failover
        return self.data_source.get_daily_lhb(date)
