"""
测试 API 验证器
"""
import pytest
from adapters.inbound.api.validators import (
    ValidationError,
    validate_stock_symbol,
    validate_date,
    validate_date_range,
    validate_positive_int,
    validate_positive_number,
    validate_percentage,
    validate_confidence,
    validate_signal_type,
    validate_market,
    validate_strategy_name,
    validate_symbols_list,
    validate_data_source,
    validate_execution_status,
    validate_json_object,
    validate_limit_offset
)


class TestStockSymbolValidator:
    """测试股票代码验证器"""

    def test_valid_sz_stock(self):
        """测试有效的深圳股票代码"""
        assert validate_stock_symbol('000001.SZ') == '000001.SZ'
        assert validate_stock_symbol('000001.sz') == '000001.SZ'  # 自动转大写

    def test_valid_sh_stock(self):
        """测试有效的上海股票代码"""
        assert validate_stock_symbol('600000.SH') == '600000.SH'
        assert validate_stock_symbol('600000.sh') == '600000.SH'

    def test_valid_hk_stock(self):
        """测试有效的港股代码"""
        assert validate_stock_symbol('00700.HK') == '00700.HK'
        assert validate_stock_symbol('00700.hk') == '00700.HK'

    def test_valid_us_stock(self):
        """测试有效的美股代码"""
        assert validate_stock_symbol('AAPL') == 'AAPL'
        assert validate_stock_symbol('aapl') == 'AAPL'
        assert validate_stock_symbol('TSLA') == 'TSLA'

    def test_invalid_empty(self):
        """测试空代码"""
        with pytest.raises(ValidationError, match="股票代码不能为空"):
            validate_stock_symbol('')

    def test_invalid_format(self):
        """测试无效格式"""
        with pytest.raises(ValidationError, match="股票代码格式不正确"):
            validate_stock_symbol('12345')
        with pytest.raises(ValidationError, match="股票代码格式不正确"):
            validate_stock_symbol('TOOLONG')


class TestDateValidator:
    """测试日期验证器"""

    def test_valid_date(self):
        """测试有效日期"""
        assert validate_date('2024-01-01') == '2024-01-01'
        assert validate_date('2024-12-31') == '2024-12-31'

    def test_invalid_format(self):
        """测试无效格式"""
        with pytest.raises(ValidationError, match="日期格式不正确"):
            validate_date('2024/01/01')
        with pytest.raises(ValidationError, match="日期格式不正确"):
            validate_date('01-01-2024')
        with pytest.raises(ValidationError, match="日期格式不正确"):
            validate_date('invalid')

    def test_invalid_date(self):
        """测试无效日期"""
        with pytest.raises(ValidationError, match="日期格式不正确"):
            validate_date('2024-13-01')  # 月份无效
        with pytest.raises(ValidationError, match="日期格式不正确"):
            validate_date('2024-02-30')  # 日期无效

    def test_empty_date(self):
        """测试空日期"""
        with pytest.raises(ValidationError, match="日期不能为空"):
            validate_date('')


class TestDateRangeValidator:
    """测试日期范围验证器"""

    def test_valid_range(self):
        """测试有效日期范围"""
        start, end = validate_date_range('2024-01-01', '2024-12-31')
        assert start == '2024-01-01'
        assert end == '2024-12-31'

    def test_same_date(self):
        """测试相同日期"""
        start, end = validate_date_range('2024-01-01', '2024-01-01')
        assert start == end

    def test_invalid_range(self):
        """测试无效日期范围"""
        with pytest.raises(ValidationError, match="开始日期不能晚于结束日期"):
            validate_date_range('2024-12-31', '2024-01-01')


