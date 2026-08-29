"""
新浪财经网页爬虫数据提供者

通过解析新浪财经网页获取财务数据，不需要 token。
"""
import structlog
logger = structlog.get_logger(__name__)
import logging
from datetime import datetime
from typing import Dict, Any
import requests
from bs4 import BeautifulSoup
import re
from .base import FinancialProvider, FinancialData

logger = logging.getLogger(__name__)


class SinaWebFinancialProvider(FinancialProvider):
    """新浪财经网页爬虫数据提供者"""

    def __init__(self, timeout: int = 10):
        super().__init__(name="sina_web", timeout=timeout)

    def get_financial_data(
        self,
        symbol: str,
        statement_type: str = 'all',
        periods: int = 4
    ) -> FinancialData:
        """通过新浪财经网页获取财务数据

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

            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }

            # 获取利润表
            if statement_type in ('income', 'all'):
                try:
                    url = f"https://money.finance.sina.com.cn/corp/go.php/vFD_ProfitStatement/stockid/{short_code}/ctrl/part/displaytype/4.phtml"
                    resp = requests.get(url, headers=headers, timeout=self.timeout)

                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.content, 'lxml')
                        table = soup.find('table', {'id': 'ProfitStatementNewTable0'})

                        if table:
                            data = self._parse_sina_table(table, periods)
                            if data:
                                result.income_statement = data
                                logger.debug(f"[{self.name}] 成功获取 {standard_symbol} 利润表")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取利润表失败 {standard_symbol}: {e}")
                    if statement_type == 'income':
                        raise Exception(f"利润表获取失败: {e}") from e

            # 获取资产负债表
            if statement_type in ('balance', 'all'):
                try:
                    url = f"https://money.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/{short_code}/ctrl/part/displaytype/4.phtml"
                    resp = requests.get(url, headers=headers, timeout=self.timeout)

                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.content, 'lxml')
                        table = soup.find('table', {'id': 'BalanceSheetNewTable0'})

                        if table:
                            data = self._parse_sina_table(table, periods)
                            if data:
                                result.balance_sheet = data
                                logger.debug(f"[{self.name}] 成功获取 {standard_symbol} 资产负债表")
                except Exception as e:
                    logger.warning(f"[{self.name}] 获取资产负债表失败 {standard_symbol}: {e}")
                    if statement_type == 'balance':
                        raise Exception(f"资产负债表获取失败: {e}") from e

            # 获取现金流量表
            if statement_type in ('cash_flow', 'cashflow', 'all'):
                try:
                    url = f"https://money.finance.sina.com.cn/corp/go.php/vFD_CashFlow/stockid/{short_code}/ctrl/part/displaytype/4.phtml"
                    resp = requests.get(url, headers=headers, timeout=self.timeout)

                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.content, 'lxml')
                        table = soup.find('table', {'id': 'CashFlowNewTable0'})

                        if table:
                            data = self._parse_sina_table(table, periods)
                            if data:
                                result.cash_flow = data
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
            raise Exception(f"新浪财经网页查询失败: {e}") from e

    def _parse_sina_table(self, table, periods: int):
        """解析新浪财经表格

        Args:
            table: BeautifulSoup table 对象
            periods: 返回期数

        Returns:
            财务数据列表
        """
        try:
            rows = table.find_all('tr')
            if len(rows) < 3:
                return None

            # 新浪表格结构:
            # 第0行: 标题行（如"贵州茅台(600519)  利润表单位：万元"）
            # 第1行: 日期行（"报表日期", "2026-03-31", "2025-12-31", ...）
            # 第2行: 空行
            # 第3行+: 数据行

            # 找到日期行（包含"报表日期"的那行）
            date_row = None
            date_row_index = 0
            for i, row in enumerate(rows[:5]):
                cols = row.find_all('td')
                if cols and len(cols) > 1:
                    first_col_text = cols[0].get_text().strip()
                    if '报表日期' in first_col_text or first_col_text == '报表日期':
                        date_row = row
                        date_row_index = i
                        break

            if not date_row:
                logger.warning("未找到日期行")
                return None

            # 解析日期列
            date_cols = date_row.find_all('td')
            date_columns = [col.get_text().strip() for col in date_cols[1:periods+1]]

            if not date_columns:
                logger.warning("未找到日期列")
                return None

            # 初始化结果
            result = [{} for _ in date_columns]
            for i, date in enumerate(date_columns):
                result[i]['报告日'] = date

            # 解析数据行（从日期行之后开始）
            for row in rows[date_row_index+1:]:
                cols = row.find_all('td')
                if len(cols) < 2:
                    continue

                # 第一列是指标名称
                indicator = cols[0].get_text().strip()

                # 跳过空行或无效行
                if not indicator or indicator == '':
                    continue

                # 其他列是数据
                for i, col in enumerate(cols[1:len(date_columns)+1]):
                    if i < len(result):
                        value_text = col.get_text().strip()
                        # 转换为数值（处理逗号、--等）
                        value = self._parse_value(value_text)
                        result[i][indicator] = value

            return result if result and len(result[0]) > 1 else None

        except Exception as e:
            logger.error(f"解析新浪表格失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_value(self, text: str):
        """解析数值文本

        Args:
            text: 文本值

        Returns:
            数值或 None
        """
        if not text or text in ['--', '-', '']:
            return None

        # 移除逗号
        text = text.replace(',', '')

        try:
            return float(text)
        except Exception:
            logger.debug("unexpected exception in module", exc_info=True)
            return text
