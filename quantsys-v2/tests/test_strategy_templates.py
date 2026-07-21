"""
测试策略模板系统 - 新增 3 种用户模板
"""
import pytest
from application.services.strategy_code_service import StrategyCodeService


class TestTrendFollowingTemplate:
    """测试趋势跟踪模板"""

    def test_validate_trend_following_template(self):
        """测试趋势跟踪模板验证通过"""
        service = StrategyCodeService()

        code = """
# 趋势跟踪策略模板
# 参数: fast=5, slow=20, atr_multiplier=2.0

# 计算均线
df['ma_fast'] = df['close'].rolling(window=5).mean()
df['ma_slow'] = df['close'].rolling(window=20).mean()

# 计算 ATR
df['atr'] = df['close'].rolling(window=14).std() * 2.0

# 买入信号：快线上穿慢线
df['buy'] = (df['ma_fast'] > df['ma_slow']) & (df['ma_fast'].shift(1) <= df['ma_slow'].shift(1))

# 卖出信号：快线下穿慢线
df['sell'] = (df['ma_fast'] < df['ma_slow']) & (df['ma_fast'].shift(1) >= df['ma_slow'].shift(1))
"""

        result = service.validate_code(code, 'trend_following')

        assert result['valid'] is True
        assert result['syntax_ok'] is True
        assert result['has_buy_signal'] is True
        assert result['has_sell_signal'] is True

    def test_trend_following_requires_buy_signal(self):
        """测试趋势跟踪模板必须有买入信号"""
        service = StrategyCodeService()

        code = """
df['ma_fast'] = df['close'].rolling(window=5).mean()
df['sell'] = df['ma_fast'] < df['close']
"""

        result = service.validate_code(code, 'trend_following')

        assert result['valid'] is False
        assert 'buy' in result['error'].lower()

    def test_trend_following_requires_sell_signal(self):
        """测试趋势跟踪模板必须有卖出信号"""
        service = StrategyCodeService()

        code = """
df['ma_fast'] = df['close'].rolling(window=5).mean()
df['buy'] = df['ma_fast'] > df['close']
"""

        result = service.validate_code(code, 'trend_following')

        assert result['valid'] is False
        assert 'sell' in result['error'].lower()


class TestMeanReversionTemplate:
    """测试均值回归模板"""

    def test_validate_mean_reversion_template(self):
        """测试均值回归模板验证通过"""
        service = StrategyCodeService()

        code = """
# 均值回归策略模板
# 参数: lookback=20, oversold=30, overbought=70

# 计算 RSI
df['rsi'] = df['close'].rolling(window=20).mean()

# 买入信号：超卖
df['buy'] = df['rsi'] < 30

# 卖出信号：超买
df['sell'] = df['rsi'] > 70
"""

        result = service.validate_code(code, 'mean_reversion')

        assert result['valid'] is True
        assert result['syntax_ok'] is True
        assert result['has_buy_signal'] is True
        assert result['has_sell_signal'] is True

    def test_mean_reversion_requires_buy_signal(self):
        """测试均值回归模板必须有买入信号"""
        service = StrategyCodeService()

        code = """
df['rsi'] = df['close'].rolling(window=20).mean()
df['sell'] = df['rsi'] > 70
"""

        result = service.validate_code(code, 'mean_reversion')

        assert result['valid'] is False
        assert 'buy' in result['error'].lower()


class TestMultiFactorTemplate:
    """测试多因子模板"""

    def test_validate_multi_factor_template(self):
        """测试多因子模板验证通过"""
        service = StrategyCodeService()

        code = """
# 多因子策略模板
# 参数: factors=['momentum', 'value'], weights=[0.6, 0.4], threshold=0.7

# 计算动量因子
df['momentum'] = df['close'].pct_change(20)

# 计算价值因子
df['value'] = 1 / df['close']

# 综合评分
df['score'] = df['momentum'] * 0.6 + df['value'] * 0.4

# 买入信号：评分超过阈值
df['buy'] = df['score'] > 0.7

# 卖出信号：评分低于阈值
df['sell'] = df['score'] < 0.3
"""

        result = service.validate_code(code, 'multi_factor')

        assert result['valid'] is True
        assert result['syntax_ok'] is True
        assert result['has_buy_signal'] is True
        assert result['has_sell_signal'] is True

    def test_multi_factor_requires_buy_signal(self):
        """测试多因子模板必须有买入信号"""
        service = StrategyCodeService()

        code = """
df['score'] = df['close'].pct_change(20)
df['sell'] = df['score'] < 0.3
"""

        result = service.validate_code(code, 'multi_factor')

        assert result['valid'] is False
        assert 'buy' in result['error'].lower()


class TestStrategyCodeTypeValidation:
    """测试策略类型验证"""

    def test_create_strategy_with_trend_following_type(self):
        """测试创建趋势跟踪类型策略"""
        service = StrategyCodeService()

        code = """
df['ma_fast'] = df['close'].rolling(window=5).mean()
df['ma_slow'] = df['close'].rolling(window=20).mean()
df['buy'] = df['ma_fast'] > df['ma_slow']
df['sell'] = df['ma_fast'] < df['ma_slow']
"""

        import time
        unique_name = f'测试趋势策略_{int(time.time() * 1000)}'

        result = service.create_strategy(
            name=unique_name,
            code=code,
            code_type='trend_following'
        )

        assert result['strategy_id'] is not None
        assert result['code_type'] == 'trend_following'
        assert result['validation']['valid'] is True

    def test_create_strategy_with_mean_reversion_type(self):
        """测试创建均值回归类型策略"""
        service = StrategyCodeService()

        code = """
df['rsi'] = df['close'].rolling(window=14).mean()
df['buy'] = df['rsi'] < 30
df['sell'] = df['rsi'] > 70
"""

        import time
        unique_name = f'测试均值回归策略_{int(time.time() * 1000)}'

        result = service.create_strategy(
            name=unique_name,
            code=code,
            code_type='mean_reversion'
        )

        assert result['strategy_id'] is not None
        assert result['code_type'] == 'mean_reversion'
        assert result['validation']['valid'] is True

    def test_create_strategy_with_multi_factor_type(self):
        """测试创建多因子类型策略"""
        service = StrategyCodeService()

        code = """
df['factor1'] = df['close'].pct_change(20)
df['factor2'] = df['volume'].pct_change(20)
df['score'] = df['factor1'] * 0.6 + df['factor2'] * 0.4
df['buy'] = df['score'] > 0.5
df['sell'] = df['score'] < 0.2
"""

        import time
        unique_name = f'测试多因子策略_{int(time.time() * 1000)}'

        result = service.create_strategy(
            name=unique_name,
            code=code,
            code_type='multi_factor'
        )

        assert result['strategy_id'] is not None
        assert result['code_type'] == 'multi_factor'
        assert result['validation']['valid'] is True

    def test_reject_invalid_code_type(self):
        """测试拒绝无效的策略类型"""
        service = StrategyCodeService()

        code = "df['buy'] = True"

        with pytest.raises(ValueError) as exc_info:
            service.create_strategy(
                name='测试策略',
                code=code,
                code_type='invalid_type'
            )

        assert 'invalid_type' in str(exc_info.value).lower()
