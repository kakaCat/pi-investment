"""Akshare 财务报表 provider（东财接口）

Phase 3 数据访问治理：集中 application/services 中散落的
stock_cash_flow_sheet_by_report_em / stock_profit_sheet_by_report_em 调用。
"""
import logging
from typing import Optional
from datetime import datetime

from adapters.outbound.datasources.models import StockData, MarketData
from infrastructure.config.proxy import proxy_disabled

logger = logging.getLogger(__name__)


class AkshareFinancialStatementProvider:
    """Akshare 财务报表 provider（东财利润表/现金流量表）"""

    @property
    def name(self) -> str:
        return 'akshare-financial'

    def _fetch_sheet(self, fetch_fn_name: str, symbol: str) -> Optional[StockData]:
        """通用报表获取

        Args:
            fetch_fn_name: akshare 函数名
            symbol: 股票代码（东财格式，如 'SH600519'，调用方负责格式化）
        """
        try:
            import akshare as ak

            fetch_fn = getattr(ak, fetch_fn_name)
            df = fetch_fn(symbol=symbol)

            if df is None or df.empty:
                return None

            records = df.where(df.notna(), None).to_dict('records')
            return StockData(
                symbol=symbol,
                data_type=fetch_fn_name,
                data=records,
                total=len(records),
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} {fetch_fn_name} failed for {symbol}: {e}")
            return None

    def get_cash_flow_sheet(self, symbol: str) -> Optional[StockData]:
        """现金流量表（stock_cash_flow_sheet_by_report_em）"""
        return self._fetch_sheet('stock_cash_flow_sheet_by_report_em', symbol)

    def get_profit_sheet(self, symbol: str) -> Optional[StockData]:
        """利润表（stock_profit_sheet_by_report_em）"""
        return self._fetch_sheet('stock_profit_sheet_by_report_em', symbol)

    def get_sina_statements(self, clean_symbol: str) -> Optional[MarketData]:
        """新浪三大报表全量原始记录（stock_financial_report_sina）

        与 application/services/financial_providers 的 provider 不同：
        不截断、不裁剪列——策略沙箱的财务注入需要全历史做时间线对齐
        （从 strategy_code_service._fetch_from_sina 迁移，Phase 3）。

        Args:
            clean_symbol: 6 位裸代码（调用方负责去后缀）

        Returns:
            MarketData(data={'income': [...], 'balance': [...], 'cashflow': [...]})
        """
        try:
            import akshare as ak

            result = {}
            with proxy_disabled():
                for key, sheet in [('income', '利润表'), ('balance', '资产负债表'), ('cashflow', '现金流量表')]:
                    df = ak.stock_financial_report_sina(stock=clean_symbol, symbol=sheet)
                    result[key] = df.where(df.notna(), None).to_dict(orient='records') if df is not None and not df.empty else []

            return MarketData(
                data_type='sina_statements',
                data=result,
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_sina_statements failed for {clean_symbol}: {e}")
            return None

    def get_financial_analysis_indicator(self, clean_symbol: str) -> Optional[MarketData]:
        """东财财务分析指标全量原始记录（stock_financial_analysis_indicator）

        不截断（策略沙箱需要全历史）。
        （从 strategy_code_service._fetch_from_eastmoney 迁移，Phase 3）

        Returns:
            MarketData(data={'records': [...]})
        """
        try:
            import akshare as ak

            with proxy_disabled():
                df = ak.stock_financial_analysis_indicator(symbol=clean_symbol)
            if df is None or df.empty:
                return None

            records = df.where(df.notna(), None).to_dict(orient='records')
            return MarketData(
                data_type='financial_analysis_indicator',
                data={'records': records, 'total': len(records)},
                source=self.name,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.warning(f"{self.name} get_financial_analysis_indicator failed for {clean_symbol}: {e}")
            return None
