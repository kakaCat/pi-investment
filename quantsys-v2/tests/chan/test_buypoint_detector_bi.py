"""买卖点检测器（笔中枢版）测试——6 类买卖点触发与不触发"""
from datetime import datetime, timedelta
from unittest.mock import patch
import pytest

from domain.chan.types import Bi, FenXing, BiZhongShu, KLine
from domain.chan.buypoint_detector import BuyPointDetector


def _fx(idx, price, ftype):
    return FenXing(type=ftype, index=idx, price=price,
                   date=datetime(2026, 1, 1) + timedelta(days=idx), klines=[])


def _bi(direction, start_idx, end_idx, low, high):
    if direction == 'up':
        s, e = _fx(start_idx, low, 'bottom'), _fx(end_idx, high, 'top')
    else:
        s, e = _fx(start_idx, high, 'top'), _fx(end_idx, low, 'bottom')
    return Bi(direction=direction, start_fenxing=s, end_fenxing=e,
              high=high, low=low, length=end_idx - start_idx + 1,
              price_change=(e.price - s.price) / s.price)


def _zs(zg, zd, start_bi_idx, end_bi_idx, bis):
    return BiZhongShu(
        zg=zg, zd=zd,
        gg=max(b.high for b in bis[start_bi_idx:end_bi_idx + 1]),
        dd=min(b.low for b in bis[start_bi_idx:end_bi_idx + 1]),
        start_bi_idx=start_bi_idx, end_bi_idx=end_bi_idx,
        bis=bis[start_bi_idx:end_bi_idx + 1],
    )


def _klines(n=60):
    return [KLine(date=datetime(2026, 1, 1) + timedelta(days=i),
                  open=10.0, high=10.1, low=9.9, close=10.0,
                  volume=1000.0, original_indices=[i]) for i in range(n)]


