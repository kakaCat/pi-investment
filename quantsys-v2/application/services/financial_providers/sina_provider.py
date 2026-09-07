"""
新浪财经数据提供者

通过 akshare 的 stock_financial_report_sina 获取财务数据。
"""
import logging
from datetime import datetime
from typing import Dict, Any
import pandas as pd
from .base import FinancialProvider, FinancialData

logger = logging.getLogger(__name__)


class SinaFinancialProvider(FinancialProvider):
    """新浪财经财务数据提供者"""

    def __init__(self, timeout: int = 10):
        super().__init__(name="sina", timeout=timeout)

    def get_financial_data(
        self,
        symbol: str,
        statement_type: str = 'all',
        periods: int = 4
    ) -> FinancialData:
        """通过新浪财经获取财务数据

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
            import os

            def _disable_proxies_permanently():
                """永久禁用代理（akshare 国内接口不需要代理）"""
                for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
                    os.environ.pop(key, None)

            _disable_proxies_permanently()

            # 规范化代码
            standard_symbol, short_code = self._normalize_symbol(symbol)

            # 创建结果对象
            result = FinancialData(
                symbol=standard_symbol,
                name=standard_symbol,  # 先用代码占位
                statement_type=statement_type,
                periods=periods,
                source=self.name,
                timestamp=datetime.now()
            )

            # 获取利润表
            if statement_type in ('income', 'all'):
                try:
                    df = ak.stock_financial_report_sina(
                        stock=short_code,
                        symbol='利润表'
                    )
                    if df is not None and not df.empty:
                        df = df.head(periods)
                        # 转换日期列为字符串
                        for col in ['报告日', '更新日期']:
                            if col in df.columns:
                                df[col] = df[col].astype(str)
                        df = df.where(df.notna(), None)
                        result.income_statement = df.to_dict(orient='records')
                        logger.debug(f"[{self.name}] 成功获取 {standard_symbol} 利润表")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取利润表失败 {standard_symbol}: {e}")
                    raise Exception(f"利润表获取失败: {e}") from e

            # 获取资产负债表
            if statement_type in ('balance', 'all'):
                try:
                    df = ak.stock_financial_report_sina(
                        stock=short_code,
                        symbol='资产负债表'
                    )
                    if df is not None and not df.empty:
                        df = df.head(periods)
                        for col in ['报告日', '更新日期']:
                            if col in df.columns:
                                df[col] = df[col].astype(str)
                        df = df.where(df.notna(), None)
                        result.balance_sheet = df.to_dict(orient='records')
                        logger.debug(f"[{self.name}] 成功获取 {standard_symbol} 资产负债表")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取资产负债表失败 {standard_symbol}: {e}")
                    raise Exception(f"资产负债表获取失败: {e}") from e

            # 获取现金流量表
            if statement_type in ('cash_flow', 'cashflow', 'all'):
                try:
                    df = ak.stock_financial_report_sina(
                        stock=short_code,
                        symbol='现金流量表'
                    )
                    if df is not None and not df.empty:
                        df = df.head(periods)
                        for col in ['报告日', '更新日期']:
                            if col in df.columns:
                                df[col] = df[col].astype(str)
                        df = df.where(df.notna(), None)
                        result.cash_flow = df.to_dict(orient='records')
                        logger.debug(f"[{self.name}] 成功获取 {standard_symbol} 现金流量表")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取现金流量表失败 {standard_symbol}: {e}")
                    raise Exception(f"现金流量表获取失败: {e}") from e

            # 验证至少获取了一个报表
            if (result.income_statement is None and
                result.balance_sheet is None and
                result.cash_flow is None):
                raise Exception("未能获取任何财务报表数据")

            return result

        except Exception as e:
            logger.error(f"[{self.name}] 获取财务数据失败 {symbol}: {e}")
            raise Exception(f"新浪财经查询失败: {e}") from e
