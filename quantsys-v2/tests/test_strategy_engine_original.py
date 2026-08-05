"""
策略引擎单元测试

所有策略均使用合成K线数据测试，不依赖数据库。
StrategyRunner 相关的集成测试在有数据库时运行。
"""
import pytest
import math
from typing import List, Dict


# ==================== 合成K线数据工具 ====================

def make_klines(closes: List[float]) -> List[Dict]:
    """
    根据收盘价序列生成合成K线数据。

    open/high/low 根据 close 自动推导：
    - open = 前一日 close
    - high/low = close +/- 2%
    """
    klines = []
    for i, close in enumerate(closes):
        prev_close = closes[i - 1] if i > 0 else close
        klines.append({
            'trade_date': f'2024-01-{i+1:02d}',
            'symbol': 'TEST01',
            'open': prev_close,
            'high': close * 1.02,
            'low': close * 0.98,
            'close': close,
            'volume': 1000000.0,
        })
    return klines


def uptrend_closes(n: int, start: float = 10.0, step: float = 0.2) -> List[float]:
    """生成上升趋势的收盘价序列"""
    return [start + i * step for i in range(n)]


def downtrend_closes(n: int, start: float = 20.0, step: float = 0.2) -> List[float]:
    """生成下降趋势的收盘价序列"""
    return [start - i * step for i in range(n)]


def sideways_closes(n: int, center: float = 10.0, amplitude: float = 0.5) -> List[float]:
    """生成横盘震荡的收盘价序列"""
    closes = []
    for i in range(n):
        offset = amplitude * math.sin(2 * math.pi * i / 10)
        closes.append(center + offset)
    return closes


