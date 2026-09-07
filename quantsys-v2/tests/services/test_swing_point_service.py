"""
SwingPointService 单元测试

测试 ZigZag 算法的核心逻辑，使用模拟 K 线数据。
"""
import pytest
from unittest.mock import patch, MagicMock
from application.services.swing_point_service import SwingPointService
from application.services.stock_code_validator import StockCodeValidator


def _make_klines(prices):
    """根据收盘价列表生成模拟 K 线"""
    klines = []
    for i, p in enumerate(prices):
        klines.append({
            'date': f'2025-01-{(i + 1):02d}',
            'open': p,
            'high': p * 1.01,   # high 略高于 close
            'low': p * 0.99,    # low 略低于 close
            'close': p,
            'volume': 10000,
        })
    return klines


def _make_klines_exact(entries):
    """根据精确的 OHLC 数据生成 K 线
    entries: [(date, open, high, low, close), ...]
    """
    klines = []
    for date, o, h, lo, c in entries:
        klines.append({
            'date': date,
            'open': o,
            'high': h,
            'low': lo,
            'close': c,
            'volume': 10000,
        })
    return klines


class TestZigZagAlgorithm:
    """测试 ZigZag 核心算法"""

    def setup_method(self):
        self.svc = SwingPointService()

    def test_simple_v_shape(self):
        """V 形走势：下跌后反弹，应识别出 1 个低点"""
        # 100 → 90 → 80 → 90 → 100 → 110
        prices = [100, 95, 90, 85, 80, 85, 90, 95, 100, 105, 110]
        klines = _make_klines(prices)

        points = self.svc._zigzag(klines, 0.10)  # 10% 阈值

        # 应该找到至少一个低点和一个高点
        types = [p['type'] for p in points]
        assert 'low' in types, f"应包含低点，实际: {types}"

    def test_simple_peak(self):
        """倒 V 形走势：上涨后下跌，应识别出 1 个高点"""
        prices = [80, 85, 90, 95, 100, 95, 90, 85, 80]
        klines = _make_klines(prices)

        points = self.svc._zigzag(klines, 0.10)

        types = [p['type'] for p in points]
        assert 'high' in types, f"应包含高点，实际: {types}"

    def test_alternating_high_low(self):
        """拐点必须高低交替出现"""
        prices = [100, 90, 80, 95, 110, 100, 85, 100, 115]
        klines = _make_klines(prices)

        points = self.svc._zigzag(klines, 0.08)

        for i in range(1, len(points)):
            assert points[i]['type'] != points[i - 1]['type'], \
                f"拐点 {i-1} 和 {i} 类型相同: {points[i-1]['type']}"

    def test_no_swing_below_threshold(self):
        """波动小于阈值时，不应产生拐点"""
        # 价格在 100 ± 2% 之间波动
        prices = [100, 101, 99, 100.5, 99.5, 100.2, 99.8]
        klines = _make_klines(prices)

        points = self.svc._zigzag(klines, 0.10)  # 10% 阈值

        # 可能只有首尾端点，不应有中间拐点
        mid_points = [p for p in points if p.get('change_pct', 0) != 0]
        # 2% 的波动在 10% 阈值下不应产生有意义的拐点
        assert len(mid_points) <= 2, f"不应有太多拐点: {points}"

    def test_empty_klines(self):
        """空数据应返回空列表"""
        points = self.svc._zigzag([], 0.05)
        assert points == []

    def test_insufficient_klines(self):
        """数据点不足应返回空列表"""
        points = self.svc._zigzag([{'date': '2025-01-01', 'high': 100, 'low': 99, 'close': 100}], 0.05)
        assert points == []


