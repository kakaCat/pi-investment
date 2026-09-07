"""
财务数据源基础接口
"""
from abc import ABC
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass


@dataclass
class FinancialStatementData:
    """财务报表数据模型（用于存储完整的财务报表）

    Attributes:
        symbol: 股票代码
        name: 股票名称
        statement_type: 报表类型 (income/balance/cash_flow/all)
        periods: 期数
        income_statement: 利润表数据列表
        balance_sheet: 资产负债表数据列表
        cash_flow: 现金流量表数据列表
        source: 数据源名称
        timestamp: 查询时间戳
    """
    symbol: str
    name: str
    source: str
    timestamp: Any
    statement_type: str = 'all'
    periods: int = 4
    income_statement: Optional[List[Dict[str, Any]]] = None
    balance_sheet: Optional[List[Dict[str, Any]]] = None
    cash_flow: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self):
        """验证数据有效性"""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol cannot be empty")


@dataclass
class FinancialIndicators:
    """财务指标数据模型

    Attributes:
        symbol: 股票代码
        name: 股票名称
        roe: 净资产收益率 (%)
        net_profit: 净利润（元）
        revenue: 营业收入（元）
        gross_margin: 毛利率 (%)
        net_margin: 净利率 (%)
        debt_ratio: 资产负债率 (%)
        current_ratio: 流动比率
        quick_ratio: 速动比率
        report_date: 报告期（如 2024-12-31）
        source: 数据源名称
        timestamp: 查询时间戳（ISO 8601 格式）
        raw_data: 原始数据（可选）
    """
    symbol: str
    name: str
    source: str
    timestamp: str
    report_date: Optional[str] = None
    roe: Optional[float] = None
    net_profit: Optional[float] = None
    revenue: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    raw_data: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """验证数据有效性"""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol cannot be empty")


@dataclass
class ValuationData:
    """估值数据模型

    Attributes:
        symbol: 股票代码
        name: 股票名称
        current_price: 当前价格
        pe: 市盈率
        pb: 市净率
        ps: 市销率
        dividend_yield: 股息率 (%)
        market_cap: 总市值（元）
        source: 数据源名称
        timestamp: 查询时间戳（ISO 8601 格式）
    """
    symbol: str
    name: str
    source: str
    timestamp: str
    current_price: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None

    def __post_init__(self):
        """验证数据有效性"""
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol cannot be empty")


class FinancialDataProvider(ABC):
    """财务数据源接口"""

    def __init__(self, name: str = "unknown", timeout: int = 10):
        self._name = name
        self.timeout = timeout
        self.retry_count = 1

    def get_financial_indicators(self, symbol: str) -> Optional[FinancialIndicators]:
        """
        获取财务指标（默认实现返回 None，子类选择性覆盖）

        Args:
            symbol: 股票代码（6位数字）

        Returns:
            FinancialIndicators 或 None（失败时）
        """
        return None

    def get_valuation(self, symbol: str) -> Optional[ValuationData]:
        """
        获取估值数据（默认实现返回 None，子类选择性覆盖）

        Args:
            symbol: 股票代码（6位数字）

        Returns:
            ValuationData 或 None（失败时）
        """
        return None

    @property
    def name(self) -> str:
        """数据源名称"""
        return self._name

    def _normalize_symbol(self, symbol: str) -> Tuple[str, str]:
        """标准化股票代码，返回 (标准代码, 简码)

        Args:
            symbol: 原始股票代码（如 600519.SH 或 600519）

        Returns:
            (标准代码, 简码) 如 ('600519.SH', '600519')
        """
        clean = symbol.split('.')[0].strip()

        # 判断市场
        if clean.startswith('6'):
            standard = f"{clean}.SH"
        elif clean.startswith(('0', '3')):
            standard = f"{clean}.SZ"
        else:
            standard = clean

        return (standard, clean)


# Backward compatibility aliases
FinancialProvider = FinancialDataProvider
FinancialData = FinancialStatementData  # 指向新的数据类