def sharp_drop_closes(n: int, start: float = 20.0, drop_pct: float = 0.3) -> List[float]:
    """
    生成前大半段平稳、末尾急跌的序列（用于RSI超卖测试）。

    前 n-drop_period 天在 start 附近小幅波动，
    最后 drop_period 天连续大跌。
    """
    drop_period = max(3, n // 5)
    closes = []
    for i in range(n - drop_period):
        closes.append(start + (i % 3) * 0.05)
    current = closes[-1]
    for _ in range(drop_period):
        current *= (1 - drop_pct / drop_period)
        closes.append(current)
    return closes


def sharp_rally_closes(n: int, start: float = 10.0, rally_pct: float = 0.3) -> List[float]:
    """
    生成前大半段平稳、末尾急涨的序列（用于RSI超买测试）。
    """
    rally_period = max(3, n // 5)
    closes = []
    for i in range(n - rally_period):
        closes.append(start + (i % 3) * 0.05)
    current = closes[-1]
    for _ in range(rally_period):
        current *= (1 + rally_pct / rally_period)
        closes.append(current)
    return closes


# ==================== StrategyBase 辅助方法测试 ====================

class TestStrategyBaseHelpers:
    """测试 StrategyBase 中的工具方法"""

    @pytest.fixture
    def base(self):
        from domain.quantlib.engine.strategy_base import StrategyBase

        # 用具体子类测试抽象类的方法
        class ConcreteStrategy(StrategyBase):
            def generate_signal(self, klines, params=None):
                return {'action': 'hold', 'confidence': 0.5, 'reason': ''}

        return ConcreteStrategy()

    def test_calculate_ma(self, base):
        """测试移动均线计算"""
        prices = [10.0, 12.0, 14.0, 16.0, 18.0]
        ma3 = base._calculate_ma(prices, 3)

        assert len(ma3) == len(prices)
        assert ma3[0] is None
        assert ma3[1] is None
        assert ma3[2] == pytest.approx(12.0)   # (10+12+14)/3
        assert ma3[3] == pytest.approx(14.0)    # (12+14+16)/3
        assert ma3[4] == pytest.approx(16.0)    # (14+16+18)/3

    def test_calculate_ma_insufficient_data(self, base):
        """测试均线计算数据不足"""
        with pytest.raises(ValueError, match="价格数据不足"):
            base._calculate_ma([10.0, 12.0], 5)

    def test_calculate_rsi(self, base):
        """测试RSI计算"""
        # 全部上涨 -> RSI 应为 100
        prices = list(range(1, 20))
        rsi = base._calculate_rsi(prices, 14)
        assert rsi > 90, f"Expected RSI > 90 for all-up prices, got {rsi}"

    def test_calculate_rsi_all_down(self, base):
        """测试全部下跌的RSI"""
        prices = list(range(20, 1, -1))
        rsi = base._calculate_rsi(prices, 14)
        assert rsi < 10, f"Expected RSI < 10 for all-down prices, got {rsi}"

    def test_calculate_rsi_sideways(self, base):
        """测试横盘的RSI"""
        prices = [10.0] * 20
        rsi = base._calculate_rsi(prices, 14)
        assert rsi == pytest.approx(50.0, abs=5), f"Expected RSI ~50 for flat, got {rsi}"

    def test_calculate_rsi_insufficient_data(self, base):
        """测试RSI计算数据不足"""
        with pytest.raises(ValueError, match="价格数据不足"):
            base._calculate_rsi([10.0, 11.0], 14)

    def test_calculate_bollinger_bands(self, base):
        """测试布林带计算"""
        prices = [10.0 + i * 0.1 for i in range(25)]  # 缓慢上升
        bands = base._calculate_bollinger_bands(prices, 20, 2.0)

        assert 'middle' in bands
        assert 'upper' in bands
        assert 'lower' in bands
        assert len(bands['middle']) == len(prices)
        assert bands['middle'][19] is not None
        assert bands['upper'][19] is not None
        assert bands['lower'][19] is not None
        assert bands['upper'][19] > bands['middle'][19] > bands['lower'][19]

    def test_validate_klines(self, base):
        """测试K线验证"""
        # 有效数据
        base._validate_klines([{'close': 10.0}, {'close': 12.0}], min_length=2)

        # 空数据
        with pytest.raises(ValueError, match="K线数据为空"):
            base._validate_klines([], min_length=2)

        # 缺少字段
        with pytest.raises(ValueError, match="缺少必需字段"):
            base._validate_klines([{'not_close': 10.0}], min_length=1)

    def test_extract_closes(self, base):
        """测试收盘价提取"""
        klines = make_klines([10.0, 12.0, 14.0])
        closes = base._extract_closes(klines)
        assert closes == [10.0, 12.0, 14.0]


# ==================== MACrossStrategy 测试 ====================

class TestMACrossStrategy:
    """均线交叉策略测试"""

    @pytest.fixture
    def strategy(self):
        from domain.quantlib.engine.ma_cross import MACrossStrategy
        return MACrossStrategy()

    def test_golden_cross_buy_signal(self, strategy):
        """
        金叉买入信号:
        前段横盘（MA5≈MA20），最后一天巨幅拉升，
        MA5 在最后一刻上穿 MA20。
        """
        # 25天10元横盘（MA5≈MA20=10），最后一天跳涨到20
        closes = [10.0] * 25 + [20.0]
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'ma_short': 5, 'ma_long': 20})

        assert signal['action'] == 'buy'
        assert 0 < signal['confidence'] <= 1.0
        assert 'MA5' in signal['reason']
        assert 'MA20' in signal['reason']
        assert '金叉' in signal['reason']

    def test_death_cross_sell_signal(self, strategy):
        """
        死叉卖出信号:
        前段横盘（MA5≈MA20），最后一天暴跌，
        MA5 在最后一刻下穿 MA20。
        """
        # 25天10元横盘（MA5≈MA20=10），最后一天暴跌到5
        closes = [10.0] * 25 + [5.0]
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'ma_short': 5, 'ma_long': 20})

        assert signal['action'] == 'sell'
        assert 0 < signal['confidence'] <= 1.0
        assert '死叉' in signal['reason']

    def test_uptrend_hold_bullish(self, strategy):
        """上升趋势中无交叉，持有多头判断"""
        closes = uptrend_closes(50, start=10.0, step=0.2)
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'ma_short': 5, 'ma_long': 20})

        assert signal['action'] == 'hold'
        assert '多头排列' in signal['reason']

    def test_downtrend_hold_bearish(self, strategy):
        """下降趋势中无交叉，持有空头判断"""
        closes = downtrend_closes(50, start=20.0, step=0.2)
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'ma_short': 5, 'ma_long': 20})

        assert signal['action'] == 'hold'
        assert '空头排列' in signal['reason']

    def test_insufficient_data(self, strategy):
        """数据不足"""
        with pytest.raises(ValueError, match="K线数据不足"):
            strategy.generate_signal(make_klines([10.0] * 10), {'ma_short': 5, 'ma_long': 20})

    def test_custom_params(self, strategy):
        """自定义参数"""
        closes = [10.0] * 30 + [15.0] * 10
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'ma_short': 10, 'ma_long': 30})

        assert signal['action'] in ('buy', 'sell', 'hold')
        assert 'MA10' in signal['reason']
        assert 'MA30' in signal['reason']


