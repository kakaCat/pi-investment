"""
策略数据提供服务单元测试
"""

import pytest
import polars as pl
from datetime import date
from application.services.strategy_data_provider import StrategyDataProvider


class TestStrategyDataProvider:
    """测试策略数据提供服务"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.provider = StrategyDataProvider()

    def test_normalize_date_from_string(self):
        """测试从字符串归一化日期"""
        date_str = "2025-01-15 10:30:00"
        result = self.provider.normalize_date(date_str)

        assert result == "20250115"

    def test_normalize_date_from_date_object(self):
        """测试从日期对象归一化"""
        date_obj = date(2025, 1, 15)
        result = self.provider.normalize_date(date_obj)

        assert result == "2025-01-15"

    def test_aggregate_minute_klines_5min(self):
        """测试5分钟K线聚合"""
        # 模拟1分钟K线数据（生产实现收 polars DataFrame，与 get_minute_klines 返回类型一致）
        klines = pl.DataFrame([
            {'trade_date': '2025-01-01 09:30:00', 'open': 10.0, 'high': 10.2, 'low': 9.9, 'close': 10.1, 'volume': 1000},
            {'trade_date': '2025-01-01 09:31:00', 'open': 10.1, 'high': 10.3, 'low': 10.0, 'close': 10.2, 'volume': 1200},
            {'trade_date': '2025-01-01 09:32:00', 'open': 10.2, 'high': 10.4, 'low': 10.1, 'close': 10.3, 'volume': 1100},
            {'trade_date': '2025-01-01 09:33:00', 'open': 10.3, 'high': 10.5, 'low': 10.2, 'close': 10.4, 'volume': 1300},
            {'trade_date': '2025-01-01 09:34:00', 'open': 10.4, 'high': 10.6, 'low': 10.3, 'close': 10.5, 'volume': 1400},
        ])

        result = self.provider.aggregate_minute_klines(klines, '5min')

        # 5条1分钟K线应该聚合成1条5分钟K线
        assert len(result) == 1
        assert result[0]['open'] == 10.0  # 第一条的开盘价
        assert result[0]['high'] == 10.6  # 最高价
        assert result[0]['low'] == 9.9    # 最低价
        assert result[0]['close'] == 10.5 # 最后一条的收盘价
        assert result[0]['volume'] == 6000 # 成交量求和

    def test_aggregate_minute_klines_empty(self):
        """测试空K线聚合"""
        klines = pl.DataFrame()

        result = self.provider.aggregate_minute_klines(klines, '5min')

        assert result == []

    def test_aggregate_minute_klines_unsupported_period(self):
        """测试不支持的周期"""
        klines = pl.DataFrame([{'trade_date': '2025-01-01 09:30:00', 'open': 10.0, 'high': 10.2, 'low': 9.9, 'close': 10.1, 'volume': 1000}])

        with pytest.raises(ValueError, match="不支持的周期"):
            self.provider.aggregate_minute_klines(klines, '2min')

    def test_inject_fund_flow_initialization(self):
        """测试资金流数据初始化"""
        klines = [
            {'trade_date': '2025-01-01', 'open': 10.0, 'high': 10.5, 'low': 9.8, 'close': 10.2, 'volume': 1000000},
            {'trade_date': '2025-01-02', 'open': 10.2, 'high': 10.8, 'low': 10.0, 'close': 10.5, 'volume': 1200000},
        ]

        result = self.provider.inject_fund_flow(klines, '600519')

        # 验证资金流列已初始化
        assert 'main_net_inflow' in result[0]
        assert 'main_net_pct' in result[0]
        assert 'super_large_net' in result[0]
        assert 'super_large_pct' in result[0]
        assert 'large_net' in result[0]
        assert 'large_pct' in result[0]

    def test_inject_financial_initialization(self):
        """测试财务数据初始化"""
        klines = [
            {'trade_date': '2025-01-01', 'open': 10.0, 'high': 10.5, 'low': 9.8, 'close': 10.2, 'volume': 1000000},
        ]

        result = self.provider.inject_financial(klines, '600519')

        # 验证财务列已初始化
        assert 'roe_q' in result[0]
        assert 'gross_margin_q' in result[0]
        assert 'debt_ratio_q' in result[0]

    def test_inject_market_filter_disabled(self):
        """测试禁用市场过滤器"""
        klines = [
            {'trade_date': '2025-01-01', 'open': 10.0, 'high': 10.5, 'low': 9.8, 'close': 10.2, 'volume': 1000000},
        ]

        result = self.provider.inject_market_filter(klines, bear_filter_enabled=False)

        # 验证市场过滤器列已初始化（但值为默认值）
        assert 'csi300_close' in result[0]
        assert 'csi300_ma200' in result[0]
        assert 'market_bear' in result[0]
        assert result[0]['market_bear'] is False

    def test_get_klines_validation(self):
        """测试K线获取参数验证"""
        # 既不提供日期范围也不提供limit，应该抛出异常
        with pytest.raises(ValueError, match="必须指定"):
            self.provider.get_klines('600519')
