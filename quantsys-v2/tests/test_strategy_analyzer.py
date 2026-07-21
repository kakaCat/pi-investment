import pytest
from application.services.strategy_analyzer import StrategyAnalyzer


class TestStrategyAnalyzer:
    """策略分析器测试套件"""

    def test_calculate_ratings_excellent_strategy(self):
        """测试优秀策略评级"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.8,
            'annualReturn': 0.20,
            'maxDrawdown': -0.12,
            'winRate': 0.60,
            'totalTrades': 30
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)

        assert result['ratings']['overall'] == 'A'
        assert result['ratings']['stability'] == 'excellent'
        assert result['ratings']['return'] == 'excellent'
        assert result['ratings']['risk'] == 'low'

    def test_calculate_ratings_poor_strategy(self):
        """测试差策略评级"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 0.4,
            'annualReturn': 0.03,
            'maxDrawdown': -0.40,
            'winRate': 0.35,
            'totalTrades': 50
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)

        assert result['ratings']['overall'] == 'D'
        assert result['ratings']['stability'] == 'poor'

    def test_missing_metrics_keys(self):
        """测试缺少 metrics 必需字段"""
        analyzer = StrategyAnalyzer()

        incomplete_metrics = {
            'sharpeRatio': 1.5,
            'annualReturn': 0.15
            # 缺少 maxDrawdown, winRate, totalTrades
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        with pytest.raises(ValueError, match="metrics 缺少必需字段"):
            analyzer.analyze(incomplete_metrics, benchmark)

    def test_missing_benchmark_keys(self):
        """测试缺少 benchmark 必需字段"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.5,
            'annualReturn': 0.15,
            'maxDrawdown': -0.20,
            'winRate': 0.55,
            'totalTrades': 25
        }

        incomplete_benchmark = {
            'sharpeRatio': 0.6
            # 缺少 annualReturn, maxDrawdown
        }

        with pytest.raises(ValueError, match="benchmark 缺少必需字段"):
            analyzer.analyze(metrics, incomplete_benchmark)

    def test_invalid_winrate_range(self):
        """测试 winRate 超出 [0, 1] 范围"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.5,
            'annualReturn': 0.15,
            'maxDrawdown': -0.20,
            'winRate': 1.5,  # 无效值
            'totalTrades': 25
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        with pytest.raises(ValueError, match="winRate 必须在 \\[0, 1\\] 范围内"):
            analyzer.analyze(metrics, benchmark)

    def test_invalid_total_trades(self):
        """测试 totalTrades 为负数"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.5,
            'annualReturn': 0.15,
            'maxDrawdown': -0.20,
            'winRate': 0.55,
            'totalTrades': -10  # 无效值
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        with pytest.raises(ValueError, match="totalTrades 必须 >= 0"):
            analyzer.analyze(metrics, benchmark)

    def test_invalid_drawdown_positive(self):
        """测试 maxDrawdown 为正数"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.5,
            'annualReturn': 0.15,
            'maxDrawdown': 0.20,  # 无效值（应该是负数）
            'winRate': 0.55,
            'totalTrades': 25
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        with pytest.raises(ValueError, match="maxDrawdown 必须 <= 0"):
            analyzer.analyze(metrics, benchmark)

    def test_boundary_sharpe_exactly_1_5(self):
        """测试夏普比率恰好为 1.5（边界值）"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.5,  # 恰好等于 excellent 阈值
            'annualReturn': 0.15,
            'maxDrawdown': -0.15,
            'winRate': 0.55,
            'totalTrades': 25
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)
        assert result['ratings']['stability'] == 'excellent'

    def test_boundary_sharpe_exactly_1_0(self):
        """测试夏普比率恰好为 1.0（边界值）"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.0,  # 恰好等于 good 阈值
            'annualReturn': 0.10,
            'maxDrawdown': -0.20,
            'winRate': 0.50,
            'totalTrades': 20
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)
        assert result['ratings']['stability'] == 'good'

    def test_moderate_return_rating(self):
        """测试 moderate 收益评级（超过基准但低于 10%）"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.2,
            'annualReturn': 0.09,  # 超过基准 0.08，但低于 0.10
            'maxDrawdown': -0.20,
            'winRate': 0.50,
            'totalTrades': 20
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)
        assert result['ratings']['return'] == 'moderate'

    def test_high_risk_rating(self):
        """测试 high 风险评级（回撤超过 -35%）"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.2,
            'annualReturn': 0.15,
            'maxDrawdown': -0.40,  # 高风险
            'winRate': 0.50,
            'totalTrades': 20
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)
        assert result['ratings']['risk'] == 'high'

    def test_generate_diagnosis_with_strengths(self):
        """测试生成诊断结论（有优势）"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.8,
            'annualReturn': 0.20,
            'maxDrawdown': -0.12,
            'winRate': 0.60,
            'totalTrades': 30
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)
        diagnosis = analyzer.generate_diagnosis(metrics, result['ratings'], result['comparison'])

        assert len(diagnosis['strengths']) > 0
        assert '夏普比率' in diagnosis['strengths'][0]
        assert '优于基准' in diagnosis['strengths'][0]
        assert '胜率' in diagnosis['strengths'][1]

    def test_generate_diagnosis_with_weaknesses(self):
        """测试生成诊断结论（有劣势）"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 0.8,
            'annualReturn': 0.10,
            'maxDrawdown': -0.30,  # 回撤偏高
            'winRate': 0.45,
            'totalTrades': 15  # 交易次数少
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)
        diagnosis = analyzer.generate_diagnosis(metrics, result['ratings'], result['comparison'])

        assert len(diagnosis['weaknesses']) == 2
        assert '最大回撤' in diagnosis['weaknesses'][0]
        assert '交易次数较少' in diagnosis['weaknesses'][1]

    def test_generate_diagnosis_with_suggestions(self):
        """测试生成诊断结论（有建议）"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 0.4,
            'annualReturn': 0.05,
            'maxDrawdown': -0.30,
            'winRate': 0.40,
            'totalTrades': 10
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)
        diagnosis = analyzer.generate_diagnosis(metrics, result['ratings'], result['comparison'])

        assert len(diagnosis['suggestions']) == 3
        assert 'ATR' in diagnosis['suggestions'][0]
        assert '入场信号' in diagnosis['suggestions'][1]
        assert '市场状态识别' in diagnosis['suggestions'][2]

    def test_generate_conclusion_sharpe_below_1(self):
        """测试结论生成（夏普比率 < 1.0）"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 0.8,
            'annualReturn': 0.10,
            'maxDrawdown': -0.20,
            'winRate': 0.50,
            'totalTrades': 20
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)
        diagnosis = analyzer.generate_diagnosis(metrics, result['ratings'], result['comparison'])

        assert '不如买指数' in diagnosis['conclusion']

    def test_generate_conclusion_sharpe_above_benchmark(self):
        """测试结论生成（夏普比率优于基准）"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.5,
            'annualReturn': 0.15,
            'maxDrawdown': -0.20,
            'winRate': 0.55,
            'totalTrades': 25
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)
        diagnosis = analyzer.generate_diagnosis(metrics, result['ratings'], result['comparison'])

        assert '优于基准' in diagnosis['conclusion']

    def test_invalid_data_type(self):
        """测试无效数据类型"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': "1.5",  # 字符串而非数值
            'annualReturn': 0.15,
            'maxDrawdown': -0.20,
            'winRate': 0.55,
            'totalTrades': 25
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        with pytest.raises(ValueError, match="必须是数值类型"):
            analyzer.analyze(metrics, benchmark)

    def test_b_rating_strategy(self):
        """测试 B 级策略（60-79 分）"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 1.2,  # good (25分)
            'annualReturn': 0.12,  # good (20分)
            'maxDrawdown': -0.20,  # moderate (10分)
            'winRate': 0.52,
            'totalTrades': 22
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)
        # 25 + 20 + 10 + 10 = 65 (B级)
        assert result['ratings']['overall'] == 'B'

    def test_c_rating_strategy(self):
        """测试 C 级策略（40-59 分）"""
        analyzer = StrategyAnalyzer()

        metrics = {
            'sharpeRatio': 0.8,  # poor (10分)
            'annualReturn': 0.12,  # good (20分)
            'maxDrawdown': -0.20,  # moderate (10分)
            'winRate': 0.48,
            'totalTrades': 18
        }

        benchmark = {
            'sharpeRatio': 0.6,
            'annualReturn': 0.08,
            'maxDrawdown': -0.25
        }

        result = analyzer.analyze(metrics, benchmark)
        # 10 + 20 + 10 = 40 (C级)
        assert result['ratings']['overall'] == 'C'

