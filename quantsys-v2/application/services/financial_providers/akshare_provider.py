"""
AkShare 财务数据提供者 - 参考实时行情的成功经验

关键改进：
1. 禁用代理（proxies={'http': None, 'https': None}）
2. 使用环境变量清理代理设置
3. 简单直接的 API 调用
"""
import logging
import os
from datetime import datetime
from typing import Optional
from .base import FinancialProvider, FinancialData

logger = logging.getLogger(__name__)


class AkshareFinancialProvider(FinancialProvider):
    """AkShare 财务数据提供者"""

    def __init__(self, timeout: int = 10):
        super().__init__(name="akshare", timeout=timeout)

    def get_financial_data(
        self,
        symbol: str,
        statement_type: str = 'all',
        periods: int = 4
    ) -> FinancialData:
        """通过 AkShare 获取财务数据

        Args:
            symbol: 股票代码
            statement_type: 报表类型
            periods: 期数

        Returns:
            FinancialData 对象

        Raises:
            Exception: 获取失败
        """
        try:
            import akshare as ak

            # 关键：禁用代理（参考实时行情的成功经验）
            old_http_proxy = os.environ.pop('HTTP_PROXY', None)
            old_https_proxy = os.environ.pop('HTTPS_PROXY', None)
            old_http_proxy_lower = os.environ.pop('http_proxy', None)
            old_https_proxy_lower = os.environ.pop('https_proxy', None)

            try:
                # 规范化代码
                standard_symbol, short_code = self._normalize_symbol(symbol)

                # 创建结果对象
                result = FinancialData(
                    symbol=standard_symbol,
                    name=standard_symbol,
                    statement_type=statement_type,
                    periods=periods,
                    source=self.name,
                    timestamp=datetime.now()
                )

                # 获取利润表
                if statement_type in ('income', 'all'):
                    try:
                        df = ak.stock_profit_sheet_by_report_em(symbol=short_code)
                        if df is not None and not df.empty:
                            df = df.head(periods)
                            # 转换为字典列表
                            result.income_statement = df.to_dict(orient='records')
                            logger.info(f"[{self.name}] 成功获取 {standard_symbol} 利润表 ({len(result.income_statement)} 期)")
                    except Exception as e:
                        logger.warning(f"[{self.name}] 获取利润表失败 {standard_symbol}: {e}")

                # 获取资产负债表
                if statement_type in ('balance', 'all'):
                    try:
                        df = ak.stock_balance_sheet_by_report_em(symbol=short_code)
                        if df is not None and not df.empty:
                            df = df.head(periods)
                            result.balance_sheet = df.to_dict(orient='records')
                            logger.info(f"[{self.name}] 成功获取 {standard_symbol} 资产负债表 ({len(result.balance_sheet)} 期)")
                    except Exception as e:
                        logger.warning(f"[{self.name}] 获取资产负债表失败 {standard_symbol}: {e}")

                # 获取现金流量表
                if statement_type in ('cash_flow', 'cashflow', 'all'):
                    try:
                        df = ak.stock_cash_flow_sheet_by_report_em(symbol=short_code)
                        if df is not None and not df.empty:
                            df = df.head(periods)
                            result.cash_flow = df.to_dict(orient='records')
                            logger.info(f"[{self.name}] 成功获取 {standard_symbol} 现金流量表 ({len(result.cash_flow)} 期)")
                    except Exception as e:
                        logger.warning(f"[{self.name}] 获取现金流量表失败 {standard_symbol}: {e}")

                # 验证至少有一个报表成功
                if not (result.income_statement or result.balance_sheet or result.cash_flow):
                    raise Exception(f"所有报表获取均失败")

                return result

            finally:
                # 恢复代理设置
                if old_http_proxy:
                    os.environ['HTTP_PROXY'] = old_http_proxy
                if old_https_proxy:
                    os.environ['HTTPS_PROXY'] = old_https_proxy
                if old_http_proxy_lower:
                    os.environ['http_proxy'] = old_http_proxy_lower
                if old_https_proxy_lower:
                    os.environ['https_proxy'] = old_https_proxy_lower

        except Exception as e:
            logger.error(f"[{self.name}] 获取财务数据失败 {symbol}: {e}")
            raise
