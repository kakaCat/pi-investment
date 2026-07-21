"""
综合评分示例 - 技术面 + 基本面双维度评分

演示如何使用 TechnicalScorer 和 FundamentalScorer 进行综合评分
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from typing import Dict, List, Tuple
from application.services.scoring.technical_scorer import TechnicalScorer
from application.services.scoring.fundamental_scorer import FundamentalScorer

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class CompositeScorer:
    """
    综合评分器

    整合技术面和基本面评分，提供多种加权策略
    """

    def __init__(self):
        """初始化评分器"""
        self.technical_scorer = TechnicalScorer()
        self.fundamental_scorer = FundamentalScorer()

    def score(
        self,
        technical_factors: Dict,
        fundamental_data: Dict,
        strategy: str = 'balanced'
    ) -> Dict:
        """
        综合评分

        Args:
            technical_factors: 技术指标数据
            fundamental_data: 基本面数据
            strategy: 评分策略
                - 'balanced': 平衡（技术50% + 基本面50%）
                - 'technical_focus': 技术为主（技术70% + 基本面30%）
                - 'fundamental_focus': 基本面为主（技术30% + 基本面70%）
                - 'aggressive': 激进（技术80% + 基本面20%）
                - 'conservative': 保守（技术20% + 基本面80%）

        Returns:
            综合评分结果
        """
        # 计算技术面评分
        tech_result = self.technical_scorer.score(technical_factors)
        tech_score = tech_result['total']

        # 计算基本面评分
        fund_result = self.fundamental_scorer.score(fundamental_data)
        fund_score = fund_result['total']

        # 根据策略计算权重
        weights = self._get_weights(strategy)
        tech_weight = weights['technical']
        fund_weight = weights['fundamental']

        # 综合评分
        composite_score = tech_score * tech_weight + fund_score * fund_weight

        # 评级
        rating = self._calculate_rating(composite_score)

        # 投资建议
        recommendation = self._generate_recommendation(
            tech_score, fund_score, composite_score, strategy
        )

        return {
            'composite_score': composite_score,
            'rating': rating,
            'recommendation': recommendation,
            'breakdown': {
                'technical': {
                    'score': tech_score,
                    'weight': tech_weight,
                    'contribution': tech_score * tech_weight,
                    'details': tech_result['breakdown']
                },
                'fundamental': {
                    'score': fund_score,
                    'weight': fund_weight,
                    'contribution': fund_score * fund_weight,
                    'details': fund_result['breakdown']
                }
            },
            'strategy': strategy
        }

    def _get_weights(self, strategy: str) -> Dict[str, float]:
        """获取评分权重"""
        weights_map = {
            'balanced': {'technical': 0.5, 'fundamental': 0.5},
            'technical_focus': {'technical': 0.7, 'fundamental': 0.3},
            'fundamental_focus': {'technical': 0.3, 'fundamental': 0.7},
            'aggressive': {'technical': 0.8, 'fundamental': 0.2},
            'conservative': {'technical': 0.2, 'fundamental': 0.8}
        }
        return weights_map.get(strategy, weights_map['balanced'])

    def _calculate_rating(self, score: float) -> str:
        """计算评级"""
        if score >= 85:
            return 'A+（强烈推荐）'
        elif score >= 75:
            return 'A（推荐）'
        elif score >= 65:
            return 'B+（较好）'
        elif score >= 55:
            return 'B（中性）'
        elif score >= 45:
            return 'C（观望）'
        else:
            return 'D（回避）'

    def _generate_recommendation(
        self,
        tech_score: float,
        fund_score: float,
        composite_score: float,
        strategy: str
    ) -> str:
        """生成投资建议"""
        if composite_score >= 80:
            base = "强烈建议关注"
        elif composite_score >= 70:
            base = "建议关注"
        elif composite_score >= 60:
            base = "可以关注"
        elif composite_score >= 50:
            base = "中性，谨慎"
        else:
            base = "建议回避"

        # 分析技术面和基本面的协同性
        score_diff = abs(tech_score - fund_score)
        if score_diff <= 10:
            synergy = "技术面和基本面高度协同"
        elif score_diff <= 20:
            synergy = "技术面和基本面较为协同"
        else:
            if tech_score > fund_score:
                synergy = "技术面强于基本面，注意基本面风险"
            else:
                synergy = "基本面强于技术面，等待技术面确认"

        return f"{base}。{synergy}。"


def demo_excellent_stock():
    """演示：优秀股票评分"""
    logger.info("=" * 60)
    logger.info("示例 1: 优秀股票（技术面+基本面都优秀）")
    logger.info("=" * 60)

    scorer = CompositeScorer()

    # 技术面数据（强烈买入信号）
    technical = {
        'rsi': 28,              # 超卖
        'macd': 0.5,
        'macd_signal': 0.3,
        'macd_prev': 0.2,
        'macd_signal_prev': 0.4,  # 金叉
        'adx': 35,              # 强趋势
        'volume_ratio_5d': 2.0  # 放量
    }

    # 基本面数据（优质公司）
    fundamental = {
        'pe': 12,               # 低估
        'roe': 22,              # 高盈利
        'gross_margin': 38,     # 高毛利
        'debt_ratio': 25,       # 低负债
        'revenue_growth': 28    # 高增长
    }

    # 使用不同策略评分
    strategies = ['balanced', 'technical_focus', 'fundamental_focus']

    for strategy in strategies:
        result = scorer.score(technical, fundamental, strategy)

        logger.info(f"\n策略: {strategy}")
        logger.info(f"  综合评分: {result['composite_score']:.2f}")
        logger.info(f"  评级: {result['rating']}")
        logger.info(f"  技术面: {result['breakdown']['technical']['score']:.2f} (权重 {result['breakdown']['technical']['weight']:.0%})")
        logger.info(f"  基本面: {result['breakdown']['fundamental']['score']:.2f} (权重 {result['breakdown']['fundamental']['weight']:.0%})")
        logger.info(f"  建议: {result['recommendation']}")


def demo_technical_strong():
    """演示：技术面强、基本面弱"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 2: 技术面强势，基本面一般（短线机会）")
    logger.info("=" * 60)

    scorer = CompositeScorer()

    # 技术面数据（强烈买入信号）
    technical = {
        'rsi': 25,
        'macd': 0.6,
        'macd_signal': 0.2,
        'macd_prev': 0.1,
        'macd_signal_prev': 0.3,
        'adx': 40,
        'volume_ratio_5d': 2.5
    }

    # 基本面数据（一般）
    fundamental = {
        'pe': 35,               # 略高估
        'roe': 8,               # 一般
        'gross_margin': 18,     # 一般
        'debt_ratio': 55,       # 中等
        'revenue_growth': 5     # 低增长
    }

    # 技术面为主策略更适合
    strategies = ['technical_focus', 'balanced', 'fundamental_focus']

    for strategy in strategies:
        result = scorer.score(technical, fundamental, strategy)

        logger.info(f"\n策略: {strategy}")
        logger.info(f"  综合评分: {result['composite_score']:.2f}")
        logger.info(f"  评级: {result['rating']}")
        logger.info(f"  建议: {result['recommendation']}")