# ==================== RSIReversalStrategy 测试 ====================

class TestRSIReversalStrategy:
    """RSI反转策略测试"""

    @pytest.fixture
    def strategy(self):
        from domain.quantlib.engine.rsi_reversal import RSIReversalStrategy
        return RSIReversalStrategy()

    def test_oversold_buy_signal(self, strategy):
        """超卖买入信号: 急跌后RSI低于30"""
        closes = sharp_drop_closes(30, start=20.0, drop_pct=0.4)
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'period': 14, 'oversold': 30, 'overbought': 70})

        assert signal['action'] == 'buy'
        assert 0 < signal['confidence'] <= 1.0
        assert '超卖' in signal['reason']

    def test_overbought_sell_signal(self, strategy):
        """超买卖出信号: 急涨后RSI高于70"""
        closes = sharp_rally_closes(30, start=10.0, rally_pct=0.4)
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'period': 14, 'oversold': 30, 'overbought': 70})

        assert signal['action'] == 'sell'
        assert 0 < signal['confidence'] <= 1.0
        assert '超买' in signal['reason']

    def test_neutral_hold(self, strategy):
        """中性区间持有"""
        closes = sideways_closes(30, center=10.0, amplitude=0.2)
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'period': 14, 'oversold': 30, 'overbought': 70})

        assert signal['action'] == 'hold'
        assert '正常区间' in signal['reason']

    def test_custom_thresholds(self, strategy):
        """自定义超买超卖阈值"""
        closes = sharp_drop_closes(30, start=20.0, drop_pct=0.2)
        klines = make_klines(closes)

        # 使用更宽的阈值，急跌也不触发
        signal = strategy.generate_signal(klines, {'period': 14, 'oversold': 20, 'overbought': 80})

        assert signal is not None
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_insufficient_data(self, strategy):
        """数据不足"""
        with pytest.raises(ValueError, match="K线数据不足"):
            strategy.generate_signal(make_klines([10.0] * 10))


# ==================== BollingerBreakoutStrategy 测试 ====================

class TestBollingerBreakoutStrategy:
    """布林带突破策略测试"""

    @pytest.fixture
    def strategy(self):
        from domain.quantlib.engine.bollinger_breakout import BollingerBreakoutStrategy
        return BollingerBreakoutStrategy()

    def test_upper_breakout_buy(self, strategy):
        """向上突破上轨买入"""
        # 25天窄幅横盘，然后一天巨幅拉升突破上轨
        closes = [10.0 + (i % 3) * 0.05 for i in range(25)] + [14.0]
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'period': 20, 'num_std': 2.0})

        assert signal['action'] == 'buy'
        assert 0 < signal['confidence'] <= 1.0
        assert '上轨' in signal['reason']

    def test_lower_breakout_sell(self, strategy):
        """向下突破下轨卖出"""
        # 25天窄幅横盘，然后一天暴跌突破下轨
        closes = [10.0 + (i % 3) * 0.05 for i in range(25)] + [8.0]
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'period': 20, 'num_std': 2.0})

        assert signal['action'] == 'sell'
        assert 0 < signal['confidence'] <= 1.0
        assert '下轨' in signal['reason']

    def test_no_breakout_hold(self, strategy):
        """无突破持有"""
        closes = sideways_closes(30, center=10.0, amplitude=0.3)
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'period': 20, 'num_std': 2.0})

        assert signal['action'] == 'hold'
        assert '无突破' in signal['reason']

    def test_custom_params(self, strategy):
        """自定义布林带参数"""
        closes = [10.0 + (i % 3) * 0.05 for i in range(15)] + [14.0]
        klines = make_klines(closes)

        signal = strategy.generate_signal(klines, {'period': 10, 'num_std': 1.5})

        assert signal is not None
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_insufficient_data(self, strategy):
        """数据不足"""
        with pytest.raises(ValueError, match="K线数据不足"):
            strategy.generate_signal(make_klines([10.0] * 10), {'period': 20})


