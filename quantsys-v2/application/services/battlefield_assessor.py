"""
战场评估服务 - BattlefieldAssessor

评估股票池在市场博弈中的竞争优势
"""
import structlog
from typing import Dict, Any, List
from datetime import datetime, timedelta
from adapters.outbound.repositories import AgentIntelligenceORMRepository
from adapters.outbound.repositories import StockPoolORMRepository
from adapters.outbound.repositories import FundFlowORMRepository
from application.services.opponent_behavior_service import OpponentBehaviorService

logger = structlog.get_logger(__name__)


class BattlefieldAssessor:
    """战场评估器 - 评估池子的博弈竞争力"""

    def __init__(self):
        """初始化服务"""
        self.pool_repo = StockPoolORMRepository()
        self.fund_flow_repo = FundFlowORMRepository()
        self.metrics_repo = AgentIntelligenceORMRepository()
        self.opponent_service = OpponentBehaviorService()

    def assess_pool(self, pool_id: int) -> Dict[str, Any]:
        """
        评估池子的战场优势

        Args:
            pool_id: 池子ID

        Returns:
            {
                'pool_id': 1,
                'battlefield_score': 78.5,  # 0-100分
                'opponent_strength': {
                    'retail_pressure': 'low',
                    'institution_interest': 'high',
                    'hot_money_risk': 'medium'
                },
                'game_phase': 'early_accumulation',
                'advantages': [...],
                'disadvantages': [...],
                'recommendation': 'accumulate',
                'urgency': 'medium',
                'confidence': 0.85
            }
        """
        logger.info(f"🎯 开始评估池子战场优势: pool_id={pool_id}")

        try:
            # 1. 获取池子信息
            pool = self.pool_repo.get_pool(pool_id)
            if not pool:
                raise ValueError(f"池子不存在: {pool_id}")

            # 2. 获取市场对手行为
            opponent_behavior = self.opponent_service.analyze_current_behavior()

            # 3. 分析池子中每只股票的战场状态
            stock_scores = self._analyze_stocks_battlefield(pool['symbols'])

            # 4. 聚合池子整体战场评分
            battlefield_score = self._calculate_pool_score(stock_scores)

            # 5. 分析对手强度
            opponent_strength = self._assess_opponent_strength(
                pool['symbols'],
                opponent_behavior
            )

            # 6. 判断博弈阶段
            game_phase = self._determine_game_phase(
                opponent_behavior['market_phase'],
                opponent_strength
            )

            # 7. 识别优势和劣势
            advantages, disadvantages = self._identify_pros_cons(
                stock_scores,
                opponent_behavior,
                opponent_strength
            )

            # 8. 生成建议
            recommendation, urgency = self._generate_recommendation(
                battlefield_score,
                game_phase,
                opponent_strength
            )

            # 9. 计算置信度
            confidence = self._calculate_confidence(stock_scores)

            # 10. 保存评估结果
            result = {
                'pool_id': pool_id,
                'battlefield_score': battlefield_score,
                'opponent_strength': opponent_strength,
                'game_phase': game_phase,
                'advantages': advantages,
                'disadvantages': disadvantages,
                'recommendation': recommendation,
                'urgency': urgency,
                'confidence': confidence
            }

            self.metrics_repo.save_metrics(result)

            logger.info(f"✅ 池子战场评估完成: score={battlefield_score:.1f}, phase={game_phase}")
            return result

        except Exception as e:
            logger.error(f"❌ 池子战场评估失败: {e}", exc_info=True)
            raise

    def _analyze_stocks_battlefield(self, symbols: List[str]) -> List[Dict]:
        """
        分析池子中每只股票的战场状态

        Args:
            symbols: 股票代码列表

        Returns:
            每只股票的战场评分
        """
        stock_scores = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)

        for symbol in symbols:
            try:
                # 获取股票资金流向
                fund_flows = self.fund_flow_repo.get_fund_flow(
                    symbol,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )

                if not fund_flows:
                    continue

                # 计算散户和机构资金流
                retail_flow = sum([
                    (row.get('small_net_inflow') or 0) + (row.get('medium_net_inflow') or 0)
                    for row in fund_flows
                ])

                institution_flow = sum([
                    (row.get('large_net_inflow') or 0) + (row.get('big_net_inflow') or 0)
                    for row in fund_flows
                ])

                # 战场评分
                score = self._calculate_stock_battlefield_score(
                    retail_flow,
                    institution_flow
                )

                stock_scores.append({
                    'symbol': symbol,
                    'score': score,
                    'retail_flow': retail_flow,
                    'institution_flow': institution_flow
                })

            except Exception as e:
                logger.warning(f"分析股票战场失败: {symbol} - {e}")
                continue

        return stock_scores

    def _calculate_stock_battlefield_score(self, retail_flow: float, institution_flow: float) -> float:
        """
        计算单股战场评分

        评分逻辑：
        - 散户抛售（负流入）：+20分
        - 机构建仓（正流入）：+30分
        - 双方力量差距大：+10分

        Args:
            retail_flow: 散户资金流
            institution_flow: 机构资金流

        Returns:
            战场评分（0-100）
        """
        score = 50  # 基础分

        # 散户行为评分
        if retail_flow < -10000000:  # 散户流出>1000万
            score += 20
        elif retail_flow < 0:
            score += 10
        elif retail_flow > 10000000:  # 散户流入>1000万
            score -= 10

        # 机构行为评分
        if institution_flow > 10000000:  # 机构流入>1000万
            score += 30
        elif institution_flow > 0:
            score += 15
        elif institution_flow < -10000000:  # 机构流出>1000万
            score -= 20

        # 力量差距评分（散户抛售+机构建仓 = 最佳）
        if retail_flow < 0 and institution_flow > 0:
            score += 10

        return max(0, min(100, score))

    def _calculate_pool_score(self, stock_scores: List[Dict]) -> float:
        """
        聚合池子整体战场评分

        Args:
            stock_scores: 每只股票的评分

        Returns:
            池子整体评分
        """
        if not stock_scores:
            return 50.0

        # 加权平均（可以根据持仓权重调整）
        avg_score = sum([s['score'] for s in stock_scores]) / len(stock_scores)
        return round(avg_score, 1)

    def _assess_opponent_strength(self, symbols: List[str], opponent_behavior: Dict) -> Dict:
        """
        评估对手强度

        Args:
            symbols: 池子股票列表
            opponent_behavior: 市场对手行为

        Returns:
            {
                'retail_pressure': 'low',
                'institution_interest': 'high',
                'hot_money_risk': 'medium'
            }
        """
        # 散户压力
        retail_behavior = opponent_behavior['retail']['behavior']
        if retail_behavior == 'panic_selling':
            retail_pressure = 'low'  # 散户恐慌 = 压力小 = 好事
        elif retail_behavior == 'fomo_buying':
            retail_pressure = 'high'  # 散户追涨 = 压力大 = 风险
        else:
            retail_pressure = 'medium'

        # 机构兴趣
        institution_behavior = opponent_behavior['institution']['behavior']
        if institution_behavior == 'accumulating':
            institution_interest = 'high'  # 机构建仓 = 兴趣高
        elif institution_behavior == 'distributing':
            institution_interest = 'low'  # 机构出货 = 兴趣低
        else:
            institution_interest = 'medium'

        # 游资风险
        hot_money_behavior = opponent_behavior['hot_money']['behavior']
        if hot_money_behavior == 'pump_and_dump':
            hot_money_risk = 'high'  # 游资炒作 = 风险高
        else:
            hot_money_risk = 'low'

        return {
            'retail_pressure': retail_pressure,
            'institution_interest': institution_interest,
            'hot_money_risk': hot_money_risk
        }

    def _determine_game_phase(self, market_phase: str, opponent_strength: Dict) -> str:
        """
        判断池子所处的博弈阶段

        Args:
            market_phase: 市场整体阶段
            opponent_strength: 对手强度

        Returns:
            博弈阶段
        """
        if market_phase == 'accumulation':
            if opponent_strength['institution_interest'] == 'high':
                return 'early_accumulation'  # 早期吸筹
            else:
                return 'late_accumulation'  # 后期吸筹

        elif market_phase == 'markup':
            return 'rising'  # 上涨阶段

        elif market_phase == 'distribution':
            if opponent_strength['retail_pressure'] == 'high':
                return 'topping'  # 顶部区域
            else:
                return 'early_distribution'  # 早期派发

        elif market_phase == 'markdown':
            return 'declining'  # 下跌阶段

        else:
            return 'consolidation'  # 震荡整理

    def _identify_pros_cons(self, stock_scores: List[Dict], opponent_behavior: Dict,
                           opponent_strength: Dict) -> tuple:
        """
        识别优势和劣势

        Returns:
            (advantages, disadvantages)
        """
        advantages = []
        disadvantages = []

        # 优势分析
        if opponent_strength['retail_pressure'] == 'low':
            advantages.append('散户恐慌抛售，筹码便宜')

        if opponent_strength['institution_interest'] == 'high':
            advantages.append('机构正在悄悄建仓')

        if opponent_behavior['market_phase'] == 'accumulation':
            advantages.append('市场处于吸筹阶段（底部）')

        avg_score = sum([s['score'] for s in stock_scores]) / len(stock_scores) if stock_scores else 50
        if avg_score > 70:
            advantages.append('池子整体战场优势明显')

        # 劣势分析
        if opponent_strength['retail_pressure'] == 'high':
            disadvantages.append('散户追涨，可能接近顶部')

        if opponent_strength['institution_interest'] == 'low':
            disadvantages.append('机构出货，风险增加')

        if opponent_strength['hot_money_risk'] == 'high':
            disadvantages.append('游资炒作，警惕拉高出货')

        if not stock_scores or len(stock_scores) < 5:
            disadvantages.append('池子成员较少，分散度不足')

        return advantages, disadvantages

    def _generate_recommendation(self, battlefield_score: float, game_phase: str,
                                opponent_strength: Dict) -> tuple:
        """
        生成操作建议

        Returns:
            (recommendation, urgency)
        """
        # 推荐动作
        if battlefield_score > 80:
            recommendation = 'accumulate'  # 积极建仓
            urgency = 'high'
        elif battlefield_score > 60:
            recommendation = 'hold'  # 持有
            urgency = 'medium'
        elif battlefield_score > 40:
            recommendation = 'reduce'  # 减仓
            urgency = 'medium'
        else:
            recommendation = 'exit'  # 退出
            urgency = 'high'

        # 特殊情况调整
        if game_phase == 'topping' or opponent_strength['institution_interest'] == 'low':
            if recommendation in ['accumulate', 'hold']:
                recommendation = 'reduce'
                urgency = 'high'

        return recommendation, urgency

    def _calculate_confidence(self, stock_scores: List[Dict]) -> float:
        """
        计算置信度

        基于：
        - 样本数量（股票数量）
        - 评分一致性（方差）

        Returns:
            置信度（0-1）
        """
        if not stock_scores:
            return 0.5

        # 基础置信度
        sample_size = len(stock_scores)
        base_confidence = min(0.7, 0.3 + sample_size * 0.04)  # 样本越多越自信

        # 一致性调整
        scores = [s['score'] for s in stock_scores]
        variance = sum([(s - sum(scores)/len(scores))**2 for s in scores]) / len(scores)
        consistency_factor = 1.0 - min(0.3, variance / 1000)

        confidence = base_confidence * consistency_factor
        return round(confidence, 2)
