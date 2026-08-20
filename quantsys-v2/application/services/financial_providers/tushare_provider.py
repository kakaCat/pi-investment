"""
Tushare Pro 财务数据提供者

需要 Tushare token，可在 https://tushare.pro/ 免费注册获取。
免费用户每分钟可调用 200 次，每天 10000 次。
"""
import logging
from datetime import datetime
from typing import Dict, Any
import pandas as pd
from .base import FinancialProvider, FinancialData
from infrastructure.config import get_config

logger = logging.getLogger(__name__)


class TushareFinancialProvider(FinancialProvider):
    """Tushare Pro 财务数据提供者"""

    def __init__(self, token: str = None, timeout: int = 10):
        """初始化

        Args:
            token: Tushare Pro token（如果为 None，从配置读取）
            timeout: 超时时间（秒）
        """
        super().__init__(name="tushare", timeout=timeout)

        config = get_config()
        self.token = token or config.external.tushare_token
        if not self.token:
            raise ValueError("Tushare token is required. Set TUSHARE_TOKEN environment variable or pass token parameter.")

        try:
            import tushare as ts
            ts.set_token(self.token)
            self.pro = ts.pro_api()
            logger.info("[tushare] Tushare Pro initialized successfully")
        except ImportError:
            raise ImportError("tushare package not found. Install with: pip install tushare")
        except Exception as e:
            raise Exception(f"Failed to initialize Tushare Pro: {e}")

    def get_financial_data(
        self,
        symbol: str,
        statement_type: str = 'all',
        periods: int = 4
    ) -> FinancialData:
        """通过 Tushare Pro 获取财务数据

        Args:
            symbol: 股票代码（如 600519.SH）
            statement_type: 报表类型 ('income', 'balance', 'cash_flow', 'all')
            periods: 返回期数

        Returns:
            FinancialData 对象

        Raises:
            Exception: 获取失败
        """
        try:
            # 规范化代码
            standard_symbol, _ = self._normalize_symbol(symbol)

            # Tushare 使用 TS 代码格式（如 600519.SH）
            ts_code = standard_symbol

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
                    df = self.pro.income(ts_code=ts_code, fields=[
                        'end_date', 'total_revenue', 'revenue', 'operate_profit',
                        'total_profit', 'n_income', 'n_income_attr_p', 'basic_eps'
                    ])
                    if df is not None and not df.empty:
                        df = df.head(periods)
                        df = df.rename(columns={
                            'end_date': '报告日',
                            'total_revenue': '营业总收入',
                            'revenue': '营业收入',
                            'operate_profit': '营业利润',
                            'total_profit': '利润总额',
                            'n_income': '净利润',
                            'n_income_attr_p': '归属净利润',
                            'basic_eps': '基本每股收益'
                        })
                        df = df.where(df.notna(), None)
                        result.income_statement = df.to_dict(orient='records')
                        logger.debug(f"[{self.name}] 成功获取 {standard_symbol} 利润表")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取利润表失败 {standard_symbol}: {e}")
                    if statement_type == 'income':
                        raise Exception(f"利润表获取失败: {e}") from e

            # 获取资产负债表
            if statement_type in ('balance', 'all'):
                try:
                    df = self.pro.balancesheet(ts_code=ts_code, fields=[
                        'end_date', 'total_assets', 'total_liab', 'total_hldr_eqy_inc_min_int',
                        'total_cur_assets', 'total_nca', 'total_cur_liab', 'total_ncl'
                    ])
                    if df is not None and not df.empty:
                        df = df.head(periods)
                        df = df.rename(columns={
                            'end_date': '报告日',
                            'total_assets': '总资产',
                            'total_liab': '总负债',
                            'total_hldr_eqy_inc_min_int': '股东权益合计',
                            'total_cur_assets': '流动资产',
                            'total_nca': '非流动资产',
                            'total_cur_liab': '流动负债',
                            'total_ncl': '非流动负债'
                        })
                        df = df.where(df.notna(), None)
                        result.balance_sheet = df.to_dict(orient='records')
                        logger.debug(f"[{self.name}] 成功获取 {standard_symbol} 资产负债表")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取资产负债表失败 {standard_symbol}: {e}")
                    if statement_type == 'balance':
                        raise Exception(f"资产负债表获取失败: {e}") from e

            # 获取现金流量表
            if statement_type in ('cash_flow', 'cashflow', 'all'):
                try:
                    df = self.pro.cashflow(ts_code=ts_code, fields=[
                        'end_date', 'n_cashflow_act', 'n_cashflow_inv_act',
                        'n_cash_flows_fnc_act', 'c_cash_equ_end_period'
                    ])
                    if df is not None and not df.empty:
                        df = df.head(periods)
                        df = df.rename(columns={
                            'end_date': '报告日',
                            'n_cashflow_act': '经营活动产生的现金流量净额',
                            'n_cashflow_inv_act': '投资活动产生的现金流量净额',
                            'n_cash_flows_fnc_act': '筹资活动产生的现金流量净额',
                            'c_cash_equ_end_period': '期末现金及现金等价物余额'
                        })
                        df = df.where(df.notna(), None)
                        result.cash_flow = df.to_dict(orient='records')
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
            raise Exception(f"Tushare 查询失败: {e}") from e
