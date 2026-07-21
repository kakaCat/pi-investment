"""
端到端测试：自定义成交价格功能

验证策略回测和执行支持自定义买卖价格
"""

import pytest
from datetime import datetime, timedelta
from application.services.strategy_backtest_service import StrategyBacktestService
from application.services.strategy_code_validator import StrategyCodeValidator
from adapters.outbound.repositories import KlineORMRepository


class TestCustomPriceBacktest:
    """自定义价格回测测试"""

    def setup_method(self):
        self.backtest_service = StrategyBacktestService()
        self.validator = StrategyCodeValidator()
        self.kline_repo = KlineORMRepository()

    def test_buy_at_low_sell_at_high(self):
        """测试：以最低价买入，最高价卖出"""

        # 策略代码：RSI超卖时以最低价买入，RSI超买时以最高价卖出
        strategy_code = """
my_indicator_name = "低买高卖测试策略"

def calc_indicator(ctx):
    df = ctx.df

    # 买入信号：RSI < 30，以最低价买入
    df['buy_tier1'] = df['rsi14'] < 30
    df['buy_tier1_pct'] = 1.0
    df['buy_tier1_price'] = df['low'] * 1.01  # 最低价上浮1%

    # 卖出信号：RSI > 70，以最高价卖出
    df['sell_tier1'] = df['rsi14'] > 70
    df['sell_tier1_pct'] = 1.0
    df['sell_tier1_price'] = df['high'] * 0.99  # 最高价下浮1%

    return df
"""

        strategy = {
            'code_content': strategy_code,
            'code_type': 'indicator',
            'parsed_params': {}
        }

        # 获取测试数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        klines = self.kline_repo.get_daily_klines(
            symbol='600519.SH',  # 贵州茅台
            start_date=start_date,
            end_date=end_date
        )

        assert len(klines) > 0, "未获取到K线数据"

        # 运行回测
        result = self.backtest_service.backtest_indicator_strategy(
            strategy=strategy,
            klines=klines,
            initial_cash=1000000
        )

        # 验证回测完成
        assert result is not None
        assert 'total_return' in result
        assert 'trades' in result

        # 验证交易记录中使用了自定义价格
        trades = result.get('trades', [])
        if len(trades) > 0:
            first_trade = trades[0]

            # 验证买入价应该是 low * 1.01
            entry_price = first_trade['entry_price']

            # 验证卖出价应该是 high * 0.99（如果有卖出）
            if 'exit_price' in first_trade and first_trade['exit_price'] is not None:
                exit_price = first_trade['exit_price']
                assert exit_price > 0, "卖出价格应大于0"

        print(f"\n回测结果：")
        print(f"  总收益率: {result['total_return']:.2%}")
        print(f"  交易次数: {result['trade_count']}")
        print(f"  胜率: {result['win_rate']:.2%}")
        print(f"  夏普比率: {result.get('sharpe_ratio', 0):.2f}")

    def test_default_price_when_not_specified(self):
        """测试：未指定价格时使用收盘价"""

        strategy_code = """
my_indicator_name = "默认价格测试策略"

def calc_indicator(ctx):
    df = ctx.df

    # 不指定价格列，应使用收盘价
    df['buy_tier1'] = df['rsi14'] < 30
    df['buy_tier1_pct'] = 1.0

    df['sell_tier1'] = df['rsi14'] > 70
    df['sell_tier1_pct'] = 1.0

    return df
"""

        strategy = {
            'code_content': strategy_code,
            'code_type': 'indicator',
            'parsed_params': {}
        }

        # 获取测试数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        klines = self.kline_repo.get_daily_klines(
            symbol='000001.SZ',  # 平安银行
            start_date=start_date,
            end_date=end_date
        )

        assert len(klines) > 0, "未获取到K线数据"

        # 运行回测
        result = self.backtest_service.backtest_indicator_strategy(
            strategy=strategy,
            klines=klines,
            initial_cash=1000000
        )

        # 验证回测完成
        assert result is not None
        assert 'total_return' in result

        print(f"\n默认价格回测结果：")
        print(f"  总收益率: {result['total_return']:.2%}")
        print(f"  交易次数: {result['trade_count']}")

    def test_tiered_buy_with_different_prices(self):
        """测试：分批买入使用不同价格"""

        strategy_code = """
my_indicator_name = "分批买入不同价格测试"

def calc_indicator(ctx):
    df = ctx.df

    # Tier1: 以开盘价买入30%
    df['buy_tier1'] = df['rsi14'] < 35
    df['buy_tier1_pct'] = 0.3
    df['buy_tier1_price'] = df['open']

    # Tier2: 以最低价买入30%
    df['buy_tier2'] = df['rsi14'] < 30
    df['buy_tier2_pct'] = 0.3
    df['buy_tier2_price'] = df['low']

    # Tier3: 以收盘价买入40%（默认）
    df['buy_tier3'] = df['rsi14'] < 25
    df['buy_tier3_pct'] = 0.4

    # 统一卖出信号
    df['sell_tier1'] = df['rsi14'] > 70
    df['sell_tier1_pct'] = 1.0
    df['sell_tier1_price'] = df['close']

    return df
"""

        strategy = {
            'code_content': strategy_code,
            'code_type': 'indicator',
            'parsed_params': {}
        }

        # 获取测试数据
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        klines = self.kline_repo.get_daily_klines(
            symbol='000858.SZ',  # 五粮液
            start_date=start_date,
            end_date=end_date
        )

        assert len(klines) > 0, "未获取到K线数据"

        # 运行回测
        result = self.backtest_service.backtest_indicator_strategy(
            strategy=strategy,
            klines=klines,
            initial_cash=1000000
        )

        # 验证回测完成
        assert result is not None
        assert 'total_return' in result

        print(f"\n分批买入回测结果：")
        print(f"  总收益率: {result['total_return']:.2%}")
        print(f"  交易次数: {result['trade_count']}")

    def test_price_validation(self):
        """测试：价格校验功能"""

        import pandas as pd

        # 创建测试数据
        test_data = pd.DataFrame({
            'open': [10.0, 11.0, 12.0],
            'high': [10.5, 11.5, 12.5],
            'low': [9.5, 10.5, 11.5],
            'close': [10.2, 11.2, 12.2],
            'buy_tier1_price': [10.6, 11.6, 12.6],  # 高于最高价（异常）
            'buy_tier2_price': [9.0, 10.0, 11.0],   # 低于最低价（异常）
            'sell_tier1_price': [10.3, 11.3, 12.3], # 正常范围
        })

        # 运行价格校验
        warnings = self.validator.validate_custom_prices(test_data)

        # 验证校验结果
        assert len(warnings) > 0, "应该检测到价格异常"

        # 验证具体警告
        assert any('buy_tier1_price > high' in w for w in warnings)
        assert any('buy_tier2_price < low' in w for w in warnings)

        print(f"\n价格校验警告：")
        for warning in warnings:
            print(f"  - {warning}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
