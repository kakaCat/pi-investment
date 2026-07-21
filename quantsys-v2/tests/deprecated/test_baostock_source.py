"""baostock 数据源单元测试
"""
import pytest
from adapters.outbound.datasources.baostock_source import BaostockSource, BAOSTOCK_AVAILABLE


class TestBaostockSource:
    """测试 baostock 数据源"""

    @pytest.fixture
    def source(self):
        """创建数据源实例"""
        return BaostockSource()

    def test_init(self, source):
        """测试初始化"""
        assert source.name == "baostock"
        assert source.requires_api_key is False

    def test_validate_config(self, source):
        """测试配置验证"""
        result = source.validate_config()
        assert result == BAOSTOCK_AVAILABLE

    def test_symbol_conversion_to_bs(self, source):
        """测试符号转换为 baostock 格式"""
        assert source._convert_symbol_to_bs("600000.SH") == "sh.600000"
        assert source._convert_symbol_to_bs("000001.SZ") == "sz.000001"
        assert source._convert_symbol_to_bs("300059.SZ") == "sz.300059"

    def test_symbol_conversion_from_bs(self, source):
        """测试符号转换从 baostock 格式"""
        assert source._convert_symbol_from_bs("sh.600000") == "600000.SH"
        assert source._convert_symbol_from_bs("sz.000001") == "000001.SZ"
        assert source._convert_symbol_from_bs("sz.300059") == "300059.SZ"

    def test_connection(self, source):
        """测试连接"""
        if not BAOSTOCK_AVAILABLE:
            pytest.skip("baostock not available")

        response = source.test_connection()
        assert response.success is True
        assert response.metadata.get("source") == "baostock"

    def test_get_stock_info(self, source):
        """测试获取股票信息"""
        if not BAOSTOCK_AVAILABLE:
            pytest.skip("baostock not available")

        response = source.get_stock_info("600000.SH")
        assert response.success is True
        assert response.data is not None
        assert response.data.get("symbol") == "600000.SH"
        assert "name" in response.data
        assert response.metadata.get("source") == "baostock"

    def test_get_klines(self, source):
        """测试获取K线数据"""
        if not BAOSTOCK_AVAILABLE:
            pytest.skip("baostock not available")

        # 使用更早的日期（baostock 数据延迟）
        response = source.get_klines(
            symbol="600000.SH",
            period="daily",
            start_date="2023-01-01",
            end_date="2023-01-31"
        )

        assert response.success is True
        assert isinstance(response.data, list)
        assert len(response.data) > 0

        # 验证数据格式
        kline = response.data[0]
        assert "symbol" in kline
        assert "trade_date" in kline
        assert "open" in kline
        assert "high" in kline
        assert "low" in kline
        assert "close" in kline
        assert "volume" in kline

        assert response.metadata.get("source") == "baostock"

    def test_get_klines_date_format(self, source):
        """测试K线数据的日期格式处理"""
        if not BAOSTOCK_AVAILABLE:
            pytest.skip("baostock not available")

        # 测试带连字符的日期格式（使用更早的日期）
        response = source.get_klines(
            symbol="600000.SH",
            start_date="2023-01-01",
            end_date="2023-01-05"
        )
        assert response.success is True

        # 测试不带连字符的日期格式
        response2 = source.get_klines(
            symbol="600000.SH",
            start_date="20230101",
            end_date="20230105"
        )
        assert response2.success is True

    def test_get_realtime_quote_not_supported(self, source):
        """测试实时行情（不支持）"""
        response = source.get_realtime_quote(["600000.SH"])
        assert response.success is False
        assert "not support" in response.error.lower()

    def test_search_stocks(self, source):
        """测试搜索股票"""
        if not BAOSTOCK_AVAILABLE:
            pytest.skip("baostock not available")

        # 搜索浦发银行
        response = source.search_stocks("浦发")
        assert response.success is True
        assert len(response.data) > 0

        # 验证包含浦发银行
        found = any("浦发" in stock.get("name", "") for stock in response.data)
        assert found is True

    def test_search_stocks_by_code(self, source):
        """测试按代码搜索股票"""
        if not BAOSTOCK_AVAILABLE:
            pytest.skip("baostock not available")

        response = source.search_stocks("600000")
        assert response.success is True
        assert len(response.data) > 0

        # 应该包含 600000
        found = any("600000" in stock.get("symbol", "") for stock in response.data)
        assert found is True

    def test_baostock_unavailable(self):
        """测试 baostock 不可用时的行为"""
        if BAOSTOCK_AVAILABLE:
            pytest.skip("baostock is available, cannot test unavailable scenario")

        source = BaostockSource()
        assert source.validate_config() is False

        # 所有操作应该失败
        response = source.test_connection()
        assert response.success is False

    def test_invalid_symbol(self, source):
        """测试无效的股票代码"""
        if not BAOSTOCK_AVAILABLE:
            pytest.skip("baostock not available")

        response = source.get_stock_info("INVALID123")
        # 应该返回错误或空数据
        assert response.success is False or response.data is None

    def test_different_periods(self, source):
        """测试不同周期的K线数据"""
        if not BAOSTOCK_AVAILABLE:
            pytest.skip("baostock not available")

        periods = ['daily', 'weekly', 'monthly']
        for period in periods:
            response = source.get_klines(
                symbol="600000.SH",
                period=period,
                start_date="2023-01-01",
                end_date="2023-03-31"
            )
            assert response.success is True
            assert response.metadata.get("period") == period

    def test_adjust_flag(self, source):
        """测试不同复权类型"""
        if not BAOSTOCK_AVAILABLE:
            pytest.skip("baostock not available")

        adjust_flags = ['1', '2', '3']  # 后复权、前复权、不复权
        for flag in adjust_flags:
            response = source.get_klines(
                symbol="600000.SH",
                start_date="2023-01-01",
                end_date="2023-01-31",
                adjust_flag=flag
            )
            assert response.success is True
            assert response.metadata.get("adjust_flag") == flag