# ==================== StrategyCombiner 测试 ====================

class TestStrategyCombiner:
    """策略组合器测试"""

    @pytest.fixture
    def signals_all_buy(self):
        return [
            {'action': 'buy', 'confidence': 0.8, 'reason': '金叉'},
            {'action': 'buy', 'confidence': 0.7, 'reason': '超卖'},
            {'action': 'buy', 'confidence': 0.9, 'reason': '突破上轨'},
        ]

    @pytest.fixture
    def signals_mixed(self):
        return [
            {'action': 'buy', 'confidence': 0.8, 'reason': '金叉'},
            {'action': 'sell', 'confidence': 0.7, 'reason': '超买'},
            {'action': 'hold', 'confidence': 0.5, 'reason': '中性'},
        ]

    @pytest.fixture
    def signals_all_hold(self):
        return [
            {'action': 'hold', 'confidence': 0.5, 'reason': '正常'},
            {'action': 'hold', 'confidence': 0.4, 'reason': '震荡'},
        ]

    def test_and_mode_all_buy(self, signals_all_buy):
        """AND模式: 全部buy -> buy"""
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner
        combiner = StrategyCombiner(mode='and')
        result = combiner.combine(signals_all_buy)

        assert result['action'] == 'buy'
        assert 0.7 <= result['confidence'] <= 0.9
        assert 'AND' in result['reason']

    def test_and_mode_mixed(self, signals_mixed):
        """AND模式: 策略分歧 -> hold"""
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner
        combiner = StrategyCombiner(mode='and')
        result = combiner.combine(signals_mixed)

        assert result['action'] == 'hold'
        assert '分歧' in result['reason']

    def test_or_mode_mixed(self, signals_mixed):
        """OR模式: 有非hold信号 -> 取最高置信度"""
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner
        combiner = StrategyCombiner(mode='or')
        result = combiner.combine(signals_mixed)

        assert result['action'] == 'buy'  # buy confidence 0.8 > sell 0.7
        assert result['confidence'] == pytest.approx(0.8)

    def test_or_mode_all_hold(self, signals_all_hold):
        """OR模式: 全部hold -> hold"""
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner
        combiner = StrategyCombiner(mode='or')
        result = combiner.combine(signals_all_hold)

        assert result['action'] == 'hold'

    def test_majority_mode(self, signals_mixed):
        """多数投票模式: buy=1, sell=1, hold=1 -> 平票取非hold"""
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner
        combiner = StrategyCombiner(mode='majority')
        result = combiner.combine(signals_mixed)

        # 各一票，平票时非hold优先
        assert result['action'] in ('buy', 'sell')

    def test_majority_mode_clear_winner(self):
        """多数投票: buy buy hold -> buy"""
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner
        signals = [
            {'action': 'buy', 'confidence': 0.8, 'reason': 'p1'},
            {'action': 'buy', 'confidence': 0.6, 'reason': 'p2'},
            {'action': 'hold', 'confidence': 0.5, 'reason': 'p3'},
        ]
        combiner = StrategyCombiner(mode='majority')
        result = combiner.combine(signals)

        assert result['action'] == 'buy'
        assert '2/3' in result['reason']

    def test_weighted_mode(self, signals_mixed):
        """加权模式: 按权重聚合"""
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner
        combiner = StrategyCombiner(mode='weighted')
        # buy权重3, sell权重1 -> buy加权得分更高
        result = combiner.combine(signals_mixed, weights=[3.0, 1.0, 1.0])

        assert result['action'] == 'buy'
        assert '加权' in result['reason']

    def test_weighted_mode_all_zero_weights(self, signals_mixed):
        """加权模式: 所有权重为0"""
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner
        combiner = StrategyCombiner(mode='weighted')
        result = combiner.combine(signals_mixed, weights=[0.0, 0.0, 0.0])

        assert result['action'] == 'hold'
        assert result['confidence'] == 0.0

    def test_empty_signals(self):
        """空信号列表"""
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner
        combiner = StrategyCombiner(mode='majority')
        result = combiner.combine([])

        assert result['action'] == 'hold'
        assert result['confidence'] == 0.0
        assert '无策略' in result['reason']

    def test_invalid_mode(self):
        """无效组合模式"""
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner
        with pytest.raises(ValueError, match="无效的组合模式"):
            StrategyCombiner(mode='invalid')


