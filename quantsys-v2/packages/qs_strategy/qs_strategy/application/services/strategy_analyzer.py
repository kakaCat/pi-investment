"""
策略分析器 - 计算策略评级和诊断结论
"""
from typing import Dict
import structlog

logger = structlog.get_logger(__name__)


class StrategyAnalyzer:
    """策略指标分析器"""

    # 固定阈值标准
    THRESHOLDS = {
        'sharpe': {'excellent': 1.5, 'good': 1.0, 'poor': 0.5},
        'return': {'excellent': 0.15, 'good': 0.10, 'poor': 0.05},
        'drawdown': {'excellent': -0.15, 'good': -0.25, 'poor': -0.35}
    }

    def analyze(self, metrics: Dict, benchmark: Dict) -> Dict:
        """
        分析策略表现

        Args:
            metrics: 策略指标 {sharpeRatio, annualReturn, maxDrawdown, winRate, totalTrades}
            benchmark: 基准指标 {sharpeRatio, annualReturn, maxDrawdown}

        Returns:
            分析结果 {ratings, comparison}

        Raises:
            ValueError: 如果缺少必需的键或数据无效
        """
        # 0. 输入验证
        self._validate_inputs(metrics, benchmark)

        # 1. 计算各维度评级
        ratings = self._calculate_ratings(metrics, benchmark)

        # 2. 对比基准
        comparison = self._compare_with_benchmark(metrics, benchmark)

        # 3. 综合评级
        overall_rating = self._calculate_overall_rating(ratings, comparison)

        return {
            'ratings': {
                'overall': overall_rating,
                'return': ratings['return'],
                'risk': ratings['risk'],
                'stability': ratings['stability']
            },
            'comparison': comparison
        }

    def _validate_inputs(self, metrics: Dict, benchmark: Dict) -> None:
        """
        验证输入参数

        Raises:
            ValueError: 如果缺少必需的键或数据无效
        """
        # 验证 metrics 必需字段
        required_metrics = ['sharpeRatio', 'annualReturn', 'maxDrawdown', 'winRate', 'totalTrades']
        missing_metrics = [key for key in required_metrics if key not in metrics]
        if missing_metrics:
            raise ValueError(f"metrics 缺少必需字段: {', '.join(missing_metrics)}")

        # 验证 benchmark 必需字段
        required_benchmark = ['sharpeRatio', 'annualReturn', 'maxDrawdown']
        missing_benchmark = [key for key in required_benchmark if key not in benchmark]
        if missing_benchmark:
            raise ValueError(f"benchmark 缺少必需字段: {', '.join(missing_benchmark)}")

        # 验证数值类型
        for key in required_metrics:
            if not isinstance(metrics[key], (int, float)):
                raise ValueError(f"metrics['{key}'] 必须是数值类型，当前类型: {type(metrics[key])}")

        for key in required_benchmark:
            if not isinstance(benchmark[key], (int, float)):
                raise ValueError(f"benchmark['{key}'] 必须是数值类型，当前类型: {type(benchmark[key])}")

        # 验证数值范围
        if metrics['winRate'] < 0 or metrics['winRate'] > 1:
            raise ValueError(f"winRate 必须在 [0, 1] 范围内，当前值: {metrics['winRate']}")

        if metrics['totalTrades'] < 0:
            raise ValueError(f"totalTrades 必须 >= 0，当前值: {metrics['totalTrades']}")

        if metrics['maxDrawdown'] > 0:
            raise ValueError(f"maxDrawdown 必须 <= 0，当前值: {metrics['maxDrawdown']}")

        if benchmark['maxDrawdown'] > 0:
            raise ValueError(f"benchmark maxDrawdown 必须 <= 0，当前值: {benchmark['maxDrawdown']}")

    def _calculate_ratings(self, metrics: Dict, benchmark: Dict) -> Dict:
        """
        计算各维度评级

        收益评级逻辑：
        1. 绝对优秀（>15%）→ excellent
        2. 绝对良好（>10%）→ good
        3. 超过基准 → moderate
        4. 其他 → poor
        """
        sharpe = metrics['sharpeRatio']
        annual_return = metrics['annualReturn']
        max_drawdown = metrics['maxDrawdown']

        # 收益评级（优先固定阈值，次要相对基准）
        if annual_return >= self.THRESHOLDS['return']['excellent']:
            return_rating = 'excellent'
        elif annual_return >= self.THRESHOLDS['return']['good']:
            return_rating = 'good'
        elif annual_return > benchmark['annualReturn']:
            return_rating = 'moderate'
        else:
            return_rating = 'poor'

        # 风险评级（回撤越小越好）
        if max_drawdown > self.THRESHOLDS['drawdown']['excellent']:
            risk_rating = 'low'
        elif max_drawdown > self.THRESHOLDS['drawdown']['good']:
            risk_rating = 'moderate'
        else:
            risk_rating = 'high'

        # 稳定性评级（基于夏普比率）
        if sharpe >= self.THRESHOLDS['sharpe']['excellent']:
            stability_rating = 'excellent'
        elif sharpe >= self.THRESHOLDS['sharpe']['good']:
            stability_rating = 'good'
        else:
            stability_rating = 'poor'

        return {
            'return': return_rating,
            'risk': risk_rating,
            'stability': stability_rating
        }

    def _compare_with_benchmark(self, metrics: Dict, benchmark: Dict) -> Dict:
        """对比基准指标"""
        return {
            'sharpe_vs_benchmark': metrics['sharpeRatio'] - benchmark['sharpeRatio'],
            'return_vs_benchmark': metrics['annualReturn'] - benchmark['annualReturn'],
            'drawdown_vs_benchmark': metrics['maxDrawdown'] - benchmark['maxDrawdown']
        }

    def _calculate_overall_rating(self, ratings: Dict, comparison: Dict) -> str:
        """
        计算综合评级 A/B/C/D

        评分规则：
        - 稳定性（夏普比率）权重 40%
        - 收益权重 30%
        - 风险控制权重 20%
        - 相对基准加分 10%
        """
        score = 0

        # 稳定性权重 40%
        if ratings['stability'] == 'excellent':
            score += 40
        elif ratings['stability'] == 'good':
            score += 25
        else:  # poor
            score += 10

        # 收益权重 30%
        if ratings['return'] == 'excellent':
            score += 30
        elif ratings['return'] == 'good':
            score += 20
        elif ratings['return'] == 'moderate':
            score += 10
        else:  # poor
            score += 5

        # 风险控制权重 20%
        if ratings['risk'] == 'low':
            score += 20
        elif ratings['risk'] == 'moderate':
            score += 10
        else:  # high
            score += 0

        # 相对基准加分 10%
        if comparison['sharpe_vs_benchmark'] > 0.3:
            score += 10

        # 评级映射
        if score >= 80:
            return 'A'
        elif score >= 60:
            return 'B'
        elif score >= 40:
            return 'C'
        else:
            return 'D'

    def generate_diagnosis(self, metrics: Dict, ratings: Dict, comparison: Dict) -> Dict:
        """
        生成诊断结论

        Returns:
            {conclusion, strengths, weaknesses, suggestions}
        """
        strengths = []
        weaknesses = []
        suggestions = []

        # 优势
        if ratings['stability'] in ['excellent', 'good']:
            strengths.append(
                f"夏普比率 {metrics['sharpeRatio']:.2f} "
                f"{'优于' if comparison['sharpe_vs_benchmark'] > 0 else '低于'}基准"
            )
        if metrics['winRate'] > 0.5:
            strengths.append(f"胜率 {metrics['winRate']:.1%} 超过 50%")

        # 劣势
        if abs(metrics['maxDrawdown']) > 0.25:
            weaknesses.append(
                f"最大回撤 {abs(metrics['maxDrawdown']):.1%} 偏高，建议加强止损"
            )
        if metrics['totalTrades'] < 20:
            weaknesses.append("交易次数较少，可能错过机会")

        # 建议
        if abs(metrics['maxDrawdown']) > 0.25:
            suggestions.append("添加动态止损（基于 ATR）")
        if metrics['totalTrades'] < 20:
            suggestions.append("优化入场信号，提高交易频率")
        if ratings['overall'] in ['C', 'D']:
            suggestions.append("考虑加入市场状态识别")

        # 结论
        conclusion = self._generate_conclusion(metrics, ratings, comparison)

        return {
            'conclusion': conclusion,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'suggestions': suggestions
        }

    def _generate_conclusion(self, metrics: Dict, ratings: Dict, comparison: Dict) -> str:
        """生成诊断结论文本"""
        rating_text = {
            'A': '优秀',
            'B': '良好',
            'C': '一般',
            'D': '较差'
        }

        overall = ratings['overall']
        sharpe = metrics['sharpeRatio']
        sharpe_diff = comparison['sharpe_vs_benchmark']

        if sharpe < 1.0:
            return f"策略表现{rating_text[overall]}，夏普比率 {sharpe:.2f} < 1.0，不如买指数"
        elif sharpe_diff > 0:
            return f"策略表现{rating_text[overall]}，夏普比率 {sharpe:.2f} 优于基准，风险调整后收益较好"
        else:
            return f"策略表现{rating_text[overall]}，夏普比率 {sharpe:.2f}，建议优化"
