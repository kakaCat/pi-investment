"""qs_market_data — 数据供给包（外部行情/K线/财务/估值的唯一取数出口）。

由 quantsys-v2 单体抽离（2026-10-18，方案卡 docs/plans/package-boundaries-import-linter.md S3）。
包内三层沿用原领域布局：
- qs_market_data.application.services.*    数据供给服务（DataService/实时行情/分红/估值/日历/校验/回补等）
- qs_market_data.adapters.outbound.datasources.*  Provider 框架（manager + providers 13 子包，CLAUDE.md「Data Access Rules」对齐物）
"""

__version__ = "0.1.0"

from qs_market_data.adapters.outbound.datasources import (  # noqa: F401
    DataProviderManager,
    DividendData,
    DividendProvider,
    FinancialData,
    FinancialProvider,
    MarketData,
    MarketProvider,
    QuoteData,
    QuoteProvider,
    StockData,
    StockProvider,
    get_data_provider_manager,
)

__all__ = [
    "DataProviderManager",
    "get_data_provider_manager",
    "QuoteData",
    "FinancialData",
    "DividendData",
    "MarketData",
    "StockData",
    "QuoteProvider",
    "FinancialProvider",
    "DividendProvider",
    "MarketProvider",
    "StockProvider",
]
