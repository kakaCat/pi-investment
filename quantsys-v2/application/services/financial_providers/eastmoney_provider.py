"""
东方财富财务数据提供者

通过 akshare 的东方财富接口获取财务数据。
"""
import logging
from datetime import datetime
from typing import Dict, Any
import pandas as pd
from .base import FinancialProvider, FinancialData

logger = logging.getLogger(__name__)


class EastmoneyFinancialProvider(FinancialProvider):
    """东方财富财务数据提供者"""

    def __init__(self, timeout: int = 10):
        super().__init__(name="eastmoney", timeout=timeout)

    def get_financial_data(
        self,
        symbol: str,
        statement_type: str = 'all',
        periods: int = 4
    ) -> FinancialData:
        """通过东方财富获取财务数据

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

            # 禁用代理
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)
            os.environ.pop('http_proxy', None)
            os.environ.pop('https_proxy', None)

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
                    df = ak.stock_financial_analysis_indicator(symbol=short_code)
                    if df is not None and not df.empty:
                        # 东方财富返回的是财务指标，需要转换为利润表格式
                        df = df.head(periods)
                        # 转换日期列
                        if '日期' in df.columns:
                            df['日期'] = df['日期'].astype(str)
                        df = df.where(df.notna(), None)

                        # 提取利润表相关字段
                        income_cols = ['日期', '营业总收入', '营业收入', '营业总成本', '营业利润',
                                      '利润总额', '净利润', '归属净利润', '基本每股收益']
                        available_cols = [col for col in income_cols if col in df.columns]
                        if available_cols:
                            result.income_statement = df[available_cols].to_dict(orient='records')
                            logger.debug(f"[{self.name}] 成功获取 {standard_symbol} 利润表")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取利润表失败 {standard_symbol}: {e}")
                    if statement_type == 'income':
                        raise Exception(f"利润表获取失败: {e}") from e

            # 获取资产负债表
            if statement_type in ('balance', 'all'):
                try:
                    df = ak.stock_financial_analysis_indicator(symbol=short_code)
                    if df is not None and not df.empty:
                        df = df.head(periods)
                        if '日期' in df.columns:
                            df['日期'] = df['日期'].astype(str)
                        df = df.where(df.notna(), None)

                        # 提取资产负债表相关字段
                        balance_cols = ['日期', '总资产', '总负债', '股东权益合计', '资产负债率',
                                       '流动资产', '非流动资产', '流动负债', '非流动负债']
                        available_cols = [col for col in balance_cols if col in df.columns]
                        if available_cols:
                            result.balance_sheet = df[available_cols].to_dict(orient='records')
                            logger.debug(f"[{self.name}] 成功获取 {standard_symbol} 资产负债表")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取资产负债表失败 {standard_symbol}: {e}")
                    if statement_type == 'balance':
                        raise Exception(f"资产负债表获取失败: {e}") from e

            # 获取现金流量表
            if statement_type in ('cash_flow', 'cashflow', 'all'):
                try:
                    df = ak.stock_financial_analysis_indicator(symbol=short_code)
                    if df is not None and not df.empty:
                        df = df.head(periods)
                        if '日期' in df.columns:
                            df['日期'] = df['日期'].astype(str)
                        df = df.where(df.notna(), None)

                        # 提取现金流量表相关字段
                        cashflow_cols = ['日期', '经营活动产生的现金流量净额', '投资活动产生的现金流量净额',
                                        '筹资活动产生的现金流量净额', '现金及现金等价物净增加额']
                        available_cols = [col for col in cashflow_cols if col in df.columns]
                        if available_cols:
                            result.cash_flow = df[available_cols].to_dict(orient='records')
                            logger.debug(f"[{self.name}] 成功获取 {standard_symbol} 现金流量表")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取现金流量表失败 {standard_symbol}: {e}")
                    if statement_type in ('cash_flow', 'cashflow'):
                        raise Exception(f"现金流量表获取失败: {e}") from e

            # 验证至少获取了一个报表
            if (result.income_statement is None and
                result.balance_sheet is None and
                result.cash_flow is None):
                raise Exception("未能获取任何财务报表数据")

            return result

        except Exception as e:
            logger.error(f"[{self.name}] 获取财务数据失败 {symbol}: {e}")
            raise Exception(f"东方财富查询失败: {e}") from e