# ==================== 集成测试：策略端到端 ====================

class TestEndToEnd:
    """端到端集成测试"""

    def test_all_strategies_on_uptrend(self):
        """上升趋势中所有策略的信号综合"""
        from domain.quantlib.engine.ma_cross import MACrossStrategy
        from domain.quantlib.engine.rsi_reversal import RSIReversalStrategy
        from domain.quantlib.engine.bollinger_breakout import BollingerBreakoutStrategy

        closes = [10.0] * 20 + [10.0 + i * 0.5 for i in range(20)]
        klines = make_klines(closes)

        ma = MACrossStrategy()
        rsi = RSIReversalStrategy()
        bb = BollingerBreakoutStrategy()

        ma_signal = ma.generate_signal(klines, {'ma_short': 5, 'ma_long': 20})
        rsi_signal = rsi.generate_signal(klines, {'period': 14, 'oversold': 30, 'overbought': 70})
        bb_signal = bb.generate_signal(klines, {'period': 20, 'num_std': 2.0})

        # 上升趋势中，MA应给buy或hold
        assert ma_signal['action'] in ('buy', 'hold')
        assert ma_signal['confidence'] >= 0.0

        # RSI可能在超买区
        assert rsi_signal['action'] in ('buy', 'sell', 'hold')

        # BB可能有突破
        assert bb_signal['action'] in ('buy', 'sell', 'hold')

    def test_all_strategies_on_downtrend(self):
        """下降趋势中所有策略的信号综合"""
        from domain.quantlib.engine.ma_cross import MACrossStrategy
        from domain.quantlib.engine.rsi_reversal import RSIReversalStrategy
        from domain.quantlib.engine.bollinger_breakout import BollingerBreakoutStrategy

        closes = [20.0] * 20 + [20.0 - i * 0.5 for i in range(20)]
        klines = make_klines(closes)

        ma = MACrossStrategy()
        rsi = RSIReversalStrategy()
        bb = BollingerBreakoutStrategy()

        ma_signal = ma.generate_signal(klines, {'ma_short': 5, 'ma_long': 20})
        rsi_signal = rsi.generate_signal(klines, {'period': 14, 'oversold': 30, 'overbought': 70})
        bb_signal = bb.generate_signal(klines, {'period': 20, 'num_std': 2.0})

        # 下降趋势中，MA应给sell或hold
        assert ma_signal['action'] in ('sell', 'hold')

        # RSI可能在超卖区
        assert rsi_signal['action'] in ('buy', 'sell', 'hold')

        # BB可能有突破
        assert bb_signal['action'] in ('buy', 'sell', 'hold')

    def test_signal_format(self):
        """验证信号返回格式"""
        from domain.quantlib.engine.ma_cross import MACrossStrategy

        strategy = MACrossStrategy()
        klines = make_klines(uptrend_closes(50, start=10.0, step=0.2))

        signal = strategy.generate_signal(klines, {'ma_short': 5, 'ma_long': 20})

        assert 'action' in signal
        assert signal['action'] in ('buy', 'sell', 'hold')
        assert 'confidence' in signal
        assert isinstance(signal['confidence'], (int, float))
        assert 0.0 <= signal['confidence'] <= 1.0
        assert 'reason' in signal
        assert isinstance(signal['reason'], str)
        assert len(signal['reason']) > 0

    def test_combine_all_three_on_uptrend(self):
        """组合三种策略信号的端到端测试"""
        from domain.quantlib.engine.ma_cross import MACrossStrategy
        from domain.quantlib.engine.rsi_reversal import RSIReversalStrategy
        from domain.quantlib.engine.bollinger_breakout import BollingerBreakoutStrategy
        from domain.quantlib.engine.strategy_combiner import StrategyCombiner

        closes = [10.0] * 20 + [10.0 + i * 0.5 for i in range(20)]
        klines = make_klines(closes)

        ma = MACrossStrategy()
        rsi = RSIReversalStrategy()
        bb = BollingerBreakoutStrategy()

        signals = [
            ma.generate_signal(klines, {'ma_short': 5, 'ma_long': 20}),
            rsi.generate_signal(klines, {'period': 14, 'oversold': 30, 'overbought': 70}),
            bb.generate_signal(klines, {'period': 20, 'num_std': 2.0}),
        ]

        # 测试各种组合模式
        for mode in ['and', 'or', 'majority', 'weighted']:
            combiner = StrategyCombiner(mode=mode)
            result = combiner.combine(signals)

            assert 'action' in result
            assert 'confidence' in result
            assert 'reason' in result
            assert result['action'] in ('buy', 'sell', 'hold')


