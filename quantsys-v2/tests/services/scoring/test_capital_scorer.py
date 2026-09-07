"""CapitalScorer 单元测试

注意：stock_fund_flow 金额字段单位为【万元】（见 fund_flow_repository docstring），
scorer 内部 ×1e4 换算为元后与 market_cap（元）比较。
"""
import pytest
from application.services.scoring.capital_scorer import CapitalScorer


def _flows(amounts_wan):
    """构造资金流列表（倒序，最新在前），amounts 单位【万元】"""
    return [{'main_net_inflow': a, 'trade_date': f'2026-07-{29-i}'}
            for i, a in enumerate(amounts_wan)]


class TestMainInflow:
    def test_strong_inflow_full_score(self):
        """5日累计净流入达流通市值2% → +30"""
        s = CapitalScorer()
        # 市值 100 亿元，5 日每日流入 4000 万元 = 累计 2 亿元 = 2%
        result = s.score({
            'fund_flows': _flows([4000] * 5),
            'market_cap': 1e10,
            'volume_ratio_5d': 1.0, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert result['breakdown']['main_inflow'] == 30.0
        assert any('净流入' in r for r in result['reasons'])

    def test_outflow_negative_score(self):
        """连续净流出 → 负分"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([-4000] * 5),
            'market_cap': 1e10,
            'volume_ratio_5d': 1.0, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert result['breakdown']['main_inflow'] == -30.0

    def test_outlier_winsorized(self):
        """单日净流入 > 流通市值20% → 截断并标记"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([1e9, 0, 0, 0, 0]),  # 10亿万元=1e13元，明显异常
            'market_cap': 1e10,
            'volume_ratio_5d': 1.0, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert result['breakdown']['main_inflow'] <= 30.0
        assert any('截断' in r for r in result['reasons'])


class TestAcceleration:
    def test_acceleration_bonus(self):
        """近2日均值 > 前3日均值 → +20"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([500, 500, 100, 100, 100]),
            'market_cap': 1e10,
            'volume_ratio_5d': 1.0, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert result['breakdown']['acceleration'] == 20.0
        assert any('加速' in r for r in result['reasons'])

    def test_insufficient_flows_no_accel(self):
        """资金流不足5条 → 加速分 0"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([500, 500]),
            'market_cap': 1e10,
            'volume_ratio_5d': 1.0, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert result['breakdown']['acceleration'] == 0.0


class TestDegradation:
    def test_no_flows_degrades_to_volume(self):
        """无资金流 → 降级纯量能，reasons 注明"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': [],
            'market_cap': 1e10,
            'volume_ratio_5d': 2.0, 'volume_ma5': 200, 'volume_ma20': 100,
        })
        assert result['breakdown'].get('main_inflow') is None
        assert result['breakdown']['volume_ratio'] == 20.0
        assert result['breakdown']['volume_trend'] == 15.0
        assert any('资金流数据缺失' in r for r in result['reasons'])
        assert result['total'] == 85.0  # 50 + 20 + 15


class TestResonance:
    def test_resonance(self):
        """主力流入+放量+上涨 → +15"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([100] * 5),
            'market_cap': 1e10,
            'volume_ratio_5d': 2.0, 'volume_ma5': 0, 'volume_ma20': 1,
            'change_pct': 2.5,
        })
        assert result['breakdown']['resonance'] == 15.0
        assert any('共振' in r for r in result['reasons'])

    def test_no_resonance_when_price_falls(self):
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([100] * 5),
            'market_cap': 1e10,
            'volume_ratio_5d': 2.0, 'volume_ma5': 0, 'volume_ma20': 1,
            'change_pct': -1.0,
        })
        assert result['breakdown']['resonance'] == 0.0


class TestTotalRange:
    def test_total_clamped(self):
        """总分 clamp 在 0-100"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([-4000] * 5),
            'market_cap': 1e10,
            'volume_ratio_5d': 0.5, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert 0 <= result['total'] <= 100
