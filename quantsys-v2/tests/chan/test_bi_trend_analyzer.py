"""走势类型分析（笔中枢版）测试"""
from datetime import datetime, timedelta
import pytest

from domain.chan.types import Bi, FenXing, BiZhongShu
from domain.chan.bi_trend_analyzer import BiTrendAnalyzer


def _fx(idx, price, ftype):
    return FenXing(type=ftype, index=idx, price=price,
                   date=datetime(2026, 1, 1) + timedelta(days=idx), klines=[])


def _bi(direction, start_idx, end_idx, low, high):
    if direction == 'up':
        s, e = _fx(start_idx, low, 'bottom'), _fx(end_idx, high, 'top')
    else:
        s, e = _fx(start_idx, high, 'top'), _fx(end_idx, low, 'bottom')
    return Bi(direction=direction, start_fenxing=s, end_fenxing=e,
              high=high, low=low, length=1, price_change=0.0)


def _zs(zg, zd, bis):
    return BiZhongShu(zg=zg, zd=zd, gg=zg, dd=zd,
                      start_bi_idx=0, end_bi_idx=2, bis=bis)


class TestBiTrend:
    def test_two_rising_zhongshus_is_uptrend(self):
        bis = [_bi('up', 0, 5, 9, 10)] * 3
        zs = [_zs(10.5, 9.5, bis), _zs(13.0, 12.0, bis)]
        assert BiTrendAnalyzer().analyze(bis, zs) == '上涨'

    def test_two_falling_zhongshus_is_downtrend(self):
        bis = [_bi('down', 0, 5, 9, 10)] * 3
        zs = [_zs(13.0, 12.0, bis), _zs(10.5, 9.5, bis)]
        assert BiTrendAnalyzer().analyze(bis, zs) == '下跌'

    def test_single_zhongshu_is_consolidation(self):
        bis = [_bi('up', 0, 5, 9, 10)] * 3
        assert BiTrendAnalyzer().analyze(bis, [_zs(10.5, 9.5, bis)]) == '盘整'

    def test_no_zhongshu_fallback_to_bi_extremes(self):
        up_bis = [_bi('up', 0, 5, 9.0, 10.0), _bi('up', 10, 15, 10.5, 12.0)]
        assert BiTrendAnalyzer().analyze(up_bis, []) == '上涨'
        down_bis = [_bi('down', 0, 5, 9.0, 12.0), _bi('down', 10, 15, 7.0, 10.0)]
        assert BiTrendAnalyzer().analyze(down_bis, []) == '下跌'
