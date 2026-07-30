"""StockProfileClassifier 单元测试"""
import pytest
from application.services.scoring.stock_profile_classifier import StockProfileClassifier


def _q(values):
    return [{'gross_margin': v} for v in values]


def _fund(pe=None, roe=None, gross_margin=None, revenue_growth=None):
    return {'pe_ratio': pe, 'roe': roe, 'gross_margin': gross_margin,
            'revenue_growth': revenue_growth}


def _run(symbols, quarterly_map, fundamentals_map):
    c = StockProfileClassifier()
    return c.classify_batch(symbols, quarterly_map, fundamentals_map)


class TestCyclical:
    def test_high_earnings_volatility_is_cyclical(self):
        """毛利率波动 ≥8pp → cyclical，且优先级高于 value 特征"""
        # 毛利率 10~30 大幅摆动（pstdev=10）
        margins = _q([30, 10, 30, 10, 30, 10, 30, 10])
        result = _run(
            ['A'], {'A': margins},
            {'A': _fund(pe=8, roe=18, gross_margin=20, revenue_growth=5)})
        assert result['A']['profile'] == 'cyclical'
        assert '波动' in result['A']['reason']
        assert result['A']['signals']['earnings_volatility_pp'] >= 8.0


class TestGrowthValue:
    def test_growth_by_percentile(self):
        """成长强度池内前30% → growth"""
        symbols = ['G1', 'G2', 'N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7', 'N8']
        quarterly = {s: _q([30, 30, 30, 30]) for s in symbols}
        funds = {s: _fund(pe=40, roe=10, gross_margin=30, revenue_growth=2)
                 for s in symbols}
        funds['G1'] = _fund(pe=40, roe=10, gross_margin=50, revenue_growth=60)
        funds['G2'] = _fund(pe=40, roe=10, gross_margin=45, revenue_growth=50)
        result = _run(symbols, quarterly, funds)
        assert result['G1']['profile'] == 'growth'
        assert result['G2']['profile'] == 'growth'
        assert result['N1']['profile'] == 'balanced'

    def test_value_by_percentile(self):
        """价值强度池内前30% → value"""
        symbols = ['V1', 'V2', 'N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7', 'N8']
        quarterly = {s: _q([20, 20, 20, 20]) for s in symbols}
        funds = {s: _fund(pe=30, roe=8, gross_margin=20, revenue_growth=3)
                 for s in symbols}
        funds['V1'] = _fund(pe=5, roe=25, gross_margin=20, revenue_growth=3)
        funds['V2'] = _fund(pe=6, roe=20, gross_margin=20, revenue_growth=3)
        result = _run(symbols, quarterly, funds)
        assert result['V1']['profile'] == 'value'
        assert result['V2']['profile'] == 'value'


class TestFallback:
    def test_insufficient_quarters_balanced(self):
        """季度数据 <4 期 → balanced 并注明"""
        result = _run(['A'], {'A': _q([30, 28])}, {'A': _fund()})
        assert result['A']['profile'] == 'balanced'
        assert '不足' in result['A']['reason']

    def test_missing_fundamentals_no_crash(self):
        result = _run(['A'], {'A': _q([30, 30, 30, 30])}, {'A': None})
        assert result['A']['profile'] in ('balanced', 'cyclical')
