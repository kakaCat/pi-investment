"""
FundamentalScorer 单元测试
"""
import pytest
from application.services.scoring.fundamental_scorer import FundamentalScorer


class TestFundamentalScorer:
    """FundamentalScorer 测试套件"""

    def setup_method(self):
        """测试前准备"""
        self.scorer = FundamentalScorer()

    def test_score_returns_correct_structure(self):
        """测试返回结构正确"""
        data = {
            'pe': 15,
            'roe': 18,
            'gross_margin': 35,
            'debt_ratio': 30,
            'revenue_growth': 25
        }

        result = self.scorer.score(data)

        assert 'total' in result
        assert 'breakdown' in result
        assert isinstance(result['total'], float)
        assert isinstance(result['breakdown'], dict)

        # 验证所有子项都在 breakdown 中
        expected_keys = ['base', 'pe', 'roe', 'gross_margin', 'debt_ratio', 'revenue_growth', 'resonance']
        for key in expected_keys:
            assert key in result['breakdown']

    def test_score_range_valid(self):
        """测试评分范围在 0-100"""
        # 极端优秀数据
        excellent_data = {
            'pe': 8,
            'roe': 25,
            'gross_margin': 40,
            'debt_ratio': 20,
            'revenue_growth': 35
        }

        result = self.scorer.score(excellent_data)
        assert 0 <= result['total'] <= 100

        # 极端糟糕数据
        poor_data = {
            'pe': 80,
            'roe': -5,
            'gross_margin': 5,
            'debt_ratio': 80,
            'revenue_growth': -15
        }

        result = self.scorer.score(poor_data)
        assert 0 <= result['total'] <= 100

    def test_pe_undervalued_scoring(self):
        """测试 PE 低估评分"""
        # PE = 8（极度低估）
        data = {'pe': 8}
        result = self.scorer.score(data)
        assert result['breakdown']['pe'] == 20.0

        # PE = 12（低估）
        data = {'pe': 12}
        result = self.scorer.score(data)
        assert 15.0 <= result['breakdown']['pe'] <= 20.0

        # PE = 20（合理）
        data = {'pe': 20}
        result = self.scorer.score(data)
        assert result['breakdown']['pe'] == 10.0

    def test_pe_overvalued_scoring(self):
        """测试 PE 高估评分"""
        # PE = 35（略高估）
        data = {'pe': 35}
        result = self.scorer.score(data)
        assert -10.0 < result['breakdown']['pe'] < 10.0

        # PE = 50（高估）
        data = {'pe': 50}
        result = self.scorer.score(data)
        assert result['breakdown']['pe'] == -5.0  # 修正：PE=50 在 40-60 区间内

        # PE = 70（极度高估）
        data = {'pe': 70}
        result = self.scorer.score(data)
        assert result['breakdown']['pe'] == -20.0

    def test_pe_negative(self):
        """测试 PE 为负（亏损）"""
        data = {'pe': -5}
        result = self.scorer.score(data)
        assert result['breakdown']['pe'] == -20.0

    def test_roe_excellent_scoring(self):
        """测试 ROE 优秀评分"""
        # ROE = 25%（卓越）
        data = {'roe': 25}
        result = self.scorer.score(data)
        assert result['breakdown']['roe'] == 20.0

        # ROE = 18%（优秀）
        data = {'roe': 18}
        result = self.scorer.score(data)
        assert 12.0 < result['breakdown']['roe'] < 20.0

        # ROE = 12%（良好）
        data = {'roe': 12}
        result = self.scorer.score(data)
        assert 5.0 < result['breakdown']['roe'] < 12.0

    def test_roe_poor_scoring(self):
        """测试 ROE 较差评分"""
        # ROE = 3%（较差）
        data = {'roe': 3}
        result = self.scorer.score(data)
        assert result['breakdown']['roe'] == -10.0

        # ROE = -5%（亏损）
        data = {'roe': -5}
        result = self.scorer.score(data)
        assert result['breakdown']['roe'] == -20.0

    def test_gross_margin_scoring(self):
        """测试毛利率评分"""
        # 毛利率 < 10%
        data = {'gross_margin': 8}
        result = self.scorer.score(data)
        assert result['breakdown']['gross_margin'] == 0.0

        # 毛利率 15%
        data = {'gross_margin': 15}
        result = self.scorer.score(data)
        assert 0.0 < result['breakdown']['gross_margin'] < 5.0

        # 毛利率 25%
        data = {'gross_margin': 25}
        result = self.scorer.score(data)
        assert 5.0 < result['breakdown']['gross_margin'] < 10.0

        # 毛利率 > 30%
        data = {'gross_margin': 35}
        result = self.scorer.score(data)
        assert result['breakdown']['gross_margin'] == 15.0

    def test_debt_ratio_scoring(self):
        """测试负债率评分"""
        # 负债率 < 30%（低负债）
        data = {'debt_ratio': 25}
        result = self.scorer.score(data)
        assert result['breakdown']['debt_ratio'] == 15.0

        # 负债率 40%
        data = {'debt_ratio': 40}
        result = self.scorer.score(data)
        assert 10.0 < result['breakdown']['debt_ratio'] < 15.0

        # 负债率 60%
        data = {'debt_ratio': 60}
        result = self.scorer.score(data)
        assert 5.0 < result['breakdown']['debt_ratio'] < 10.0

        # 负债率 > 70%（高负债）
        data = {'debt_ratio': 80}
        result = self.scorer.score(data)
        assert result['breakdown']['debt_ratio'] == 0.0

    def test_revenue_growth_scoring(self):
        """测试营收增长率评分"""
        # 增长 < -10%（严重萎缩）
        data = {'revenue_growth': -15}
        result = self.scorer.score(data)
        assert result['breakdown']['revenue_growth'] == 0.0

        # 增长 -5%
        data = {'revenue_growth': -5}
        result = self.scorer.score(data)
        assert 0.0 < result['breakdown']['revenue_growth'] < 3.0

        # 增长 5%
        data = {'revenue_growth': 5}
        result = self.scorer.score(data)
        assert 3.0 < result['breakdown']['revenue_growth'] < 8.0

        # 增长 20%
        data = {'revenue_growth': 20}
        result = self.scorer.score(data)
        assert 8.0 < result['breakdown']['revenue_growth'] < 13.0

        # 增长 > 30%（高成长）
        data = {'revenue_growth': 35}
        result = self.scorer.score(data)
        assert result['breakdown']['revenue_growth'] == 15.0

    def test_resonance_value_profitability(self):
        """测试共振：价值 + 高盈利"""
        data = {
            'pe': 18,
            'roe': 20,
            'gross_margin': 25,
            'debt_ratio': 50,
            'revenue_growth': 10
        }

        result = self.scorer.score(data)
        # 应该触发价值+高盈利共振（+10分）
        assert result['breakdown']['resonance'] >= 10.0

    def test_resonance_quality_growth(self):
        """测试共振：优质成长"""
        data = {
            'pe': 25,
            'roe': 12,
            'gross_margin': 35,
            'debt_ratio': 50,
            'revenue_growth': 25
        }

        result = self.scorer.score(data)
        # 应该触发优质成长共振（+5分）
        assert result['breakdown']['resonance'] >= 5.0

    def test_resonance_stable_quality(self):
        """测试共振：稳健优质"""
        data = {
            'pe': 25,
            'roe': 18,
            'gross_margin': 25,
            'debt_ratio': 35,
            'revenue_growth': 10
        }

        result = self.scorer.score(data)
        # 应该触发稳健优质共振（+5分）
        assert result['breakdown']['resonance'] >= 5.0

    def test_resonance_multiple_rules(self):
        """测试共振：多个规则同时触发"""
        data = {
            'pe': 18,
            'roe': 20,
            'gross_margin': 35,
            'debt_ratio': 30,
            'revenue_growth': 25
        }

        result = self.scorer.score(data)
        # 应该触发多个共振规则（最多 15 分）
        assert result['breakdown']['resonance'] == 15.0

    def test_missing_fields(self):
        """测试缺失字段处理"""
        # 空数据
        data = {}
        result = self.scorer.score(data)
        assert result['total'] == 50.0  # 只有基础分

        # 部分数据
        data = {'pe': 15, 'roe': 18}
        result = self.scorer.score(data)
        assert result['breakdown']['gross_margin'] == 0.0
        assert result['breakdown']['debt_ratio'] == 0.0
        assert result['breakdown']['revenue_growth'] == 0.0

    def test_excellent_company(self):
        """测试优秀公司评分"""
        data = {
            'pe': 12,
            'roe': 22,
            'gross_margin': 38,
            'debt_ratio': 25,
            'revenue_growth': 28
        }

        result = self.scorer.score(data)
        # 优秀公司应该得高分
        assert result['total'] > 80

    def test_poor_company(self):
        """测试较差公司评分"""
        data = {
            'pe': 60,
            'roe': 3,
            'gross_margin': 8,
            'debt_ratio': 75,
            'revenue_growth': -12
        }

        result = self.scorer.score(data)
        # 较差公司应该得低分
        assert result['total'] < 40

    def test_average_company(self):
        """测试平均公司评分"""
        data = {
            'pe': 30,        # 略高估
            'roe': 8,        # 一般
            'gross_margin': 18,  # 一般
            'debt_ratio': 55,    # 中等
            'revenue_growth': 5  # 低增长
        }

        result = self.scorer.score(data)
        # 平均公司应该在中等偏上分数段
        assert 65 <= result['total'] <= 80
