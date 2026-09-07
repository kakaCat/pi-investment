"""笔中枢识别器测试——3 笔重叠成中枢、延续、独立多中枢"""
from datetime import datetime, timedelta
import pytest

from domain.chan.types import Bi, FenXing
from domain.chan.bi_zhongshu_identifier import BiZhongShuIdentifier


def _fx(idx: int, price: float, ftype: str) -> FenXing:
    return FenXing(type=ftype, index=idx, price=price,
                   date=datetime(2026, 1, 1) + timedelta(days=idx), klines=[])


def _bi(direction: str, start_idx: int, end_idx: int,
        low: float, high: float) -> Bi:
    """direction='up': 底→顶；'down': 顶→底"""
    if direction == 'up':
        s, e = _fx(start_idx, low, 'bottom'), _fx(end_idx, high, 'top')
    else:
        s, e = _fx(start_idx, high, 'top'), _fx(end_idx, low, 'bottom')
    return Bi(direction=direction, start_fenxing=s, end_fenxing=e,
              high=high, low=low, length=end_idx - start_idx + 1,
              price_change=(e.price - s.price) / s.price)


class TestBiZhongShuIdentifier:
    def test_three_overlapping_bis_form_zhongshu(self):
        """下上下 3 笔重叠 → 中枢成立，ZG=min(高点), ZD=max(低点)"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=11.0),
            _bi('up', 5, 10, low=9.5, high=10.5),
            _bi('down', 10, 15, low=9.2, high=10.8),
        ]
        result = BiZhongShuIdentifier().identify(bis)
        assert len(result) == 1
        zs = result[0]
        assert zs.zg == pytest.approx(10.5)   # min(11.0, 10.5, 10.8)
        assert zs.zd == pytest.approx(9.5)    # max(9.0, 9.5, 9.2)
        assert zs.gg == pytest.approx(11.0)
        assert zs.dd == pytest.approx(9.0)
        assert zs.bi_count == 3

    def test_no_overlap_no_zhongshu(self):
        """3 笔无重叠（ZD > ZG）→ 不成立"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=10.0),
            _bi('up', 5, 10, low=9.5, high=12.0),
            _bi('down', 10, 15, low=11.0, high=13.0),
        ]
        assert BiZhongShuIdentifier().identify(bis) == []

    def test_extension_merges_overlapping_bis(self):
        """第 4 笔仍与 [ZD, ZG] 重叠 → 并入中枢；第 5 笔完全脱离 → 中枢结束"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=11.0),
            _bi('up', 5, 10, low=9.5, high=10.5),
            _bi('down', 10, 15, low=9.2, high=10.8),
            _bi('up', 15, 20, low=9.6, high=10.4),   # 仍重叠 → 并入
            _bi('down', 20, 25, low=7.0, high=8.0),  # 完全在 ZD 下 → 结束
        ]
        result = BiZhongShuIdentifier().identify(bis)
        assert len(result) == 1
        assert result[0].bi_count == 4
        assert result[0].zg == pytest.approx(10.5)  # ZG/ZD 由前 3 笔锁定，不随延续改变
        assert result[0].zd == pytest.approx(9.5)

    def test_two_independent_zhongshus(self):
        """两组重叠笔 → 两个中枢"""
        bis = [
            _bi('down', 0, 5, low=9.0, high=11.0),
            _bi('up', 5, 10, low=9.5, high=10.5),
            _bi('down', 10, 15, low=9.2, high=10.8),
            _bi('up', 15, 20, low=14.0, high=16.0),   # 脱离中枢1
            _bi('down', 20, 25, low=14.5, high=15.5),
            _bi('up', 25, 30, low=14.2, high=15.8),
            _bi('down', 30, 35, low=14.4, high=15.6),
        ]
        result = BiZhongShuIdentifier().identify(bis)
        assert len(result) == 2
        assert result[1].zg == pytest.approx(15.5)
        assert result[1].zd == pytest.approx(14.5)  # max(14.5, 14.2, 14.4)

    def test_less_than_3_bis(self):
        assert BiZhongShuIdentifier().identify([]) == []
        assert BiZhongShuIdentifier().identify([_bi('up', 0, 5, 9.0, 10.0)]) == []
