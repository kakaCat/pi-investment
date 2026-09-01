"""测试 _inject_fund_flow_to_klines 从 DB 读取资金流数据"""
import pytest
from adapters.shared.fund_flow_helpers import (
    _inject_fund_flow_to_klines,
    _extract_fund_flow_factors,
    _DB_TO_FACTOR_MAP,
)


class TestInjectFundFlowToKlines:
    """测试资金流注入函数"""

    def test_inject_adds_factor_columns(self):
        """注入后 klines 应包含所有 factor 列"""
        klines = [
            {"trade_date": "2026-08-28", "close": 100.0},
            {"trade_date": "2026-08-29", "close": 101.0},
            {"trade_date": "2026-08-31", "close": 102.0},
        ]
        result = _inject_fund_flow_to_klines(klines, "600519")
        for alias in _DB_TO_FACTOR_MAP.values():
            assert alias in result[0], f"Missing factor column: {alias}"

    def test_inject_preserves_existing_columns(self):
        """注入不破坏原有 kline 字段"""
        klines = [{"trade_date": "2026-08-31", "close": 100.0, "volume": 50000}]
        result = _inject_fund_flow_to_klines(klines, "600519")
        assert result[0]["close"] == 100.0
        assert result[0]["volume"] == 50000

    def test_inject_empty_klines(self):
        """空 klines 不报错"""
        result = _inject_fund_flow_to_klines([], "600519")
        assert result == []

    def test_inject_unknown_symbol_returns_zeros(self):
        """未知股票代码返回全零"""
        klines = [{"trade_date": "2026-08-31", "close": 100.0}]
        result = _inject_fund_flow_to_klines(klines, "XXXXXX")
        assert result[0]["main_net_inflow"] == 0.0
        assert result[0]["super_large_net"] == 0.0

    def test_inject_with_dot_suffix(self):
        """带 .SH/.SZ 后缀的 symbol 能正确处理"""
        klines = [{"trade_date": "2026-08-31", "close": 100.0}]
        result = _inject_fund_flow_to_klines(klines, "600519.SH")
        assert "main_net_inflow" in result[0]

    def test_inject_real_data_nonzero(self):
        """600519 在 2026-08-31 有实际资金流数据，注入后非零"""
        klines = [
            {"trade_date": "2026-08-28", "close": 1300.0},
            {"trade_date": "2026-08-29", "close": 1310.0},
            {"trade_date": "2026-08-31", "close": 1290.0},
        ]
        result = _inject_fund_flow_to_klines(klines, "600519")
        last = result[-1]
        assert last["main_net_inflow"] != 0.0, "main_net_inflow should be non-zero for 600519"
        assert last["super_large_net"] != 0.0, "super_large_net should be non-zero for 600519"


class TestExtractFundFlowFactors:
    """测试资金流因子提取"""

    def test_extract_returns_expected_keys(self):
        """提取结果包含所有预期因子名"""
        klines = [{"trade_date": "2026-08-31", "main_net_inflow": -100.0,
                   "main_net_pct": -0.5, "super_large_net": -50.0,
                   "large_net": -30.0, "super_large_pct": -0.2, "large_pct": -0.1}]
        factors = _extract_fund_flow_factors(klines)
        expected = {
            "main_net_inflow", "main_net_pct", "super_large_net", "large_net",
            "super_large_pct", "large_pct", "fund_inflow_3d_sum", "fund_inflow_5d_sum",
            "fund_inflow_pos_days_3", "fund_inflow_pos_days_5",
        }
        assert expected == set(factors.keys())

    def test_extract_3d_sum(self):
        """3日累计 = 最后3条 main_net_inflow 之和"""
        klines = [
            {"trade_date": "2026-08-27", "main_net_inflow": 100.0, **{k: 0 for k in ["main_net_pct", "super_large_net", "large_net", "super_large_pct", "large_pct"]}},
            {"trade_date": "2026-08-28", "main_net_inflow": 200.0, **{k: 0 for k in ["main_net_pct", "super_large_net", "large_net", "super_large_pct", "large_pct"]}},
            {"trade_date": "2026-08-31", "main_net_inflow": 300.0, **{k: 0 for k in ["main_net_pct", "super_large_net", "large_net", "super_large_pct", "large_pct"]}},
        ]
        factors = _extract_fund_flow_factors(klines)
        assert factors["fund_inflow_3d_sum"] == 600.0

    def test_extract_5d_sum_fewer_than_5(self):
        """不足5日时取全部"""
        klines = [
            {"trade_date": "2026-08-30", "main_net_inflow": 100.0, **{k: 0 for k in ["main_net_pct", "super_large_net", "large_net", "super_large_pct", "large_pct"]}},
            {"trade_date": "2026-08-31", "main_net_inflow": 200.0, **{k: 0 for k in ["main_net_pct", "super_large_net", "large_net", "super_large_pct", "large_pct"]}},
        ]
        factors = _extract_fund_flow_factors(klines)
        assert factors["fund_inflow_5d_sum"] == 300.0

    def test_extract_pos_days(self):
        """正流入天数统计正确"""
        klines = [
            {"trade_date": "2026-08-27", "main_net_inflow": 100.0, **{k: 0 for k in ["main_net_pct", "super_large_net", "large_net", "super_large_pct", "large_pct"]}},
            {"trade_date": "2026-08-28", "main_net_inflow": -50.0, **{k: 0 for k in ["main_net_pct", "super_large_net", "large_net", "super_large_pct", "large_pct"]}},
            {"trade_date": "2026-08-31", "main_net_inflow": 200.0, **{k: 0 for k in ["main_net_pct", "super_large_net", "large_net", "super_large_pct", "large_pct"]}},
        ]
        factors = _extract_fund_flow_factors(klines)
        assert factors["fund_inflow_pos_days_3"] == 2
        assert factors["fund_inflow_pos_days_5"] == 2

    def test_extract_empty_klines(self):
        """空 klines 返回空 dict"""
        assert _extract_fund_flow_factors([]) == {}
