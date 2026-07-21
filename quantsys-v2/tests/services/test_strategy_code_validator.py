"""
策略代码验证器单元测试
"""

import pytest
from application.services.strategy_code_validator import StrategyCodeValidator


class TestStrategyCodeValidator:
    """测试策略代码验证器"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.validator = StrategyCodeValidator()

    def test_validate_indicator_code_success(self):
        """测试验证有效的Indicator代码"""
        code = """
my_indicator_name = "测试策略"
my_indicator_description = "这是一个测试策略"

def calc_indicator(ctx):
    df = ctx.kline_df
    df['buy'] = df['rsi14'] < 30
    df['sell'] = df['rsi14'] > 70
    return df
"""
        result = self.validator.validate_code(code, 'indicator')

        assert result['valid'] is True
        assert result['syntax_ok'] is True
        assert result['has_buy_signal'] is True
        assert result['has_sell_signal'] is True
        assert result['metadata']['name'] == "测试策略"

    def test_validate_indicator_code_missing_function(self):
        """测试缺少必需函数的Indicator代码"""
        code = """
my_indicator_name = "测试策略"
# 缺少 calc_indicator 函数
"""
        result = self.validator.validate_code(code, 'indicator')

        # 验证器不会抛出异常，而是返回错误结果
        assert result['valid'] is False
        assert 'error' in result
        assert 'calc_indicator' in result['error']

    def test_validate_indicator_code_missing_signals(self):
        """测试缺少买卖信号的Indicator代码"""
        code = """
def calc_indicator(ctx):
    df = ctx.kline_df
    # 这里没有生成买卖信号
    return df
"""
        result = self.validator.validate_code(code, 'indicator')

        assert result['valid'] is True
        assert result['has_buy_signal'] is False
        assert result['has_sell_signal'] is False

    def test_validate_script_code_success(self):
        """测试验证有效的Script代码"""
        code = """
strategy_name = "测试Script策略"

def on_init(ctx):
    ctx.ma_period = 20

def on_bar(ctx, bar):
    if bar.close > ctx.ma20:
        ctx.buy(100)
    elif bar.close < ctx.ma20:
        ctx.sell(100)
"""
        result = self.validator.validate_code(code, 'script')

        assert result['valid'] is True
        assert result['syntax_ok'] is True
        assert result['has_on_init'] is True
        assert result['has_on_bar'] is True

    def test_validate_script_code_missing_on_init(self):
        """测试缺少on_init的Script代码"""
        code = """
def on_bar(ctx, bar):
    pass
"""
        result = self.validator.validate_code(code, 'script')

        assert result['valid'] is False
        assert 'error' in result
        assert 'on_init' in result['error']

    def test_validate_script_code_missing_on_bar(self):
        """测试缺少on_bar的Script代码"""
        code = """
def on_init(ctx):
    pass
"""
        result = self.validator.validate_code(code, 'script')

        assert result['valid'] is False
        assert 'error' in result
        assert 'on_bar' in result['error']

    def test_validate_template_code(self):
        """测试验证模板策略代码"""
        code = """
def calc_indicator(ctx):
    df = ctx.kline_df
    df['buy'] = True
    df['sell'] = False
    return df
"""
        result = self.validator.validate_code(code, 'trend_following')

        assert result['valid'] is True
        assert result['has_buy_signal'] is True
        assert result['has_sell_signal'] is True
        assert result['metadata']['template_type'] == 'trend_following'

    def test_validate_invalid_code_type(self):
        """测试无效的代码类型"""
        code = "pass"
        result = self.validator.validate_code(code, 'invalid_type')

        assert result['valid'] is False
        assert 'error' in result
        assert '不支持的策略类型' in result['error']

    def test_validate_syntax_error(self):
        """测试语法错误的代码"""
        code = """
def calc_indicator(ctx)
    # 缺少冒号，语法错误
    df = ctx.kline_df
    return df
"""
        result = self.validator.validate_code(code, 'indicator')

        assert result['valid'] is False
        assert result['syntax_ok'] is False
        assert 'error' in result
