"""Adapter: wraps DataProviderManager to provide FinancialDataService-compatible interface.

This allows internal services to migrate from FinancialDataService to
DataProviderManager without changing their calling code.
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import structlog

from adapters.outbound.datasources import get_data_provider_manager

logger = structlog.get_logger(__name__)


@dataclass
class FinancialStatementData:
    """Compatible with old FinancialDataService return type."""
    symbol: str
    statement_type: str = 'all'
    periods: int = 4
    income_statement: List[Dict[str, Any]] = field(default_factory=list)
    balance_sheet: List[Dict[str, Any]] = field(default_factory=list)
    cash_flow: List[Dict[str, Any]] = field(default_factory=list)
    source: str = ''


class FinancialDataServiceAdapter:
    """Wraps DataProviderManager to match old FinancialDataService interface."""

    def __init__(self):
        self.total_requests = 0
        self.success_count = 0
        self.failure_count = 0
        self.provider_stats = {}

    def get_financial_data(self, symbol: str, statement_type: str = 'all', periods: int = 4) -> FinancialStatementData:
        self.total_requests += 1
        mgr = get_data_provider_manager()

        result = FinancialStatementData(
            symbol=symbol,
            statement_type=statement_type,
            periods=periods,
        )

        try:
            sina_result = mgr.get_sina_financial_statements(symbol)
            if sina_result.get('success') and sina_result.get('data'):
                data = sina_result['data'].data if hasattr(sina_result['data'], 'data') else sina_result['data']
                if isinstance(data, dict):
                    result.income_statement = data.get('income', [])
                    result.balance_sheet = data.get('balance', [])
                    result.cash_flow = data.get('cashflow', [])
                    result.source = sina_result.get('source', 'sina')
                    self.success_count += 1
                    return result
        except Exception as e:
            logger.warning(f"Sina statements failed for {symbol}: {e}")

        try:
            profit_result = mgr.get_profit_sheet(symbol)
            if profit_result.get('success') and profit_result.get('data'):
                data = profit_result['data'].data if hasattr(profit_result['data'], 'data') else profit_result['data']
                if isinstance(data, list):
                    result.income_statement = data
                elif isinstance(data, dict):
                    result.income_statement = data.get('data', [])
                result.source = profit_result.get('source', 'eastmoney')
                self.success_count += 1
        except Exception as e:
            logger.warning(f"Profit sheet failed for {symbol}: {e}")

        try:
            cash_result = mgr.get_cash_flow_sheet(symbol)
            if cash_result.get('success') and cash_result.get('data'):
                data = cash_result['data'].data if hasattr(cash_result['data'], 'data') else cash_result['data']
                if isinstance(data, list):
                    result.cash_flow = data
                elif isinstance(data, dict):
                    result.cash_flow = data.get('data', [])
                if not result.source:
                    result.source = cash_result.get('source', 'eastmoney')
                self.success_count += 1
        except Exception as e:
            logger.warning(f"Cash flow sheet failed for {symbol}: {e}")

        try:
            balance_result = mgr.get_financial(symbol)
            if balance_result.get('success') and balance_result.get('data'):
                result.source = balance_result.get('source', result.source)
        except Exception:
            pass

        if result.income_statement or result.balance_sheet or result.cash_flow:
            return result

        self.failure_count += 1
        raise Exception(f"All providers failed for {symbol}")

    def get_financial_indicators(self, symbol: str) -> Optional[Dict[str, Any]]:
        mgr = get_data_provider_manager()
        try:
            result = mgr.get_financial_analysis_indicator(symbol)
            if result.get('success'):
                return result
        except Exception as e:
            logger.warning(f"Financial indicators failed for {symbol}: {e}")
        return None

    def was_cache_hit(self) -> bool:
        return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            'total_requests': self.total_requests,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
        }

    def clear_cache(self):
        pass

    def reset_stats(self):
        self.total_requests = 0
        self.success_count = 0
        self.failure_count = 0


_adapter: Optional[FinancialDataServiceAdapter] = None


def get_financial_data_service() -> FinancialDataServiceAdapter:
    global _adapter
    if _adapter is None:
        _adapter = FinancialDataServiceAdapter()
    return _adapter