class TestFirstBuySell:
    def test_first_buy_on_bottom_divergence(self):
        """中枢后离开下跌笔背驰 → 1买"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),    # 0: 进入下跌笔
            _bi('up', 5, 10, low=9.0, high=11.0),     # 1-3: 中枢3笔
            _bi('down', 10, 15, low=9.5, high=10.5),  # 2
            _bi('up', 15, 20, low=9.8, high=10.2),    # 3
            _bi('down', 20, 25, low=7.5, high=10.0),  # 4: 离开下跌笔（新低）
        ]
        zs = [_zs(zg=10.5, zd=9.8, start_bi_idx=1, end_bi_idx=3, bis=bis)]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=True):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        first_buys = [p for p in pts if p.type == '1买']
        assert len(first_buys) == 1
        assert first_buys[0].price == pytest.approx(7.5)
        assert first_buys[0].confidence == 0.9

    def test_no_first_buy_without_divergence(self):
        """背驰不成立 → 无 1买"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),
            _bi('up', 5, 10, low=9.0, high=11.0),
            _bi('down', 10, 15, low=9.5, high=10.5),
            _bi('up', 15, 20, low=9.8, high=10.2),
            _bi('down', 20, 25, low=7.5, high=10.0),
        ]
        zs = [_zs(zg=10.5, zd=9.8, start_bi_idx=1, end_bi_idx=3, bis=bis)]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=False):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        assert [p for p in pts if p.type == '1买'] == []

    def test_first_buy_fallback_without_zhongshu(self):
        """无中枢：最近两条下跌笔比较，背驰 → 1买"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),
            _bi('up', 5, 10, low=9.0, high=11.0),
            _bi('down', 10, 15, low=7.5, high=10.5),
        ]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=True):
            pts = BuyPointDetector().detect(bis, [], _klines())
        assert len([p for p in pts if p.type == '1买']) == 1

    def test_first_sell_symmetric(self):
        """中枢后离开上涨笔顶背驰 → 1卖"""
        bis = [
            _bi('up', 0, 5, low=8.0, high=12.0),
            _bi('down', 5, 10, low=9.0, high=11.0),
            _bi('up', 10, 15, low=9.5, high=10.5),
            _bi('down', 15, 20, low=9.8, high=10.2),
            _bi('up', 20, 25, low=10.0, high=13.0),   # 离开上涨笔（新高）
        ]
        zs = [_zs(zg=10.2, zd=9.5, start_bi_idx=1, end_bi_idx=3, bis=bis)]
        with patch.object(BuyPointDetector, '_is_top_div', return_value=True):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        sells = [p for p in pts if p.type == '1卖']
        assert len(sells) == 1
        assert sells[0].price == pytest.approx(13.0)


class TestSecondPoints:
    def test_second_buy_holds_above_first_low(self):
        """1买后回抽不破前低 → 2买"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),
            _bi('down', 5, 10, low=7.0, high=10.0),   # 1买在此末端（低 7.0）
            _bi('up', 10, 15, low=7.2, high=9.5),     # 反弹笔
            _bi('down', 15, 20, low=7.3, high=9.0),   # 回抽，低点 7.3 > 7.0
        ]
        # 选择性 patch：只对 (bi0→bi1) 这对报背驰（bi3 低点 7.3 非新低，真实也不背驰）
        with patch.object(BuyPointDetector, '_is_bottom_div',
                          side_effect=lambda e, l, k: l.low == 7.0):
            pts = BuyPointDetector().detect(bis, [], _klines())
        second = [p for p in pts if p.type == '2买']
        assert len(second) == 1
        assert second[0].price == pytest.approx(7.3)
        assert second[0].confidence == 0.7

    def test_no_second_buy_when_breaks_first_low(self):
        """回抽跌破 1买低点 → 无 2买"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),
            _bi('down', 5, 10, low=7.0, high=10.0),
            _bi('up', 10, 15, low=7.2, high=9.5),
            _bi('down', 15, 20, low=6.8, high=9.0),   # 6.8 < 7.0 破前低
        ]
        with patch.object(BuyPointDetector, '_is_bottom_div',
                          side_effect=lambda e, l, k: l.low == 7.0):
            pts = BuyPointDetector().detect(bis, [], _klines())
        assert [p for p in pts if p.type == '2买'] == []


class TestThirdPoints:
    def test_third_buy_pullback_stays_above_zg(self):
        """上笔离开中枢（>ZG），回抽低点 > ZG → 3买"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=11.0),    # 0-2: 中枢
            _bi('up', 5, 10, low=9.5, high=10.5),
            _bi('down', 10, 15, low=9.2, high=10.8),
            _bi('up', 15, 20, low=10.0, high=12.5),   # 3: 离开（12.5 > ZG 10.5）
            _bi('down', 20, 25, low=10.6, high=12.0),  # 4: 回抽 10.6 > ZG 10.5
        ]
        zs = [_zs(zg=10.5, zd=9.5, start_bi_idx=0, end_bi_idx=2, bis=bis)]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=False), \
             patch.object(BuyPointDetector, '_is_top_div', return_value=False):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        third = [p for p in pts if p.type == '3买']
        assert len(third) == 1
        assert third[0].price == pytest.approx(10.6)
        assert third[0].confidence == 0.5

    def test_no_third_buy_when_pullback_enters_zhongshu(self):
        """回抽落入中枢（低点 ≤ ZG）→ 无 3买"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=11.0),
            _bi('up', 5, 10, low=9.5, high=10.5),
            _bi('down', 10, 15, low=9.2, high=10.8),
            _bi('up', 15, 20, low=10.0, high=12.5),
            _bi('down', 20, 25, low=10.2, high=12.0),  # 10.2 < ZG 10.5 落入
        ]
        zs = [_zs(zg=10.5, zd=9.5, start_bi_idx=0, end_bi_idx=2, bis=bis)]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=False), \
             patch.object(BuyPointDetector, '_is_top_div', return_value=False):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        assert [p for p in pts if p.type == '3买'] == []

    def test_third_sell_symmetric(self):
        """下笔跌破中枢（<ZD），回拉高点 < ZD → 3卖"""
        bis = [
            _bi('up', 0, 5, low=9.0, high=11.0),
            _bi('down', 5, 10, low=9.5, high=10.5),
            _bi('up', 10, 15, low=9.2, high=10.8),
            _bi('down', 15, 20, low=8.0, high=10.0),   # 跌破（8.0 < ZD 9.2）
            _bi('up', 20, 25, low=8.5, high=9.0),      # 回拉 9.0 < ZD 9.2
        ]
        zs = [_zs(zg=10.8, zd=9.2, start_bi_idx=0, end_bi_idx=2, bis=bis)]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=False), \
             patch.object(BuyPointDetector, '_is_top_div', return_value=False):
            pts = BuyPointDetector().detect(bis, zs, _klines())
        sells = [p for p in pts if p.type == '3卖']
        assert len(sells) == 1
        assert sells[0].price == pytest.approx(9.0)


class TestEnableFilter:
    def test_enable_types_filter(self):
        """enable_types 过滤生效"""
        bis = [
            _bi('down', 0, 5, low=8.0, high=12.0),
            _bi('up', 5, 10, low=9.0, high=11.0),
            _bi('down', 10, 15, low=7.5, high=10.5),
        ]
        with patch.object(BuyPointDetector, '_is_bottom_div', return_value=True):
            pts = BuyPointDetector().detect(bis, [], _klines(), enable_types=['2买'])
        assert pts == []
