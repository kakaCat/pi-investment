"""
东方财富直接 API 数据提供者

不依赖 AkShare，直接调用东方财富 API，参考实时行情的成功经验。
"""
import logging
import requests
from datetime import datetime
from typing import Dict, Any, List
from .base import FinancialProvider, FinancialData

logger = logging.getLogger(__name__)


class EastmoneyDirectProvider(FinancialProvider):
    """东方财富直接 API 数据提供者"""

    def __init__(self, timeout: int = 10):
        super().__init__(name="eastmoney_direct", timeout=timeout)

    def get_financial_data(
        self,
        symbol: str,
        statement_type: str = 'all',
        periods: int = 4
    ) -> FinancialData:
        """通过东方财富 API 获取财务数据

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
                    data = self._fetch_income_statement(short_code, periods)
                    if data:
                        result.income_statement = data
                        logger.info(f"[{self.name}] 成功获取 {standard_symbol} 利润表 ({len(data)} 期)")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取利润表失败 {standard_symbol}: {e}")

            # 获取资产负债表
            if statement_type in ('balance', 'all'):
                try:
                    data = self._fetch_balance_sheet(short_code, periods)
                    if data:
                        result.balance_sheet = data
                        logger.info(f"[{self.name}] 成功获取 {standard_symbol} 资产负债表 ({len(data)} 期)")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取资产负债表失败 {standard_symbol}: {e}")

            # 获取现金流量表
            if statement_type in ('cash_flow', 'cashflow', 'all'):
                try:
                    data = self._fetch_cashflow_statement(short_code, periods)
                    if data:
                        result.cash_flow = data
                        logger.info(f"[{self.name}] 成功获取 {standard_symbol} 现金流量表 ({len(data)} 期)")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取现金流量表失败 {standard_symbol}: {e}")

            # 验证至少获取了一个报表
            if not (result.income_statement or result.balance_sheet or result.cash_flow):
                raise Exception("未能获取任何财务报表数据")

            return result

        except Exception as e:
            logger.error(f"[{self.name}] 获取财务数据失败 {symbol}: {e}")
            raise

    def _fetch_income_statement(self, symbol: str, periods: int) -> List[Dict[str, Any]]:
        """获取利润表"""
        url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        params = {
            'reportName': 'RPT_LICO_FN_CPD',
            'columns': 'ALL',
            'filter': f'(SECURITY_CODE="{symbol}")',
            'pageNumber': '1',
            'pageSize': str(periods),
            'sortTypes': '-1',
            'sortColumns': 'NOTICE_DATE',
            'source': 'WEB',
            'client': 'WEB'
        }

        # 禁用代理
        response = requests.get(
            url,
            params=params,
            timeout=self.timeout,
            proxies={'http': None, 'https': None}
        )

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        data = response.json()
        # 东方财富返回 code=0 表示成功
        if data.get('code') != 0:
            raise Exception(f"API 返回错误: {data.get('message', 'unknown')}")

        records = data.get('result', {}).get('data', [])
        if not records:
            raise Exception("无数据返回")

        # 转换为标准格式
        return [self._convert_income_record(r) for r in records]

    def _fetch_balance_sheet(self, symbol: str, periods: int) -> List[Dict[str, Any]]:
        """获取资产负债表"""
        url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        params = {
            'reportName': 'RPT_DMSK_FN_BALANCE',
            'columns': 'ALL',
            'filter': f'(SECURITY_CODE="{symbol}")',
            'pageNumber': '1',
            'pageSize': str(periods),
            'sortTypes': '-1',
            'sortColumns': 'NOTICE_DATE',
            'source': 'WEB',
            'client': 'WEB'
        }

        response = requests.get(
            url,
            params=params,
            timeout=self.timeout,
            proxies={'http': None, 'https': None}
        )

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        data = response.json()
        if data.get('code') != 0:
            raise Exception(f"API 返回错误: {data.get('message', 'unknown')}")

        records = data.get('result', {}).get('data', [])
        if not records:
            raise Exception("无数据返回")

        return [self._convert_balance_record(r) for r in records]

    def _fetch_cashflow_statement(self, symbol: str, periods: int) -> List[Dict[str, Any]]:
        """获取现金流量表"""
        url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        params = {
            'reportName': 'RPT_DMSK_FN_CASHFLOW',
            'columns': 'ALL',
            'filter': f'(SECURITY_CODE="{symbol}")',
            'pageNumber': '1',
            'pageSize': str(periods),
            'sortTypes': '-1',
            'sortColumns': 'NOTICE_DATE',
            'source': 'WEB',
            'client': 'WEB'
        }

        response = requests.get(
            url,
            params=params,
            timeout=self.timeout,
            proxies={'http': None, 'https': None}
        )

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        data = response.json()
        if data.get('code') != 0:
            raise Exception(f"API 返回错误: {data.get('message', 'unknown')}")

        records = data.get('result', {}).get('data', [])
        if not records:
            raise Exception("无数据返回")

        return [self._convert_cashflow_record(r) for r in records]

    def _convert_income_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """转换利润表记录为标准格式
        
        东方财富 RPT_LICO_FN_CPD API 不返回 TOTAL_OPERATE_COST/NETPROFIT 等详细字段，
        但返回 XSMLL（销售毛利率）和 WEIGHTAVG_ROE（加权ROE），可据此推导其他字段。
        """
        total_revenue = record.get('TOTAL_OPERATE_INCOME')
        gross_margin = record.get('XSMLL')  # 销售毛利率（%），如 33.26
        
        # 从毛利率反推营业成本
        total_cost = None
        if total_revenue is not None and gross_margin is not None:
            total_cost = total_revenue * (1 - gross_margin / 100)
        
        return {
            'report_date': record.get('REPORTDATE', '').split(' ')[0] if record.get('REPORTDATE') else None,
            'total_revenue': total_revenue,
            'revenue': record.get('OPERATE_INCOME') or total_revenue,
            'total_cost': total_cost,
            'gross_margin': gross_margin,  # 直接使用东方财富的毛利率
            'operating_profit': record.get('OPERATE_PROFIT'),
            'total_profit': record.get('TOTAL_PROFIT'),
            'net_profit': record.get('NETPROFIT'),
            'parent_net_profit': record.get('PARENT_NETPROFIT'),
            'basic_eps': record.get('BASIC_EPS'),
            'weighted_roe': record.get('WEIGHTAVG_ROE'),  # 加权ROE
        }

    def _convert_balance_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """转换资产负债表记录为标准格式"""
        return {
            'report_date': record.get('REPORT_DATE', '').split('T')[0] if record.get('REPORT_DATE') else None,
            'total_assets': record.get('TOTAL_ASSETS'),
            'total_liabilities': record.get('TOTAL_LIABILITIES'),
            'total_equity': record.get('TOTAL_EQUITY'),
            'asset_liab_ratio': record.get('ASSET_LIAB_RATIO'),
            'current_assets': record.get('CURRENT_ASSETS'),
            'current_liabilities': record.get('CURRENT_LIABILITIES'),
        }

    def _convert_cashflow_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """转换现金流量表记录为标准格式"""
        return {
            'report_date': record.get('REPORT_DATE', '').split('T')[0] if record.get('REPORT_DATE') else None,
            'operating_cash_flow': record.get('OPERATE_CASH_FLOW_NET'),
            'investing_cash_flow': record.get('INVEST_CASH_FLOW_NET'),
            'financing_cash_flow': record.get('FINANCE_CASH_FLOW_NET'),
            'cash_increase': record.get('CCE_ADD'),
        }