class TestPairTrades:
    """测试交易配对"""

    def setup_method(self):
        self.svc = SwingPointService()

    def test_basic_pairing(self):
        """低点买入 → 高点卖出"""
        points = [
            {'date': '2025-01-01', 'price': 80, 'type': 'low', 'change_pct': 0},
            {'date': '2025-01-10', 'price': 100, 'type': 'high', 'change_pct': 25.0},
            {'date': '2025-01-20', 'price': 85, 'type': 'low', 'change_pct': -15.0},
            {'date': '2025-01-30', 'price': 110, 'type': 'high', 'change_pct': 29.41},
        ]

        trades = self.svc._pair_trades(points)

        assert len(trades) == 2
        assert trades[0]['buy_price'] == 80
        assert trades[0]['sell_price'] == 100
        assert trades[0]['profit_pct'] == 25.0
        assert trades[1]['buy_price'] == 85
        assert trades[1]['sell_price'] == 110

    def test_starts_with_high(self):
        """以高点开头时，第一个高点应被跳过"""
        points = [
            {'date': '2025-01-01', 'price': 100, 'type': 'high', 'change_pct': 0},
            {'date': '2025-01-10', 'price': 80, 'type': 'low', 'change_pct': -20.0},
            {'date': '2025-01-20', 'price': 110, 'type': 'high', 'change_pct': 37.5},
        ]

        trades = self.svc._pair_trades(points)

        assert len(trades) == 1
        assert trades[0]['buy_price'] == 80
        assert trades[0]['sell_price'] == 110

    def test_empty_points(self):
        """空列表应返回空交易"""
        trades = self.svc._pair_trades([])
        assert trades == []


class TestComputeSummary:
    """测试统计计算"""

    def setup_method(self):
        self.svc = SwingPointService()

    def test_all_wins(self):
        """全部盈利"""
        trades = [
            {'profit_pct': 10.0, 'holding_days': 5},
            {'profit_pct': 20.0, 'holding_days': 10},
        ]
        s = self.svc._compute_summary(trades)
        assert s['total_trades'] == 2
        assert s['win_count'] == 2
        assert s['win_rate'] == 100.0
        assert s['avg_return'] == 15.0

    def test_mixed_results(self):
        """盈亏混合"""
        trades = [
            {'profit_pct': 15.0, 'holding_days': 10},
            {'profit_pct': -5.0, 'holding_days': 3},
            {'profit_pct': 8.0, 'holding_days': 7},
        ]
        s = self.svc._compute_summary(trades)
        assert s['total_trades'] == 3
        assert s['win_count'] == 2
        assert s['loss_count'] == 1
        assert s['win_rate'] == pytest.approx(66.7, abs=0.1)
        assert s['max_return'] == 15.0
        assert s['max_loss'] == -5.0

    def test_empty(self):
        """空交易列表"""
        s = self.svc._compute_summary([])
        assert s['total_trades'] == 0
        assert s['win_rate'] == 0.0


class TestAnalyzeIntegration:
    """集成测试（mock KlineRepository）"""

    @patch.object(SwingPointService, '__init__', lambda self: None)
    def test_missing_symbol(self):
        svc = SwingPointService()
        with pytest.raises(ValueError, match="symbol"):
            svc.analyze({})

    @patch.object(SwingPointService, '__init__', lambda self: None)
    def test_invalid_min_change(self):
        svc = SwingPointService()
        svc.validator = MagicMock()
        svc.validator.validate.return_value = {'valid': True}
        with pytest.raises(ValueError, match="min_change"):
            svc.analyze({'symbol': '600519', 'min_change': 50})

    def test_full_flow(self):
        """完整流程测试"""
        # 模拟 K 线：明显的波段走势
        prices = [100, 95, 90, 85, 80, 85, 90, 100, 110, 120,
                  115, 105, 95, 90, 95, 100, 110, 120, 130]
        mock_klines = _make_klines(prices)

        mock_repo = MagicMock()
        mock_repo.count_daily_klines.return_value = len(mock_klines)
        mock_repo.get_date_range.return_value = ('2025-01-01', '2025-01-19')
        mock_klines_df = MagicMock()
        mock_klines_df.__len__ = MagicMock(return_value=len(mock_klines))
        mock_klines_df.to_dicts.return_value = mock_klines
        mock_repo.get_daily_klines.return_value = mock_klines_df

        validator = StockCodeValidator(kline_repo=mock_repo)
        svc = SwingPointService(kline_repo=mock_repo, validator=validator)
        result = svc.analyze({
            'symbol': '600519',
            'start_date': '2025-01-01',
            'end_date': '2025-01-19',
            'min_change': 10,
        })

        assert result['symbol'] == '600519'
        assert 'swing_points' in result
        assert 'trades' in result
        assert 'summary' in result
        assert result['kline_count'] == 19

        # 应该有拐点
        assert len(result['swing_points']) > 0

        # 类型交替
        pts = result['swing_points']
        for i in range(1, len(pts)):
            assert pts[i]['type'] != pts[i-1]['type']