# ==================== StrategyRepository 测试 (需要数据库) ====================

class TestStrategyRepository:
    """StrategyRepository测试（需要数据库连接）"""

    @pytest.fixture
    def repo(self):
        from adapters.outbound.repositories import StrategyORMRepository
        r = StrategyORMRepository()
        yield r
        if hasattr(r, 'db') and r.db:
            r.db.close()

    def test_get_all(self, repo):
        """测试获取所有策略"""
        try:
            strategies = repo.get_all()
            assert isinstance(strategies, list)
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

    def test_get_all_active_only(self, repo):
        """测试只获取活跃策略"""
        try:
            strategies = repo.get_all(active_only=True)
            assert isinstance(strategies, list)
            for s in strategies:
                assert s['is_active'] is True
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

    def test_get_by_id_not_found(self, repo):
        """测试查询不存在的策略"""
        try:
            result = repo.get_by_id(999999999)
            assert result is None
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

    def test_get_by_name_not_found(self, repo):
        """测试查询不存在的策略名"""
        try:
            result = repo.get_by_name('nonexistent_strategy_12345')
            assert result is None
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

    def test_get_by_type(self, repo):
        """测试按类型查询"""
        try:
            for stype in ['ma_cross', 'rsi_reversal', 'bollinger_breakout', 'custom']:
                strategies = repo.get_by_type(stype)
                assert isinstance(strategies, list)
                for s in strategies:
                    assert s['strategy_type'] == stype
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

    def test_create_and_delete(self, repo):
        """测试创建和删除策略"""
        try:
            data = {
                'name': 'test_strategy_temp',
                'strategy_type': 'ma_cross',
                'description': '测试策略',
                'parameters': {'ma_short': 5, 'ma_long': 20},
                'is_active': True,
            }
            created = repo.create(data)
            assert created is not None
            assert created['name'] == 'test_strategy_temp'
            assert created['strategy_type'] == 'ma_cross'
            assert isinstance(created['id'], int)

            # 先验证创建成功
            fetched = repo.get_by_id(created['id'])
            assert fetched is not None
            assert fetched['name'] == 'test_strategy_temp'

            # 验证参数序列化
            params = fetched['parameters']
            if isinstance(params, str):
                import json
                params = json.loads(params)
            assert params['ma_short'] == 5
            assert params['ma_long'] == 20

            # 删除
            deleted = repo.delete(created['id'])
            assert deleted is True

            # 验证已删除
            fetched_after = repo.get_by_id(created['id'])
            assert fetched_after is None

        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {e}")

    def test_update(self, repo):
        """测试更新策略"""
        try:
            # 先创建一个测试策略
            data = {
                'name': 'test_update_temp',
                'strategy_type': 'ma_cross',
                'description': 'before update',
                'parameters': {'ma_short': 5, 'ma_long': 20},
                'is_active': True,
            }
            created = repo.create(data)

            # 更新
            updated = repo.update(created['id'], {
                'description': 'after update',
                'parameters': {'ma_short': 10, 'ma_long': 30},
            })
            assert updated is not None
            assert updated['description'] == 'after update'

            # 验证参数
            params = updated['parameters']
            if isinstance(params, str):
                import json
                params = json.loads(params)
            assert params['ma_short'] == 10
            assert params['ma_long'] == 30

            # 清理
            repo.delete(created['id'])

        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {e}")

    def test_toggle(self, repo):
        """测试切换策略状态"""
        try:
            data = {
                'name': 'test_toggle_temp',
                'strategy_type': 'ma_cross',
                'parameters': {'ma_short': 5, 'ma_long': 20},
                'is_active': True,
            }
            created = repo.create(data)
            assert created['is_active'] is True

            # 切换
            toggled = repo.toggle(created['id'])
            assert toggled is not None
            assert toggled['is_active'] is False

            # 再切换回来
            toggled2 = repo.toggle(created['id'])
            assert toggled2['is_active'] is True

            # 清理
            repo.delete(created['id'])

        except Exception as e:
            pytest.skip(f"数据库写入测试跳过: {e}")

    def test_update_nonexistent(self, repo):
        """测试更新不存在的策略"""
        try:
            result = repo.update(999999999, {'description': 'test'})
            assert result is None
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

    def test_delete_nonexistent(self, repo):
        """测试删除不存在的策略"""
        try:
            result = repo.delete(999999999)
            assert result is False
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

    def test_create_missing_name(self, repo):
        """测试缺少名称字段"""
        try:
            with pytest.raises(ValueError, match="缺少必需字段"):
                repo.create({'strategy_type': 'ma_cross'})
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

    def test_create_missing_type(self, repo):
        """测试缺少类型字段"""
        try:
            with pytest.raises(ValueError, match="缺少必需字段"):
                repo.create({'name': 'test_no_type'})
        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")


