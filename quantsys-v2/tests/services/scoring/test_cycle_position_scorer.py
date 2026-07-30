"""CyclePositionScorer 单元测试"""
import pytest
from application.services.scoring.cycle_position_scorer import CyclePositionScorer


def _margins(values):
    """构造季度毛利率列表（倒序，最新在前）"""
    return [{'gross_margin': v, 'report_date': f'2026-0{7-i}-01'}
            for i, v in enumerate(values)]


class TestMarginQoq:
    def test_two_quarters_expansion(self):
        """连续2季扩张 → +35"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([35, 32, 30, 28]),
                     'pct_from_52w_high': -0.4})
        assert r['breakdown']['margin_qoq'] == 35.0
        assert any('扩张' in x for x in r['reasons'])

    def test_two_quarters_contraction(self):
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([28, 30, 32, 35]),
                     'pct_from_52w_high': -0.4})
        assert r['breakdown']['margin_qoq'] == -35.0


class TestFromHigh:
    def test_priced_in_zone(self):
        """回撤 30-50% → +35（已定价区）"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([30, 30, 30, 30]),
                     'pct_from_52w_high': -0.38})
        assert r['breakdown']['from_52w_high'] == 35.0

    def test_near_high_warning(self):
        """距高点 <10% → -35（顶部警惕）"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([30, 30, 30, 30]),
                     'pct_from_52w_high': -0.05})
        assert r['breakdown']['from_52w_high'] == -35.0


class TestAlignment:
    def test_golden_pit(self):
        """盈利扩张+深跌 → 黄金坑 +30"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([35, 32, 30, 28]),
                     'pct_from_52w_high': -0.38})
        assert r['breakdown']['alignment'] == 30.0
        assert any('黄金坑' in x for x in r['reasons'])
        assert r['total'] == 100.0  # 50+35+35+30 clamp

    def test_top_trap(self):
        """盈利收缩+新高 → 顶部陷阱 -30"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([28, 30, 32, 35]),
                     'pct_from_52w_high': -0.05})
        assert r['breakdown']['alignment'] == -30.0
        assert any('顶部陷阱' in x for x in r['reasons'])
        assert r['total'] == 0.0  # 50-35-35-30 clamp


class TestInsufficientData:
    def test_insufficient_quarters_neutral(self):
        """季度数据 <4 期 → 中性 50 并注明"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([30, 28]),
                     'pct_from_52w_high': -0.3})
        assert r['total'] == 50.0
        assert any('不足' in x for x in r['reasons'])

    def test_missing_high_neutral(self):
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([30, 29, 28, 27]),
                     'pct_from_52w_high': None})
        assert r['total'] == 50.0
