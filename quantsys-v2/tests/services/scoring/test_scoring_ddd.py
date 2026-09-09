"""
评分系统单元测试

测试 DDD 架构的评分系统：
1. IndustryNeutralScorer: 行业中性化评分
2. SmoothScorer: 平滑化评分
3. CompositeScorer: 复合评分
4. ScoringEngine: 评分引擎
"""

import pytest
import math
from domain.scoring.models import (
    ScoreResult, ScoringContext, ScoreDimension, ScoringMethod
)
from domain.scoring.services import (
    IndustryNeutralScorer, SmoothScorer, CompositeScorer
)
from domain.scoring.ports import IndustryDataPort
from application.services.scoring.scoring_engine import ScoringEngine


class MockIndustryDataAdapter(IndustryDataPort):
    """模拟行业数据适配器"""
    
    def __init__(self):
        self.sector_map = {
            '600887': '食品饮料',
            '002463': '电子',
            '600519': '食品饮料',
            '000001': '银行',
        }
        self.sector_factors = {
            '食品饮料': {
                'pe': [20, 25, 30, 35, 40, 45, 50],
                'roe': [15, 18, 20, 22, 25, 28, 30],
                'revenue_growth': [5, 8, 10, 12, 15, 18, 20],
            },
            '电子': {
                'pe': [30, 40, 50, 60, 70, 80, 100],
                'roe': [10, 12, 15, 18, 20, 25, 30],
                'revenue_growth': [10, 15, 20, 25, 30, 40, 50],
            },
            '银行': {
                'pe': [4, 5, 6, 7, 8, 9, 10],
                'roe': [10, 11, 12, 13, 14, 15, 16],
                'revenue_growth': [2, 3, 4, 5, 6, 7, 8],
            },
        }
    
    def get_sector(self, symbol: str) -> str:
        return self.sector_map.get(symbol, '未知')
    
    def get_sector_stocks(self, sector: str):
        return [s for s, sec in self.sector_map.items() if sec == sector]
    
    def get_sector_factor_values(self, sector, factor_name, symbols=None):
        return self.sector_factors.get(sector, {}).get(factor_name, [])


class TestIndustryNeutralScorer:
    """测试行业中性化评分器"""
    
    @pytest.fixture
    def scorer(self):
        adapter = MockIndustryDataAdapter()
        return IndustryNeutralScorer(adapter)
    
    def test_calculate_percentile(self, scorer):
        """测试分位数计算"""
        # 值在列表中间
        percentile = scorer.calculate_percentile(30, [20, 25, 30, 35, 40])
        assert 0.4 <= percentile <= 0.6
        
        # 值最小
        percentile = scorer.calculate_percentile(10, [20, 25, 30, 35, 40])
        assert percentile == 0.0
        
        # 值最大
        percentile = scorer.calculate_percentile(50, [20, 25, 30, 35, 40])
        assert percentile == 1.0
        
        # 空列表
        percentile = scorer.calculate_percentile(30, [])
        assert percentile == 0.5
    
    def test_score_factor_reverse(self, scorer):
        """测试反向因子评分（PE）"""
        # 科技股 PE=50，在电子行业内排名靠前（前 20%）
        score = scorer.score_factor(
            symbol='002463',
            factor_name='pe',
            value=50,
            sector='电子',
            direction=-1,  # 反向
            weight=0.40
        )
        
        # PE=50 在 [30,40,50,60,70,80,100] 中排第 3/7 ≈ 0.43
        # 反向得分 = (1 - 0.43) * 100 ≈ 57
        assert 50 <= score.score <= 65
        assert score.percentile < 0.5  # 排名靠前
    
    def test_score_factor_forward(self, scorer):
        """测试正向因子评分（ROE）"""
        score = scorer.score_factor(
            symbol='600887',
            factor_name='roe',
            value=25,
            sector='食品饮料',
            direction=1,  # 正向
            weight=0.30
        )
        
        # ROE=25 在 [15,18,20,22,25,28,30] 中排第 5/7 ≈ 0.71
        # 正向得分 = 0.71 * 100 ≈ 71
        assert 65 <= score.score <= 75
        assert score.percentile > 0.5  # 排名靠后
    
    def test_score_fundamental(self, scorer):
        """测试基本面评分"""
        context = ScoringContext(
            symbol='002463',
            sector='电子',
            factors={
                'pe': 50,
                'roe': 20,
                'revenue_growth': 30,
            }
        )
        
        scores = scorer.score_fundamental(context)
        
        assert 'pe' in scores
        assert 'roe' in scores
        assert 'revenue_growth' in scores
        
        # 科技股 PE=50 应该得分不低（行业内相对）
        assert scores['pe'].score > 40