def demo_fundamental_strong():
    """演示：基本面强、技术面弱"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 3: 基本面优秀，技术面疲弱（长线价值）")
    logger.info("=" * 60)

    scorer = CompositeScorer()

    # 技术面数据（疲弱）
    technical = {
        'rsi': 65,              # 接近超买
        'macd': -0.2,
        'macd_signal': 0.1,
        'macd_prev': 0.0,
        'macd_signal_prev': 0.1,  # 死叉
        'adx': 20,              # 弱趋势
        'volume_ratio_5d': 0.7  # 缩量
    }

    # 基本面数据（优秀）
    fundamental = {
        'pe': 10,               # 低估
        'roe': 25,              # 卓越
        'gross_margin': 40,     # 优秀
        'debt_ratio': 20,       # 低负债
        'revenue_growth': 30    # 高增长
    }

    # 基本面为主策略更适合
    strategies = ['fundamental_focus', 'balanced', 'technical_focus']

    for strategy in strategies:
        result = scorer.score(technical, fundamental, strategy)

        logger.info(f"\n策略: {strategy}")
        logger.info(f"  综合评分: {result['composite_score']:.2f}")
        logger.info(f"  评级: {result['rating']}")
        logger.info(f"  建议: {result['recommendation']}")


def demo_poor_stock():
    """演示：双重疲弱"""
    logger.info("\n" + "=" * 60)
    logger.info("示例 4: 技术面和基本面都疲弱（回避）")
    logger.info("=" * 60)

    scorer = CompositeScorer()

    # 技术面数据（疲弱）
    technical = {
        'rsi': 75,
        'macd': -0.5,
        'macd_signal': -0.2,
        'macd_prev': -0.3,
        'macd_signal_prev': -0.1,
        'adx': 15,
        'volume_ratio_5d': 0.6
    }

    # 基本面数据（较差）
    fundamental = {
        'pe': 60,
        'roe': 3,
        'gross_margin': 8,
        'debt_ratio': 75,
        'revenue_growth': -12
    }

    result = scorer.score(technical, fundamental, 'balanced')

    logger.info(f"\n综合评分: {result['composite_score']:.2f}")
    logger.info(f"评级: {result['rating']}")
    logger.info(f"技术面: {result['breakdown']['technical']['score']:.2f}")
    logger.info(f"基本面: {result['breakdown']['fundamental']['score']:.2f}")
    logger.info(f"建议: {result['recommendation']}")


def compare_strategies():
    """对比不同策略"""
    logger.info("\n" + "=" * 60)
    logger.info("策略对比总结")
    logger.info("=" * 60)

    strategies_info = {
        'balanced': '平衡策略 - 技术面和基本面各占50%，适合大多数情况',
        'technical_focus': '技术面为主 - 技术70%基本30%，适合短线交易',
        'fundamental_focus': '基本面为主 - 基本70%技术30%，适合长线投资',
        'aggressive': '激进策略 - 技术80%基本20%，适合波段操作',
        'conservative': '保守策略 - 基本80%技术20%，适合价值投资'
    }

    logger.info("\n可用策略:")
    for strategy, description in strategies_info.items():
        logger.info(f"  • {strategy}: {description}")

    logger.info("\n策略选择建议:")
    logger.info("  • 短线交易者: technical_focus 或 aggressive")
    logger.info("  • 中线交易者: balanced")
    logger.info("  • 长线投资者: fundamental_focus 或 conservative")
    logger.info("  • 价值投资者: conservative")


def main():
    """运行所有示例"""
    logger.info("\n" + "=" * 80)
    logger.info("综合评分示例 - 技术面 + 基本面双维度评分")
    logger.info("=" * 80)

    # 运行所有示例
    demo_excellent_stock()
    demo_technical_strong()
    demo_fundamental_strong()
    demo_poor_stock()
    compare_strategies()

    logger.info("\n" + "=" * 80)
    logger.info("示例完成")
    logger.info("=" * 80)
    logger.info("\n提示: 在实际使用中，可以根据市场环境和投资风格选择合适的策略")


if __name__ == '__main__':
    main()
