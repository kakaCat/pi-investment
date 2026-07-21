"""
腾讯财经数据提供者

直接调用腾讯财经 API，参考实时行情的成功经验。
腾讯财经在实时行情中验证可用（source=tencent）。
"""
import logging
import requests
import json
from datetime import datetime
from typing import Dict, Any, List
from .base import FinancialProvider, FinancialStatementData

logger = logging.getLogger(__name__)


class TencentFinancialProvider(FinancialProvider):
    """腾讯财经数据提供者"""

    def __init__(self, timeout: int = 10):
        super().__init__(name="tencent", timeout=timeout)

    def get_financial_data(
        self,
        symbol: str,
        statement_type: str = 'all',
        periods: int = 4
    ) -> FinancialStatementData:
        """通过腾讯财经 API 获取财务数据

        Args:
            symbol: 股票代码（如 600426）
            statement_type: 报表类型
            periods: 期数

        Returns:
            FinancialData 对象

        Raises:
            Exception: 获取失败
        """
        try:
            # 规范化代码（获取标准代码和简码）
            standard_symbol, clean_symbol = self._normalize_symbol(symbol)

            # 判断市场代码（腾讯格式：sh600519 或 sz000001）
            if clean_symbol.startswith('6'):
                market_code = f'sh{clean_symbol}'
            else:
                market_code = f'sz{clean_symbol}'

            # 创建结果对象（使用 FinancialStatementData）
            result = FinancialStatementData(
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
                    data = self._fetch_income_statement(market_code, periods)
                    if data:
                        result.income_statement = data
                        logger.info(f"[{self.name}] 成功获取 {clean_symbol} 利润表 ({len(data)} 期)")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取利润表失败 {clean_symbol}: {e}")

            # 获取资产负债表
            if statement_type in ('balance', 'all'):
                try:
                    data = self._fetch_balance_sheet(market_code, periods)
                    if data:
                        result.balance_sheet = data
                        logger.info(f"[{self.name}] 成功获取 {clean_symbol} 资产负债表 ({len(data)} 期)")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取资产负债表失败 {clean_symbol}: {e}")

            # 获取现金流量表
            if statement_type in ('cash_flow', 'cashflow', 'all'):
                try:
                    data = self._fetch_cashflow_statement(market_code, periods)
                    if data:
                        result.cash_flow = data
                        logger.info(f"[{self.name}] 成功获取 {clean_symbol} 现金流量表 ({len(data)} 期)")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取现金流量表失败 {clean_symbol}: {e}")

            # 验证至少获取了一个报表
            if not (result.income_statement or result.balance_sheet or result.cash_flow):
                raise Exception("未能获取任何财务报表数据")

            return result

        except Exception as e:
            logger.error(f"[{self.name}] 获取财务数据失败 {symbol}: {e}")
            raise

    def _fetch_income_statement(self, market_code: str, periods: int) -> List[Dict[str, Any]]:
        """获取利润表"""
        # 腾讯财经利润表 API
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

        params = {
            'param': f'{market_code},lrb,,,{periods}',
            '_var': 'kline_daylrb'
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

        # 解析响应（腾讯返回的是 JSONP 格式）
        text = response.text
        if not text or 'kline_daylrb=' not in text:
            raise Exception("响应格式错误")

        # 提取 JSON 部分
        json_str = text.split('kline_daylrb=')[1].strip()
        data = json.loads(json_str)

        if 'data' not in data or not data['data']:
            raise Exception("无数据返回")

        # 转换为标准格式
        records = []
        for item in data['data'][:periods]:
            records.append({
                'report_date': item.get('date'),
                'total_revenue': item.get('yysr'),  # 营业收入
                'operating_profit': item.get('yylr'),  # 营业利润
                'total_profit': item.get('lrze'),  # 利润总额
                'net_profit': item.get('jlr'),  # 净利润
            })

        return records

    def _fetch_balance_sheet(self, market_code: str, periods: int) -> List[Dict[str, Any]]:
        """获取资产负债表"""
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

        params = {
            'param': f'{market_code},zcfzb,,,{periods}',
            '_var': 'kline_dayzcfzb'
        }

        response = requests.get(
            url,
            params=params,
            timeout=self.timeout,
            proxies={'http': None, 'https': None}
        )

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        text = response.text
        if not text or 'kline_dayzcfzb=' not in text:
            raise Exception("响应格式错误")

        json_str = text.split('kline_dayzcfzb=')[1].strip()
        data = json.loads(json_str)

        if 'data' not in data or not data['data']:
            raise Exception("无数据返回")

        records = []
        for item in data['data'][:periods]:
            records.append({
                'report_date': item.get('date'),
                'total_assets': item.get('zzc'),  # 总资产
                'total_liabilities': item.get('fz'),  # 负债
                'total_equity': item.get('jzc'),  # 净资产
            })

        return records

    def _fetch_cashflow_statement(self, market_code: str, periods: int) -> List[Dict[str, Any]]:
        """获取现金流量表"""
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

        params = {
            'param': f'{market_code},xjllb,,,{periods}',
            '_var': 'kline_dayxjllb'
        }

        response = requests.get(
            url,
            params=params,
            timeout=self.timeout,
            proxies={'http': None, 'https': None}
        )

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        text = response.text
        if not text or 'kline_dayxjllb=' not in text:
            raise Exception("响应格式错误")

        json_str = text.split('kline_dayxjllb=')[1].strip()
        data = json.loads(json_str)

        if 'data' not in data or not data['data']:
            raise Exception("无数据返回")

        records = []
        for item in data['data'][:periods]:
            records.append({
                'report_date': item.get('date'),
                'operating_cash_flow': item.get('jyxjl'),  # 经营现金流
                'investing_cash_flow': item.get('tzxjl'),  # 投资现金流
                'financing_cash_flow': item.get('czxjl'),  # 筹资现金流
            })

        return records
