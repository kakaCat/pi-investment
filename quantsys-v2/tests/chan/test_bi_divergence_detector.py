"""笔组背驰检测测试——围绕中枢的进入/离开笔组 MACD 面积比较

注意：MACD(12,26,9) 需 ~34 根预热，合成序列必须加 40 根前导，
否则 bi 跨度落在预热区（hist NaN→0），面积为 0 测试失效（首轮全挂教训）。
"""
from datetime import datetime, timedelta
import pytest

from domain.chan.types import KLine, Bi, FenXing
from domain.chan.bi_divergence_detector import BiDivergenceDetector

LEAD = 40  # MACD 预热前导


def _klines_from_closes(closes):
    """由收盘价序列构造 KLine 列表（open=昨收，high/low 包络 close）"""
    out = []
    prev = closes[0]
    for i, c in enumerate(closes):
        out.append(KLine(
            date=datetime(2026, 1, 1) + timedelta(days=i),
            open=prev, high=max(prev, c) + 0.01, low=min(prev, c) - 0.01,
            close=c, volume=1000.0, original_indices=[i],
        ))
        prev = c
    return out


def _down_bi(start_idx: int, end_idx: int, high: float, low: float) -> Bi:
    s = FenXing(type='top', index=start_idx, price=high,
                date=datetime(2026, 1, 1) + timedelta(days=start_idx), klines=[])
    e = FenXing(type='bottom', index=end_idx, price=low,
                date=datetime(2026, 1, 1) + timedelta(days=end_idx), klines=[])
    return Bi(direction='down', start_fenxing=s, end_fenxing=e,
              high=high, low=low, length=end_idx - start_idx + 1,
              price_change=(low - high) / high)


def _up_bi(start_idx: int, end_idx: int, low: float, high: float) -> Bi:
    s = FenXing(type='bottom', index=start_idx, price=low,
                date=datetime(2026, 1, 1) + timedelta(days=start_idx), klines=[])
    e = FenXing(type='top', index=end_idx, price=high,
                date=datetime(2026, 1, 1) + timedelta(days=end_idx), klines=[])
    return Bi(direction='up', start_fenxing=s, end_fenxing=e,
              high=high, low=low, length=end_idx - start_idx + 1,
              price_change=(high - low) / low)


class TestBottomDivergence:
    def test_bottom_divergence_weaker_second_drop(self):
        """第二段下跌更浅（|MACD 面积|更小）且价格新低 → 底背驰"""
        closes = ([100.0] * LEAD
                  + [100 - 1.5 * (i + 1) for i in range(20)]   # 急跌 100→70
                  + [70 + 1.5 * (i + 1) for i in range(10)]    # 反弹 70→85
                  + [85 - 0.85 * (i + 1) for i in range(20)])  # 缓跌 85→68（新低、面积更小）
        klines = _klines_from_closes(closes)
        enter = _down_bi(LEAD, LEAD + 19, high=100.0, low=70.0)
        leave = _down_bi(LEAD + 29, LEAD + 48, high=85.0, low=68.0)

        det = BiDivergenceDetector()
        assert det.is_bottom_divergence(enter, leave, klines) is True

    def test_no_divergence_when_second_drop_stronger(self):
        """第二段下跌更急（面积更大）→ 非背驰"""
        closes = ([100.0] * LEAD
                  + [100 - 0.5 * (i + 1) for i in range(20)]   # 缓跌
                  + [90 + 1.5 * (i + 1) for i in range(10)]    # 反弹
                  + [105 - 3.0 * (i + 1) for i in range(20)])  # 急跌
        klines = _klines_from_closes(closes)
        enter = _down_bi(LEAD, LEAD + 19, high=100.0, low=90.0)
        leave = _down_bi(LEAD + 29, LEAD + 48, high=105.0, low=48.0)

        det = BiDivergenceDetector()
        assert det.is_bottom_divergence(enter, leave, klines) is False


class TestTopDivergence:
    def test_top_divergence_weaker_second_rise(self):
        """第二段上涨更弱（面积更小）且价格新高 → 顶背驰"""
        closes = ([50.0] * LEAD
                  + [50 + 2.0 * (i + 1) for i in range(20)]    # 急涨 50→90
                  + [90 - 1.0 * (i + 1) for i in range(10)]    # 回落 90→80
                  + [80 + 0.6 * (i + 1) for i in range(20)])   # 缓涨 80→91.4（新高、面积更小）
        klines = _klines_from_closes(closes)
        enter = _up_bi(LEAD, LEAD + 19, low=50.0, high=90.0)
        leave = _up_bi(LEAD + 29, LEAD + 48, low=80.0, high=91.4)

        det = BiDivergenceDetector()
        assert det.is_top_divergence(enter, leave, klines) is True

    def test_no_top_divergence_when_stronger(self):
        """第二段上涨更急 → 非顶背驰"""
        closes = ([50.0] * LEAD
                  + [50 + 0.5 * (i + 1) for i in range(20)]
                  + [60 - 1.0 * (i + 1) for i in range(10)]
                  + [50 + 3.0 * (i + 1) for i in range(20)])
        klines = _klines_from_closes(closes)
        enter = _up_bi(LEAD, LEAD + 19, low=50.0, high=60.0)
        leave = _up_bi(LEAD + 29, LEAD + 48, low=50.0, high=107.0)

        det = BiDivergenceDetector()
        assert det.is_top_divergence(enter, leave, klines) is False
