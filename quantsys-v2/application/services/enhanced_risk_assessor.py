"""
增强型风险评估服务 - EnhancedRiskAssessor

在原有风险评估基础上，增加博弈维度的风险评估
"""
import structlog
from typing import Dict, Any, List
from datetime import datetime, timedelta
from adapters.outbound.repositories import StockPoolRepository
from adapters.outbound.repositories import FundFlowRepository
from application.services.opponent_behavior_service import OpponentBehaviorService
from application.services.manipulation_detector import ManipulationDetector

logger = structlog.get_logger(__name__)


class EnhancedRiskAssessor:
    """增强型风险评估器 - 包含博弈维度"""

    def __init__(self):
        """初始化服务"""
        self.pool_repo = StockPoolORMRepository()
        self.fund_flow_repo = FundFlowORMRepository()
        self.opponent_service = OpponentBehaviorService()
        self.manipulation_detector = ManipulationDetector()

    def assess_pool_risk(self, pool_id: int) -> Dict[str, Any]:
        """
        评估池子的综合风险

        Args:
            pool_id: 池子ID

        Returns:
            {
                'pool_id': 1,
                'overall_risk_score': 65,  # 0-100，越高越危险
                'risk_level': 'medium',     # low/medium/high/critical
                'risk_factors': [
                    {
                        'category': 'market_risk',
                        'factor': '机构大量出货',
                        'score': 80,
                        'weight': 0.3
                    }
                ],
                'dimensions': {
                    'market_risk': 75,      # 市场风险
                    'opponent_risk': 60,    # 对手风险
                    'manipulation_risk': 40, # 操纵风险
                    'concentration_risk': 30 # 集中度风险
                },
                'recommendation': '建议减仓50%',
                'warning_signs': [...]
            }
        """
        logger.info(f"🔍 评估池子综合风险: pool_id={pool_id}")

        try:
            # 1. 获取池子信息
            pool = self.pool_repo.get_pool(pool_id)
            if not pool:
                raise ValueError(f"池子不存在: {pool_id}")

            # 2. 评估各维度风险
            market_risk = self._assess_market_risk(pool)
            opponent_risk = self._assess_opponent_risk(pool)
            manipulation_risk = self._assess_manipulation_risk(pool)
            concentration_risk = self._assess_concentration_risk(pool)

            # 3. 计算综合风险评分
            dimensions = {
                'market_risk': market_risk['score'],
                'opponent_risk': opponent_risk['score'],
                'manipulation_risk': manipulation_risk['score'],
                'concentration_risk': concentration_risk['score']
            }

            # 加权计算
            weights = {
                'market_risk': 0.3,
                'opponent_risk': 0.3,
                'manipulation_risk': 0.25,
                'concentration_risk': 0.15
            }

            overall_score = sum(
                dimensions[dim] * weights[dim]
                for dim in dimensions
            )

            # 4. 确定风险级别
            risk_level = self._determine_risk_level(overall_score)

            # 5. 汇总风险因子
            risk_factors = []
            risk_factors.extend(market_risk.get('factors', []))
            risk_factors.extend(opponent_risk.get('factors', []))
            risk_factors.extend(manipulation_risk.get('factors', []))
            risk_factors.extend(concentration_risk.get('factors', []))

            # 6. 生成建议
            recommendation = self._generate_risk_recommendation(overall_score, risk_level)

            # 7. 识别预警信号
            warning_signs = self._identify_warning_signs(risk_factors)

            result = {
                'pool_id': pool_id,
                'overall_risk_score': round(overall_score, 1),
                'risk_level': risk_level,
                'dimensions': dimensions,
                'risk_factors': risk_factors,
                'recommendation': recommendation,
                'warning_signs': warning_signs,
                'assessed_at': datetime.now().isoformat()
            }

            logger.info(
                f"✅ 风险评估完成: score={overall_score:.1f}, "
                f"level={risk_level}, factors={len(risk_factors)}"
            )

            return result

        except Exception as e:
            logger.error(f"❌ 风险评估失败: {e}", exc_info=True)
            raise

    def _assess_market_risk(self, pool: Dict) -> Dict[str, Any]:
        """评估市场风险"""
        score = 0
        factors = []

        try:
            # 获取市场对手行为
            opponent_behavior = self.opponent_service.analyze_current_behavior()

            # 市场处于派发阶段 → 高风险
            if opponent_behavior['market_phase'] == 'distribution':
                score += 30
                factors.append({
                    'category': 'market_risk',
                    'factor': '市场处于派发阶段（顶部）',
                    'score': 30,
                    'weight': 0.3
                })

            # 散户追涨 → 中风险
            if opponent_behavior['retail']['behavior'] == 'fomo_buying':
                score += 20
                factors.append({
                    'category': 'market_risk',
                    'factor': '散户追涨买入（情绪过热）',
                    'score': 20,
                    'weight': 0.3
                })

            # 机构大量出货 → 高风险
            institution_flow = opponent_behavior['institution']['flow_amount']
            if institution_flow < -50:
                score += 40
                factors.append({
                    'category': 'market_risk',
                    'factor': f'机构大量出货（{abs(institution_flow):.1f}亿）',
                    'score': 40,
                    'weight': 0.3
                })

        except Exception as e:
            logger.warning(f"评估市场风险失败: {e}")

        return {
            'score': min(100, score),
            'factors': factors
        }

    def _assess_opponent_risk(self, pool: Dict) -> Dict[str, Any]:
        """评估对手风险"""
        score = 0
        factors = []

        try:
            symbols = pool.get('symbols', [])
            if not symbols:
                return {'score': 0, 'factors': []}

            # 分析池子中股票的资金流向
            end_date = datetime.now()
            start_date = end_date - timedelta(days=3)

            for symbol in symbols[:5]:  # 只分析前5只
                try:
                    flows = self.fund_flow_repo.get_fund_flow(
                        symbol,
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d')
                    )

                    if not flows:
                        continue

                    # 计算机构资金流
                    institution_flow = sum([
                        (row.get('large_net_inflow') or 0) +
                        (row.get('big_net_inflow') or 0)
                        for row in flows
                    ])

                    # 机构流出 → 风险
                    if institution_flow < -10000000:  # -1000万
                        score += 15
                        factors.append({
                            'category': 'opponent_risk',
                            'factor': f'{symbol} 机构流出{abs(institution_flow)/100000000:.1f}亿',
                            'score': 15,
                            'weight': 0.3
                        })

                except Exception as e:
                    logger.debug(f"分析{symbol}资金流失败: {e}")
                    continue

        except Exception as e:
            logger.warning(f"评估对手风险失败: {e}")

        return {
            'score': min(100, score),
            'factors': factors
        }

    def _assess_manipulation_risk(self, pool: Dict) -> Dict[str, Any]:
        """评估操纵风险"""
        score = 0
        factors = []

        try:
            symbols = pool.get('symbols', [])
            if not symbols:
                return {'score': 0, 'factors': []}

            # 检测池子中是否有被操纵的股票
            manipulation_result = self.manipulation_detector.detect_market_manipulation()
            active_manipulations = manipulation_result.get('active_manipulations', [])

            for manip in active_manipulations:
                if manip['symbol'] in symbols:
                    # 池子中有被操纵的股票 → 高风险
                    risk_score = 80 if manip['risk_level'] == 'extreme' else 60
                    score += risk_score

                    factors.append({
                        'category': 'manipulation_risk',
                        'factor': f"{manip['symbol']} 检测到{manip['manipulation_type']}",
                        'score': risk_score,
                        'weight': 0.25
                    })

        except Exception as e:
            logger.warning(f"评估操纵风险失败: {e}")

        return {
            'score': min(100, score),
            'factors': factors
        }

    def _assess_concentration_risk(self, pool: Dict) -> Dict[str, Any]:
        """评估集中度风险"""
        score = 0
        factors = []

        try:
            symbols = pool.get('symbols', [])
            symbol_count = len(symbols)

            # 股票数量过少 → 集中度风险
            if symbol_count < 5:
                score += 40
                factors.append({
                    'category': 'concentration_risk',
                    'factor': f'股票数量过少（{symbol_count}只）',
                    'score': 40,
                    'weight': 0.15
                })
            elif symbol_count < 10:
                score += 20
                factors.append({
                    'category': 'concentration_risk',
                    'factor': f'股票数量偏少（{symbol_count}只）',
                    'score': 20,
                    'weight': 0.15
                })

            # TODO: 分析行业集中度、权重集中度等

        except Exception as e:
            logger.warning(f"评估集中度风险失败: {e}")

        return {
            'score': min(100, score),
            'factors': factors
        }

    def _determine_risk_level(self, score: float) -> str:
        """确定风险级别"""
        if score >= 75:
            return 'critical'
        elif score >= 50:
            return 'high'
        elif score >= 25:
            return 'medium'
        else:
            return 'low'

    def _generate_risk_recommendation(self, score: float, level: str) -> str:
        """生成风险建议"""
        if level == 'critical':
            return '建议立即清仓或大幅减仓80%以上'
        elif level == 'high':
            return '建议减仓50-80%'
        elif level == 'medium':
            return '建议减仓20-50%或密切观察'
        else:
            return '风险可控，保持当前仓位'

    def _identify_warning_signs(self, risk_factors: List[Dict]) -> List[str]:
        """识别预警信号"""
        warning_signs = []

        # 高分风险因子 → 预警信号
        for factor in risk_factors:
            if factor.get('score', 0) >= 30:
                warning_signs.append(factor.get('factor', ''))

        return warning_signs