class TestSmoothScorer:
    """测试平滑化评分器"""
    
    @pytest.fixture
    def scorer(self):
        return SmoothScorer()
    
    def test_tanh_score(self, scorer):
        """测试 tanh 平滑评分"""
        # 中心点
        assert scorer.tanh_score(0, scale=50, max_score=10) == 0
        
        # 正向
        score_pos = scorer.tanh_score(0.1, scale=50, max_score=10)
        assert 0 < score_pos < 10
        
        # 负向
        score_neg = scorer.tanh_score(-0.1, scale=50, max_score=10)
        assert -10 < score_neg < 0
        
        # 对称性
        assert abs(score_pos + score_neg) < 0.01
    
    def test_sigmoid_score(self, scorer):
        """测试 sigmoid 平滑评分"""
        # 中心点
        score_center = scorer.sigmoid_score(15, center=15, scale=5, max_score=15)
        assert abs(score_center - 7.5) < 0.1
        
        # 正向
        score_pos = scorer.sigmoid_score(25, center=15, scale=5, max_score=15)
        assert score_pos > score_center
        
        # 负向
        score_neg = scorer.sigmoid_score(5, center=15, scale=5, max_score=15)
        assert score_neg < score_center
    
    def test_score_macd_smooth(self, scorer):
        """测试 MACD 平滑评分"""
        # 金叉（hist > 0）
        factors_golden = {'macd': 0.05, 'macd_signal': 0.03}
        score_golden = scorer.score_macd_smooth(factors_golden)
        assert 0 < score_golden <= 10
        
        # 死叉（hist < 0）
        factors_death = {'macd': 0.02, 'macd_signal': 0.03}
        score_death = scorer.score_macd_smooth(factors_death)
        assert -10 <= score_death < 0
        
        # 中性（hist = 0）
        factors_neutral = {'macd': 0.03, 'macd_signal': 0.03}
        score_neutral = scorer.score_macd_smooth(factors_neutral)
        assert abs(score_neutral) < 0.01
        
        # 平滑性：小幅变化不会导致评分突变
        factors_small_change = {'macd': 0.031, 'macd_signal': 0.03}
        score_small = scorer.score_macd_smooth(factors_small_change)
        assert abs(score_small) < 1  # 变化很小
    
    def test_score_rsi_smooth(self, scorer):
        """测试 RSI 平滑评分"""
        # 超卖区（RSI=10）
        score_oversold = scorer.score_rsi_smooth(10)
        assert 10 <= score_oversold <= 15
        
        # 中性区（RSI=50）
        score_neutral = scorer.score_rsi_smooth(50)
        assert score_neutral == 0
        
        # 超买区（RSI=90）
        score_overbought = scorer.score_rsi_smooth(90)
        assert -15 <= score_overbought <= -10


class TestScoringEngine:
    """测试评分引擎"""
    
    @pytest.fixture
    def engine(self):
        adapter = MockIndustryDataAdapter()
        return ScoringEngine(adapter)
    
    def test_score_stock(self, engine):
        """测试单只股票评分"""
        factors = {
            'pe': 50,
            'roe': 20,
            'revenue_growth': 30,
            'rsi': 55,
            'macd': 0.05,
            'macd_signal': 0.03,
        }
        
        result = engine.score_stock('002463', factors)
        
        assert isinstance(result, ScoreResult)
        assert result.symbol == '002463'
        assert 0 <= result.total_score <= 100
        assert ScoreDimension.FUNDAMENTAL in result.dimension_scores
        assert ScoreDimension.TECHNICAL in result.dimension_scores
    
    def test_score_batch(self, engine):
        """测试批量评分"""
        factors_dict = {
            '600887': {
                'pe': 30,
                'roe': 22,
                'revenue_growth': 12,
                'rsi': 50,
                'macd': 0.03,
                'macd_signal': 0.02,
            },
            '002463': {
                'pe': 50,
                'roe': 20,
                'revenue_growth': 30,
                'rsi': 55,
                'macd': 0.05,
                'macd_signal': 0.03,
            },
        }
        
        results = engine.score_batch(['600887', '002463'], factors_dict)
        
        assert len(results) == 2
        assert all(isinstance(r, ScoreResult) for r in results)
    
    def test_compare_stocks(self, engine):
        """测试股票比较"""
        factors_dict = {
            '600887': {
                'pe': 30,
                'roe': 22,
                'revenue_growth': 12,
            },
            '002463': {
                'pe': 50,
                'roe': 20,
                'revenue_growth': 30,
            },
        }
        
        comparison = engine.compare_stocks(['600887', '002463'], factors_dict)
        
        assert 'ranking' in comparison
        assert 'details' in comparison
        assert len(comparison['ranking']) == 2
        
        # 按总分排序
        scores = [r['total_score'] for r in comparison['ranking']]
        assert scores == sorted(scores, reverse=True)
