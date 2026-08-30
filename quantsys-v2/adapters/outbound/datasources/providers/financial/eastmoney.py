"""Eastmoney financial data provider — wraps EastmoneyDirectProvider"""
import logging
from datetime import datetime
from typing import Optional

from adapters.outbound.datasources.models import FinancialData

logger = logging.getLogger(__name__)


class EastmoneyFinancialProvider:
    """东方财富财务数据 provider（通过 EastmoneyDirectProvider 获取）"""

    def __init__(self):
        self.last_error: Optional[str] = None

    @property
    def name(self) -> str:
        return 'eastmoney-direct'

    def get_financial(self, symbol: str, report_type: str = 'latest') -> Optional[FinancialData]:
        """获取财务数据

        Args:
            symbol: 股票代码（如 600519.SH）
            report_type: 'latest' | 'quarterly' | 'annual'

        Returns:
            FinancialData 或 None
        """
        self.last_error = None
        try:
            from application.services.financial_providers.eastmoney_direct_provider import (
                EastmoneyDirectProvider,
            )

            provider = EastmoneyDirectProvider(timeout=15)
            statement_type = 'all'
            periods = 4 if report_type == 'latest' else 8

            data = provider.get_financial_data(
                symbol=symbol,
                statement_type=statement_type,
                periods=periods,
            )

            if not data:
                self.last_error = f'EastmoneyDirect 返回空数据: {symbol}'
                return None

            return FinancialData(
                symbol=symbol,
                roe=getattr(data, 'roe', None),
                gross_margin=getattr(data, 'gross_margin', None),
                net_profit_margin=getattr(data, 'net_profit_margin', None),
                debt_ratio=getattr(data, 'debt_ratio', None),
                revenue_growth=getattr(data, 'revenue_growth', None),
                ocf_to_profit=getattr(data, 'ocf_to_profit', None),
                current_ratio=getattr(data, 'current_ratio', None),
                roa=getattr(data, 'roa', None),
                operating_margin=getattr(data, 'operating_margin', None),
                source=self.name,
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            self.last_error = f'EastmoneyDirect 获取财务数据失败: {type(e).__name__}: {e}'
            logger.warning(f"EastmoneyFinancialProvider.get_financial failed for {symbol}: {e}")
            return None