class TestPositiveIntValidator:
    """测试正整数验证器"""

    def test_valid_int(self):
        """测试有效正整数"""
        assert validate_positive_int(1) == 1
        assert validate_positive_int('10') == 10
        assert validate_positive_int(100) == 100

    def test_zero(self):
        """测试零"""
        with pytest.raises(ValidationError, match="必须是正整数"):
            validate_positive_int(0)

    def test_negative(self):
        """测试负数"""
        with pytest.raises(ValidationError, match="必须是正整数"):
            validate_positive_int(-1)

    def test_invalid_type(self):
        """测试无效类型"""
        with pytest.raises(ValidationError, match="必须是正整数"):
            validate_positive_int('abc')


class TestPositiveNumberValidator:
    """测试正数验证器"""

    def test_valid_number(self):
        """测试有效正数"""
        assert validate_positive_number(1.5) == 1.5
        assert validate_positive_number('10.5') == 10.5
        assert validate_positive_number(100) == 100.0

    def test_zero(self):
        """测试零"""
        with pytest.raises(ValidationError, match="必须是正数"):
            validate_positive_number(0)

    def test_negative(self):
        """测试负数"""
        with pytest.raises(ValidationError, match="必须是正数"):
            validate_positive_number(-1.5)


class TestPercentageValidator:
    """测试百分比验证器"""

    def test_valid_percentage(self):
        """测试有效百分比"""
        assert validate_percentage(0) == 0
        assert validate_percentage(50) == 50
        assert validate_percentage(100) == 100
        assert validate_percentage('75.5') == 75.5

    def test_out_of_range(self):
        """测试超出范围"""
        with pytest.raises(ValidationError, match="必须在 0-100 之间"):
            validate_percentage(-1)
        with pytest.raises(ValidationError, match="必须在 0-100 之间"):
            validate_percentage(101)


class TestConfidenceValidator:
    """测试置信度验证器"""

    def test_valid_confidence(self):
        """测试有效置信度"""
        assert validate_confidence(0) == 0
        assert validate_confidence(0.5) == 0.5
        assert validate_confidence(1) == 1
        assert validate_confidence('0.75') == 0.75

    def test_out_of_range(self):
        """测试超出范围"""
        with pytest.raises(ValidationError, match="置信度必须在 0-1 之间"):
            validate_confidence(-0.1)
        with pytest.raises(ValidationError, match="置信度必须在 0-1 之间"):
            validate_confidence(1.1)


class TestSignalTypeValidator:
    """测试信号类型验证器"""

    def test_valid_types(self):
        """测试有效信号类型"""
        assert validate_signal_type('buy') == 'buy'
        assert validate_signal_type('BUY') == 'buy'
        assert validate_signal_type('sell') == 'sell'
        assert validate_signal_type('hold') == 'hold'

    def test_invalid_type(self):
        """测试无效信号类型"""
        with pytest.raises(ValidationError, match="信号类型必须是以下之一"):
            validate_signal_type('invalid')


class TestMarketValidator:
    """测试市场代码验证器"""

    def test_valid_markets(self):
        """测试有效市场代码"""
        assert validate_market('SZ') == 'SZ'
        assert validate_market('sz') == 'SZ'
        assert validate_market('SH') == 'SH'
        assert validate_market('HK') == 'HK'
        assert validate_market('US') == 'US'

    def test_invalid_market(self):
        """测试无效市场代码"""
        with pytest.raises(ValidationError, match="市场代码必须是以下之一"):
            validate_market('INVALID')


class TestStrategyNameValidator:
    """测试策略名称验证器"""

    def test_valid_names(self):
        """测试有效策略名称"""
        assert validate_strategy_name('ma_cross') == 'ma_cross'
        assert validate_strategy_name('MA-Cross') == 'MA-Cross'
        assert validate_strategy_name('策略1') == '策略1'
        assert validate_strategy_name('strategy_v2') == 'strategy_v2'

    def test_empty_name(self):
        """测试空名称"""
        with pytest.raises(ValidationError, match="策略名称不能为空"):
            validate_strategy_name('')

    def test_invalid_characters(self):
        """测试无效字符"""
        with pytest.raises(ValidationError, match="只能包含"):
            validate_strategy_name('strategy@123')
        with pytest.raises(ValidationError, match="只能包含"):
            validate_strategy_name('strategy#test')

    def test_too_long(self):
        """测试名称过长"""
        with pytest.raises(ValidationError, match="长度不能超过50"):
            validate_strategy_name('a' * 51)


