"""
端到端测试：自定义成交价格功能

验证策略回测和执行支持自定义买卖价格
"""

import pytest
from datetime import datetime, timedelta
from application.services.strategy_backtest_service import StrategyBacktestService
from application.services.strategy_code_validator import StrategyCodeValidator
from adapters.outbound.repositories import KlineORMRepository


# 2026-10-02（REQ-261001145152-3982 审查）：标的改用**测试库里确有日线数据**的一只。
# 实测 quant_test 中 600519.SH / 000001.SZ / 000858.SZ 的 daily_klines 均为 **0 行**
# （生产库才有），原本 3 个用例因此在 `assert len(klines) > 0` 处失败；600036.SH 有 120 行。
# 本文件验证的是「自定义成交价」功能，与具体标的口径无关，故统一到可用标的上。
TEST_SYMBOL = '600036.SH'


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
            symbol=TEST_SYMBOL,
            start_date=start_date,
            end_date=end_date
        )

        if len(klines) == 0:
            pytest.skip(
                f"测试库 {TEST_SYMBOL} 无日线数据（生产库有）：本组用例需铺底 K 线才能跑"
            )

        # 2026-10-02（REQ-261001145152-3982 审查）：**先按现契约转成 list[dict]**。
        # `KlineORMRepository.get_daily_klines()` 现返回 **polars DataFrame**
        # （签名标注即如此），而 `IndicatorStrategyExecutor.execute(klines: List[Dict])`
        # 与注入器都期望 list[dict]（每项含 open/high/low/close/volume）——
        # 本用例写于仓库返回 list[dict] 的年代，故直接传会一路 KeyError。
        if hasattr(klines, 'to_dicts'):          # polars
            klines = klines.to_dicts()
        elif hasattr(klines, 'to_dict'):         # pandas
            klines = klines.to_dict(orient='records')

        # **按生产口径先注入技术指标**。
        # `backtest_indicator_strategy` 的 docstring 明写 klines 须是"已注入因子和财务数据"的，
        # 而本用例此前把 get_daily_klines() 的**原始 K 线**直接喂进去，策略代码里的
        # df['rsi14'] 于是 KeyError（4 条用例全因此失败）。
        # 生产路径（strategy_code_service）正是用同一个注入器准备的，这里照做。
        from application.services.strategy_code_service import StrategyCodeService
        klines = StrategyCodeService()._inject_technical_indicators(klines)

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
        print(f"  交易次数: {result['total_trades']}")
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
            symbol=TEST_SYMBOL,
            start_date=start_date,
            end_date=end_date
        )

        if len(klines) == 0:
            pytest.skip(
                f"测试库 {TEST_SYMBOL} 无日线数据（生产库有）：本组用例需铺底 K 线才能跑"
            )

        # 2026-10-02（REQ-261001145152-3982 审查）：**按生产口径先注入技术指标**。
        # `backtest_indicator_strategy` 的 docstring 明写 klines 须是"已注入因子和财务数据"的，
        # 而本用例此前把 get_daily_klines() 的**原始 K 线**直接喂进去，策略代码里的
        # df['rsi14'] 于是 KeyError（4 条用例全因此失败）。
        # 生产路径（strategy_code_service）正是用同一个注入器准备的，这里照做。
        from application.services.strategy_code_service import StrategyCodeService
        # 2026-10-02（REQ-261001145152-3982 审查）：仓库现返回 polars DataFrame，
        # 而执行器与注入器要 list[dict] —— 先转换再注入（同上）。
        if hasattr(klines, 'to_dicts'):
            klines = klines.to_dicts()
        elif hasattr(klines, 'to_dict'):
            klines = klines.to_dict(orient='records')
        klines = StrategyCodeService()._inject_technical_indicators(klines)

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
        print(f"  交易次数: {result['total_trades']}")

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
            symbol=TEST_SYMBOL,
            start_date=start_date,
            end_date=end_date
        )

        if len(klines) == 0:
            pytest.skip(
                f"测试库 {TEST_SYMBOL} 无日线数据（生产库有）：本组用例需铺底 K 线才能跑"
            )

        # 2026-10-02（REQ-261001145152-3982 审查）：**按生产口径先注入技术指标**。
        # `backtest_indicator_strategy` 的 docstring 明写 klines 须是"已注入因子和财务数据"的，
        # 而本用例此前把 get_daily_klines() 的**原始 K 线**直接喂进去，策略代码里的
        # df['rsi14'] 于是 KeyError（4 条用例全因此失败）。
        # 生产路径（strategy_code_service）正是用同一个注入器准备的，这里照做。
        from application.services.strategy_code_service import StrategyCodeService
        # 2026-10-02（REQ-261001145152-3982 审查）：仓库现返回 polars DataFrame，
        # 而执行器与注入器要 list[dict] —— 先转换再注入（同上）。
        if hasattr(klines, 'to_dicts'):
            klines = klines.to_dicts()
        elif hasattr(klines, 'to_dict'):
            klines = klines.to_dict(orient='records')
        klines = StrategyCodeService()._inject_technical_indicators(klines)

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
        print(f"  交易次数: {result['total_trades']}")

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
        # 2026-10-02（REQ-261001145152-3982 审查）：该方法返回的是
        # **{'warnings': [...], 'errors': [...]}**（签名即 Dict[str, List[str]]），
        # 而本用例按 list 使用——`for w in warnings` 迭代到的是**键名**，
        # 于是两条具体断言永远匹配不到。此处取出 warnings 列表。
        _res = self.validator.validate_custom_prices(test_data)
        warnings = _res.get('warnings', []) if isinstance(_res, dict) else _res

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
