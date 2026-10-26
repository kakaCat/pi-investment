"""财务指标链路回归测试（data_fetch_financial dataType=indicators）。

2026-10-19 故障：FinancialStatementData 缺 timestamp 字段，而调用方
FinancialAnalysisService.get_financial_indicators 按旧 FinancialDataService 契约
写的是 `financial_data.timestamp.isoformat()`。数据其实已从 akshare 成功取回，
却在组装返回值时抛 AttributeError，被上层 except 吞掉、再落到未注册的 DB fallback，
最终对外统一报「所有数据源均不可用」——与个股无关，是全局故障。

本测试锁两件事：
1. 适配器返回值必须带 timestamp（契约字段不能少）；
2. 报表行是中文键时，指标仍能算全（英文键/中文键映射不能只覆盖一半）。
"""
import logging
from datetime import datetime

import pytest

from qs_market_data.application.services.financial_analysis_service import (
    FinancialAnalysisService,
)
from qs_market_data.application.services.financial_data_service_adapter import (
    FinancialDataServiceAdapter,
    FinancialStatementData,
)

# 数据源（akshare / 东财）真实报表行的键形态：中文键、无 total_revenue/total_equity
INCOME_ROW = {
    '报告日': '2026-06-30',
    '营业总收入': 1000.0,
    '营业收入': 1000.0,
    '营业成本': 700.0,
    '营业利润': 200.0,
    '净利润': 150.0,
    '归属于母公司所有者的净利润': 120.0,
}
BALANCE_ROW = {
    '报告日': '2026-06-30',
    '资产总计': 5000.0,
    '负债合计': 2000.0,
    '流动资产合计': 3000.0,
    '流动负债合计': 1000.0,
    '所有者权益(或股东权益)合计': 3000.0,
}


def _service_without_provider_init() -> FinancialAnalysisService:
    """绕开 __init__ 里的 provider manager 初始化，保持测试离线。"""
    service = object.__new__(FinancialAnalysisService)
    service.logger = logging.getLogger(__name__)
    service._financial_repo = None
    service._kline_repo = None
    return service


def test_adapter_result_exposes_timestamp():
    data = FinancialStatementData(symbol='688981')
    assert hasattr(data, 'timestamp'), 'FinancialStatementData 必须保留 timestamp 契约字段'
    assert isinstance(data.timestamp, datetime)


def test_indicators_computed_from_chinese_statement_keys(monkeypatch):
    def fake_get_financial_data(self, symbol, statement_type='all', periods=4):
        return FinancialStatementData(
            symbol=symbol,
            statement_type=statement_type,
            periods=periods,
            income_statement=[INCOME_ROW],
            balance_sheet=[BALANCE_ROW],
            cash_flow=[],
            source='fake-source',
        )

    monkeypatch.setattr(
        FinancialDataServiceAdapter, 'get_financial_data', fake_get_financial_data
    )

    result = _service_without_provider_init().get_financial_indicators('688981')

    assert result['success'] is True
    data = result['data']
    assert data['source'] == 'fake-source'
    # timestamp 缺失时这里会抛 AttributeError，整个成功分支被吞成「所有数据源均不可用」
    assert isinstance(data['update_time'], str) and data['update_time']

    indicators = data['indicators']
    assert indicators['roe'] == pytest.approx(5.0)             # 150 / 3000
    assert indicators['net_profit_margin'] == pytest.approx(15.0)   # 150 / 1000
    assert indicators['gross_margin'] == pytest.approx(30.0)        # (1000-700)/1000
    assert indicators['operating_margin'] == pytest.approx(20.0)    # 200 / 1000
    assert indicators['roa'] == pytest.approx(3.0)                  # 150 / 5000
    assert indicators['debt_ratio'] == pytest.approx(40.0)          # 2000 / 5000
    assert indicators['current_ratio'] == pytest.approx(3.0)        # 3000 / 1000

    assert len(data['income_statements']) == 1
    assert len(data['balance_sheets']) == 1