class TestSymbolsListValidator:
    """测试股票代码列表验证器"""

    def test_valid_list(self):
        """测试有效列表"""
        result = validate_symbols_list(['000001.SZ', '600000.SH'])
        assert result == ['000001.SZ', '600000.SH']

    def test_comma_separated_string(self):
        """测试逗号分隔字符串"""
        result = validate_symbols_list('000001.SZ,600000.SH,AAPL')
        assert result == ['000001.SZ', '600000.SH', 'AAPL']

    def test_empty_list(self):
        """测试空列表"""
        with pytest.raises(ValidationError, match="股票代码列表不能为空"):
            validate_symbols_list([])

    def test_invalid_symbol_in_list(self):
        """测试列表中包含无效代码"""
        with pytest.raises(ValidationError, match="股票代码格式不正确"):
            validate_symbols_list(['000001.SZ', 'INVALID'])


class TestDataSourceValidator:
    """测试数据源验证器"""

    def test_valid_sources(self):
        """测试有效数据源"""
        assert validate_data_source('portfolio') == 'portfolio'
        assert validate_data_source('WATCHLIST') == 'watchlist'
        assert validate_data_source('hs300') == 'hs300'
        assert validate_data_source('all') == 'all'

    def test_invalid_source(self):
        """测试无效数据源"""
        with pytest.raises(ValidationError, match="数据源必须是以下之一"):
            validate_data_source('invalid')


class TestExecutionStatusValidator:
    """测试执行状态验证器"""

    def test_valid_statuses(self):
        """测试有效执行状态"""
        assert validate_execution_status('pending') == 'pending'
        assert validate_execution_status('EXECUTED') == 'executed'
        assert validate_execution_status('closed') == 'closed'
        assert validate_execution_status('cancelled') == 'cancelled'

    def test_invalid_status(self):
        """测试无效执行状态"""
        with pytest.raises(ValidationError, match="执行状态必须是以下之一"):
            validate_execution_status('invalid')


class TestJsonObjectValidator:
    """测试JSON对象验证器"""

    def test_valid_object(self):
        """测试有效JSON对象"""
        data = {'name': 'test', 'value': 123}
        result = validate_json_object(data)
        assert result == data

    def test_with_required_fields(self):
        """测试必需字段"""
        data = {'name': 'test', 'value': 123}
        result = validate_json_object(data, required_fields=['name', 'value'])
        assert result == data

    def test_missing_required_fields(self):
        """测试缺少必需字段"""
        data = {'name': 'test'}
        with pytest.raises(ValidationError, match="缺少必需字段"):
            validate_json_object(data, required_fields=['name', 'value'])

    def test_invalid_type(self):
        """测试无效类型"""
        with pytest.raises(ValidationError, match="请求体必须是JSON对象"):
            validate_json_object([1, 2, 3])


class TestLimitOffsetValidator:
    """测试分页参数验证器"""

    def test_default_values(self):
        """测试默认值"""
        limit, offset = validate_limit_offset()
        assert limit == 100
        assert offset == 0

    def test_custom_values(self):
        """测试自定义值"""
        limit, offset = validate_limit_offset(50, 100)
        assert limit == 50
        assert offset == 100

    def test_max_limit(self):
        """测试最大限制"""
        with pytest.raises(ValidationError, match="limit 不能超过"):
            validate_limit_offset(2000, 0, max_limit=1000)

    def test_negative_offset(self):
        """测试负偏移量"""
        with pytest.raises(ValidationError, match="offset 不能为负数"):
            validate_limit_offset(100, -1)

    def test_zero_limit(self):
        """测试零限制"""
        with pytest.raises(ValidationError, match="limit 必须是正整数"):
            validate_limit_offset(0, 0)