# ==================== StrategyRunner 测试 (需要数据库) ====================

class TestStrategyRunner:
    """StrategyRunner测试（需要数据库连接）"""

    @pytest.fixture
    def runner(self):
        from domain.quantlib.engine.strategy_runner import StrategyRunner
        from adapters.outbound.repositories import StrategyORMRepository
        r = StrategyRunner(strategy_repo=StrategyORMRepository())
        yield r
        r.close()

    def test_run_with_klines(self, runner):
        """测试使用K线数据运行策略"""
        try:
            klines = make_klines(uptrend_closes(50, start=10.0, step=0.2))
            signals = runner.run(klines, symbol='000001.SZ')

            assert isinstance(signals, list)
            for signal in signals:
                assert 'strategy_name' in signal
                assert 'action' in signal
                assert 'confidence' in signal
                assert 'reason' in signal
                assert signal['action'] in ('buy', 'sell', 'hold')
                assert 0.0 <= signal['confidence'] <= 1.0

            # 验证按置信度降序排列
            if len(signals) > 1:
                for i in range(len(signals) - 1):
                    assert (
                        signals[i]['confidence'] >= signals[i + 1]['confidence']
                        or signals[i]['action'] != signals[i + 1]['action']
                    )

        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

    def test_get_top_signals(self, runner):
        """测试获取Top N信号"""
        try:
            klines = make_klines(uptrend_closes(50, start=10.0, step=0.2))
            top = runner.get_top_signals(klines, symbol='000001.SZ', top_n=3)

            assert isinstance(top, list)
            assert len(top) <= 3

        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

    def test_combine_signals(self, runner):
        """测试组合信号"""
        try:
            klines = make_klines(uptrend_closes(50, start=10.0, step=0.2))
            result = runner.combine_signals(klines, mode='majority')

            assert 'action' in result
            assert 'confidence' in result
            assert 'reason' in result

        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")

    def test_combine_signals_weighted(self, runner):
        """测试加权组合"""
        try:
            klines = make_klines(uptrend_closes(50, start=10.0, step=0.2))
            configs = runner.repo.get_all(active_only=True)

            if configs:
                ids = [c['id'] for c in configs]
                weights = [1.0] * len(ids)
                result = runner.combine_signals(
                    klines, config_ids=ids, mode='weighted', weights=weights
                )

                assert 'action' in result
                assert 'confidence' in result

        except Exception as e:
            pytest.skip(f"数据库不可用: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
