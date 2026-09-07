"""
TechnicalScorer 单元测试
"""

import pytest
from application.services.scoring.technical_scorer import TechnicalScorer


class TestTechnicalScorer:
    """TechnicalScorer 单元测试"""

    def setup_method(self):
        """每个测试前初始化"""
        self.scorer = TechnicalScorer()

    def test_score_returns_correct_structure(self):
        """测试返回结构正确"""
        factors = {
            'rsi': 50,
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_prev': 0.2,
            'macd_signal_prev': 0.4,
            'adx': 30,
            'volume_ratio_5d': 1.2,
        }

        result = self.scorer.score(factors)

        # 验证结构
        assert 'total' in result
        assert 'breakdown' in result
        assert isinstance(result['total'], (int, float))
        assert isinstance(result['breakdown'], dict)

        # 验证 breakdown 包含所有子项
        assert 'base' in result['breakdown']
        assert 'rsi' in result['breakdown']
        assert 'macd' in result['breakdown']
        assert 'adx' in result['breakdown']
        assert 'volume' in result['breakdown']
        assert 'resonance' in result['breakdown']

    def test_score_range_valid(self):
        """测试评分范围在 0-100 之间"""
        # 极端超卖情况
        factors_oversold = {
            'rsi': 10,
            'macd': 1.0,
            'macd_signal': 0.1,
            'macd_prev': 0.1,
            'macd_signal_prev': 0.5,
            'adx': 50,
            'volume_ratio_5d': 3.0,
        }

        result = self.scorer.score(factors_oversold)
        assert 0 <= result['total'] <= 100

        # 极端超买情况
        factors_overbought = {
            'rsi': 90,
            'macd': -0.5,
            'macd_signal': 0.5,
            'macd_prev': 0.5,
            'macd_signal_prev': 0.3,
            'adx': 10,
            'volume_ratio_5d': 0.5,
        }

        result = self.scorer.score(factors_overbought)
        assert 0 <= result['total'] <= 100

    def test_rsi_oversold_scoring(self):
        """测试 RSI 超卖评分"""
        # RSI=0 应该得满分 20 分
        score_0 = self.scorer._score_rsi(0)
        assert score_0 == 20

        # RSI=15 应该得 10 分
        score_15 = self.scorer._score_rsi(15)
        assert abs(score_15 - 10) < 0.1

        # RSI=30 应该得 0 分
        score_30 = self.scorer._score_rsi(30)
        assert score_30 == 0

    def test_rsi_overbought_scoring(self):
        """测试 RSI 超买评分"""
        # RSI=70 应该得 0 分
        score_70 = self.scorer._score_rsi(70)
        assert score_70 == 0

        # RSI=85 应该得 -10 分
        score_85 = self.scorer._score_rsi(85)
        assert abs(score_85 - (-10)) < 0.1

        # RSI=100 应该得 -20 分
        score_100 = self.scorer._score_rsi(100)
        assert score_100 == -20

    def test_rsi_neutral_scoring(self):
        """测试 RSI 中性区间评分"""
        # 40-60 之间应该得 5 分
        for rsi in [40, 45, 50, 55, 60]:
            score = self.scorer._score_rsi(rsi)
            assert score == 5

        # 35 和 65 不在中性区间
        assert self.scorer._score_rsi(35) != 5
        assert self.scorer._score_rsi(65) != 5

    def test_macd_golden_cross(self):
        """测试 MACD 金叉评分"""
        factors = {
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_prev': 0.2,
            'macd_signal_prev': 0.4,  # 金叉
        }

        score = self.scorer._score_macd(factors)
        assert score > 10  # 至少基础分 10
        assert score <= 20  # 最多 20 分

    def test_macd_dead_cross(self):
        """测试 MACD 死叉评分"""
        factors = {
            'macd': 0.2,
            'macd_signal': 0.5,
            'macd_prev': 0.4,
            'macd_signal_prev': 0.3,  # 死叉
        }

        score = self.scorer._score_macd(factors)
        assert score < 0  # 应该扣分
        assert score >= -15

    def test_macd_no_cross(self):
        """测试 MACD 无交叉"""
        factors = {
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_prev': 0.4,
            'macd_signal_prev': 0.2,  # 持续金叉状态，无新交叉
        }

        score = self.scorer._score_macd(factors)
        assert score == 0

    def test_adx_weak_trend(self):
        """测试弱趋势 ADX 评分"""
        score_20 = self.scorer._score_adx(20)
        assert score_20 == 0

        score_25 = self.scorer._score_adx(25)
        assert score_25 == 0

    def test_adx_strong_trend(self):
        """测试强趋势 ADX 评分"""
        score_30 = self.scorer._score_adx(30)
        assert 0 < score_30 < 15

        score_50 = self.scorer._score_adx(50)
        assert score_50 == 15

        score_70 = self.scorer._score_adx(70)
        assert score_70 == 15  # 最多 15 分

    def test_volume_scoring(self):
        """测试成交量评分"""
        # 放量
        factors_high = {'volume_ratio_5d': 2.0}
        score_high = self.scorer._score_volume(factors_high)
        assert score_high > 0
        assert score_high <= 20

        # 缩量
        factors_low = {'volume_ratio_5d': 0.7}
        score_low = self.scorer._score_volume(factors_low)
        assert score_low == -10

        # 正常
        factors_normal = {'volume_ratio_5d': 1.2}
        score_normal = self.scorer._score_volume(factors_normal)
        assert score_normal == 0

    def test_resonance_rsi_macd(self):
        """测试 RSI 超卖 + MACD 金叉共振"""
        factors = {
            'rsi': 25,  # 超卖
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_prev': 0.2,
            'macd_signal_prev': 0.4,  # 金叉
            'adx': 20,
            'volume_ratio_5d': 1.0,
        }

        breakdown = {
            'macd': 15,  # 金叉得分 > 10
        }

        resonance = self.scorer._calculate_resonance(factors, breakdown)
        assert resonance == 10  # 应该触发规则 1

    def test_resonance_volume_adx(self):
        """测试放量 + 强趋势共振"""
        factors = {
            'rsi': 50,
            'macd': 0.5,
            'macd_signal': 0.3,
            'adx': 30,  # 强趋势
            'volume_ratio_5d': 2.0,  # 放量
        }

        breakdown = {'macd': 5}

        resonance = self.scorer._calculate_resonance(factors, breakdown)
        assert resonance == 5  # 应该触发规则 2

    def test_resonance_both_rules(self):
        """测试两个共振规则同时触发"""
        factors = {
            'rsi': 25,  # 超卖
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_prev': 0.2,
            'macd_signal_prev': 0.4,  # 金叉
            'adx': 30,  # 强趋势
            'volume_ratio_5d': 2.0,  # 放量
        }

        breakdown = {'macd': 15}

        resonance = self.scorer._calculate_resonance(factors, breakdown)
        assert resonance == 15  # 10 + 5，最多 15 分

    def test_resonance_no_trigger(self):
        """测试共振规则未触发"""
        factors = {
            'rsi': 50,  # 非超卖
            'macd': 0.5,
            'macd_signal': 0.3,
            'adx': 20,  # 弱趋势
            'volume_ratio_5d': 1.0,  # 正常量
        }

        breakdown = {'macd': 5}

        resonance = self.scorer._calculate_resonance(factors, breakdown)
        assert resonance == 0
