"""
对手行为分析服务
分析市场参与者行为，识别博弈机会

按照 quantsys-v2 项目规范实现
"""
import structlog
from typing import Dict, Any, List
from datetime import datetime, timedelta
from adapters.outbound.repositories import AgentIntelligenceORMRepository, FundFlowORMRepository

logger = structlog.get_logger(__name__)


class OpponentBehaviorService:
    """对手行为分析服务"""

    def __init__(self):
        """初始化服务"""
        self.opponent_repo = AgentIntelligenceORMRepository()
        self.fund_flow_repo = FundFlowORMRepository()

    def analyze_current_behavior(self) -> Dict[str, Any]:
        """
        分析当前市场参与者行为

        Returns:
            {
                'retail': {...},           # 散户行为
                'institution': {...},      # 机构行为
                'hot_money': {...},        # 游资行为
                'market_phase': '...',     # 市场阶段
                'risk_appetite': '...',    # 风险偏好
                'opportunity_map': {...},  # 博弈机会
                'timestamp': '...'
            }
        """
        logger.info("🔍 开始分析对手行为")

        try:
            # 1. 分析散户行为
            retail = self._analyze_retail_behavior()
            logger.info(f"散户行为: {retail['behavior']}, 情绪指数: {retail['emotion_index']}")

            # 2. 分析机构行为
            institution = self._analyze_institution_behavior()
            logger.info(f"机构行为: {institution['behavior']}, 净流入: {institution['net_flow']/100000000:.1f}亿")

            # 3. 分析游资行为
            hot_money = self._analyze_hot_money_behavior()
            logger.info(f"游资行为: {hot_money['behavior']}")

            # 4. 判断市场阶段
            market_phase = self._determine_market_phase(retail, institution)
            logger.info(f"市场阶段: {market_phase}")

            # 5. 评估风险偏好
            risk_appetite = self._assess_risk_appetite(retail, institution)

            # 6. 生成机会地图
            opportunity_map = self._generate_opportunity_map(retail, institution, hot_money)
            logger.info(f"识别到 {len(opportunity_map)} 个博弈机会")

            # 7. 保存快照
            snapshot = {
                'retail_behavior': retail['behavior'],
                'retail_net_flow': retail['net_flow'],
                'retail_emotion_index': retail['emotion_index'],
                'institution_behavior': institution['behavior'],
                'institution_net_flow': institution['net_flow'],
                'institution_target_sectors': institution.get('target_sectors', []),
                'hot_money_behavior': hot_money['behavior'],
                'hot_money_target_stocks': hot_money.get('target_stocks', []),
                'hot_money_stage': hot_money.get('stage'),
                'market_phase': market_phase,
                'risk_appetite': risk_appetite,
                'opportunities': opportunity_map
            }
            self.opponent_repo.save_snapshot(snapshot)

            # 8. 构建返回结果
            result = {
                'retail': retail,
                'institution': institution,
                'hot_money': hot_money,
                'market_phase': market_phase,
                'risk_appetite': risk_appetite,
                'opportunity_map': opportunity_map,
                'timestamp': datetime.now().isoformat()
            }

            logger.info("✅ 对手行为分析完成")
            return result

        except Exception as e:
            logger.error(f"❌ 对手行为分析失败: {e}", exc_info=True)
            raise

    def _analyze_retail_behavior(self) -> Dict[str, Any]:
        """
        分析散户行为

        基于资金流向数据分析散户的行为模式和情绪状态

        Returns:
            {
                'behavior': 'panic_selling' | 'fomo_buying' | 'neutral',
                'net_flow': int,           # 净流入（元）
                'emotion_index': float,    # 情绪指数 0-100
                'common_mistakes': [str]   # 常见错误
            }
        """
        try:
            # 获取近5日资金流向数据
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)

            # TODO: 这里需要获取市场整体资金流向，暂时使用模拟逻辑
            # 实际实现时应该聚合所有股票或使用指数的资金流向

            # 计算散户净流入（小单 + 中单）
            # 散户通常是小额交易者
            retail_flow = self._calculate_retail_flow(start_date, end_date)

            # 判断行为模式
            if retail_flow < -30_0000_0000:  # -30亿
                behavior = 'panic_selling'
                emotion_index = 20.0  # 极度恐慌
                mistakes = ['割肉在低位', '恐慌中卖出优质股']
            elif retail_flow > 30_0000_0000:  # +30亿
                behavior = 'fomo_buying'
                emotion_index = 80.0  # 极度贪婪
                mistakes = ['追涨在高位', '不看基本面盲目追热点']
            else:
                behavior = 'neutral'
                emotion_index = 50.0  # 中性
                mistakes = []

            return {
                'behavior': behavior,
                'net_flow': int(retail_flow),
                'emotion_index': emotion_index,
                'common_mistakes': mistakes,
                'description': self._get_behavior_description(behavior, 'retail')
            }

        except Exception as e:
            logger.warning(f"分析散户行为失败，使用默认值: {e}")
            return {
                'behavior': 'neutral',
                'net_flow': 0,
                'emotion_index': 50.0,
                'common_mistakes': [],
                'description': '数据不足，无法判断'
            }

    def _analyze_institution_behavior(self) -> Dict[str, Any]:
        """
        分析机构行为

        基于大单流向、龙虎榜数据分析机构的建仓/出货行为

        Returns:
            {
                'behavior': 'accumulating' | 'distributing' | 'neutral',
                'net_flow': int,                  # 净流入（元）
                'target_sectors': [str],          # 目标板块
                'position_change': 'increasing' | 'decreasing'
            }
        """
        try:
            # 获取近5日资金流向
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)

            # 计算机构净流入（大单 + 特大单）
            institution_flow = self._calculate_institution_flow(start_date, end_date)

            # 判断行为模式
            if institution_flow > 20_0000_0000:  # +20亿
                behavior = 'accumulating'
                position_change = 'increasing'
            elif institution_flow < -20_0000_0000:  # -20亿
                behavior = 'distributing'
                position_change = 'decreasing'
            else:
                behavior = 'neutral'
                position_change = 'stable'

            # TODO: 分析目标板块（需要按行业聚合资金流向）
            target_sectors = self._identify_target_sectors(institution_flow > 0)

            return {
                'behavior': behavior,
                'net_flow': int(institution_flow),
                'target_sectors': target_sectors,
                'position_change': position_change,
                'description': self._get_behavior_description(behavior, 'institution')
            }

        except Exception as e:
            logger.warning(f"分析机构行为失败，使用默认值: {e}")
            return {
                'behavior': 'neutral',
                'net_flow': 0,
                'target_sectors': [],
                'position_change': 'stable',
                'description': '数据不足，无法判断'
            }

    def _analyze_hot_money_behavior(self) -> Dict[str, Any]:
        """
        分析游资行为

        基于龙虎榜、涨停板数据分析游资的炒作行为

        Returns:
            {
                'behavior': 'pump_and_dump' | 'inactive',
                'target_stocks': [str],  # 目标股票
                'stage': str,            # accumulation/markup/distribution
                'activity_level': str    # high/medium/low
            }
        """
        try:
            # TODO: 实现龙虎榜数据分析
            # 1. 查询近期龙虎榜上的游资席位
            # 2. 识别连续涨停的小盘股
            # 3. 分析成交量异常放大的个股

            # 暂时返回默认值
            return {
                'behavior': 'inactive',
                'target_stocks': [],
                'stage': None,
                'activity_level': 'low',
                'description': '游资活跃度较低，市场以价值投资为主'
            }

        except Exception as e:
            logger.warning(f"分析游资行为失败: {e}")
            return {
                'behavior': 'inactive',
                'target_stocks': [],
                'stage': None,
                'activity_level': 'low',
                'description': '数据不足，无法判断'
            }

    def _determine_market_phase(self, retail: Dict, institution: Dict) -> str:
        """
        判断市场阶段

        根据散户和机构的行为组合判断当前市场所处阶段

        Phases:
        - accumulation: 机构建仓，散户恐慌（底部）
        - markup: 机构和散户都在买入（上涨）
        - distribution: 机构出货，散户追涨（顶部）
        - markdown: 机构和散户都在卖出（下跌）
        - consolidation: 震荡整理

        Args:
            retail: 散户行为数据
            institution: 机构行为数据

        Returns:
            市场阶段
        """
        retail_behavior = retail['behavior']
        institution_behavior = institution['behavior']

        # 吸筹阶段：机构建仓，散户恐慌抛售
        if institution_behavior == 'accumulating' and retail_behavior == 'panic_selling':
            return 'accumulation'

        # 派发阶段：机构出货，散户FOMO追涨
        elif institution_behavior == 'distributing' and retail_behavior == 'fomo_buying':
            return 'distribution'

        # 上涨阶段：机构建仓，散户追涨
        elif institution_behavior == 'accumulating' and retail_behavior == 'fomo_buying':
            return 'markup'

        # 下跌阶段：机构出货，散户恐慌
        elif institution_behavior == 'distributing' and retail_behavior == 'panic_selling':
            return 'markdown'

        # 震荡整理
        else:
            return 'consolidation'

    def _assess_risk_appetite(self, retail: Dict, institution: Dict) -> str:
        """
        评估市场风险偏好

        Args:
            retail: 散户行为数据
            institution: 机构行为数据

        Returns:
            'high' | 'medium' | 'low'
        """
        emotion_index = retail['emotion_index']

        if emotion_index > 70:
            return 'high'
        elif emotion_index < 30:
            return 'low'
        else:
            return 'medium'

    def _generate_opportunity_map(self, retail: Dict, institution: Dict,
                                  hot_money: Dict) -> Dict[str, Any]:
        """
        生成博弈机会地图

        根据对手行为识别可以利用的机会

        Args:
            retail: 散户行为
            institution: 机构行为
            hot_money: 游资行为

        Returns:
            机会地图
        """
        opportunities = {}

        # 机会1: 收割散户恐慌
        if retail['behavior'] == 'panic_selling' and institution['behavior'] == 'accumulating':
            opportunities['take_from_retail'] = [{
                'strategy': 'bottom_fishing',
                'confidence': 0.85,
                'expected_return': '+5% ~ +10%',
                'time_horizon': '3-5 days',
                'reason': '散户恐慌抛售，机构逢低吸纳，优质股被错杀',
                'action': '创建"恐慌抄底池"，筛选基本面优质但超跌的股票'
            }]

        # 机会2: 避开机构出货陷阱
        if institution['behavior'] == 'distributing' and retail['behavior'] == 'fomo_buying':
            opportunities['avoid_institution'] = [{
                'risk': 'high',
                'reason': '机构大量出货，散户高位接盘',
                'action': '清仓观望，或做空相关板块',
                'urgency': 'critical'
            }]

        # 机会3: 跟随机构建仓
        if institution['behavior'] == 'accumulating' and retail['behavior'] == 'neutral':
            opportunities['follow_institution'] = [{
                'strategy': 'value_investing',
                'confidence': 0.75,
                'expected_return': '+10% ~ +20%',
                'time_horizon': '1-3 months',
                'reason': '机构悄悄建仓，散户尚未察觉',
                'action': f"关注机构建仓板块: {', '.join(institution['target_sectors'])}"
            }]

        # 机会4: 游资炒作后抄底
        if hot_money['behavior'] == 'pump_and_dump' and hot_money['stage'] == 'collapse':
            opportunities['post_manipulation'] = [{
                'strategy': 'value_recovery',
                'confidence': 0.65,
                'expected_return': '+15% ~ +30%',
                'time_horizon': '1-2 weeks',
                'reason': '游资出货完毕，恐慌盘杀跌结束',
                'action': '在游资炒作股暴跌后，筛选基本面尚可的股票抄底'
            }]

        return opportunities

    # ==================== 辅助方法 ====================

    def _calculate_retail_flow(self, start_date: datetime, end_date: datetime) -> float:
        """
        计算散户资金净流入（小单+中单）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            散户净流入金额（元）
        """
        try:
            # 获取市场聚合资金流向
            flows = self.fund_flow_repo.get_market_aggregate_flow(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )

            if not flows:
                logger.warning("未获取到资金流向数据，返回0")
                return 0.0

            # 计算散户净流入（小单 + 中单）
            total_retail_flow = sum([
                (row.get('total_small_flow') or 0) + (row.get('total_medium_flow') or 0)
                for row in flows
            ])

            logger.debug(f"散户资金流向: {total_retail_flow/100000000:.2f}亿元")
            return float(total_retail_flow)

        except Exception as e:
            logger.error(f"计算散户资金流失败: {e}")
            return 0.0

    def _calculate_institution_flow(self, start_date: datetime, end_date: datetime) -> float:
        """
        计算机构资金净流入（大单+特大单）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            机构净流入金额（元）
        """
        try:
            # 获取市场聚合资金流向
            flows = self.fund_flow_repo.get_market_aggregate_flow(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )

            if not flows:
                logger.warning("未获取到资金流向数据，返回0")
                return 0.0

            # 计算机构净流入（大单 + 特大单）
            # large = 大单, big = 特大单
            total_institution_flow = sum([
                (row.get('total_large_flow') or 0) + (row.get('total_big_flow') or 0)
                for row in flows
            ])

            logger.debug(f"机构资金流向: {total_institution_flow/100000000:.2f}亿元")
            return float(total_institution_flow)

        except Exception as e:
            logger.error(f"计算机构资金流失败: {e}")
            return 0.0

    def _identify_target_sectors(self, is_buying: bool) -> List[str]:
        """
        识别机构目标板块

        基于各行业资金流向，识别机构重点买入/卖出的板块

        Args:
            is_buying: 机构是否在买入

        Returns:
            目标板块列表
        """
        try:
            # TODO: 实现真实的板块识别逻辑
            # 需要：
            # 1. 获取行业分类数据
            # 2. 按行业聚合资金流向
            # 3. 排序找出资金流入/流出最多的行业

            # 暂时返回常见板块
            if is_buying:
                return ['医药', '消费', '科技']
            else:
                return ['周期', '地产', '金融']

        except Exception as e:
            logger.error(f"识别目标板块失败: {e}")
            return []

    def _get_behavior_description(self, behavior: str, participant: str) -> str:
        """获取行为描述"""
        descriptions = {
            ('panic_selling', 'retail'): '散户正在恐慌性抛售，情绪极度悲观',
            ('fomo_buying', 'retail'): '散户正在疯狂追涨，情绪极度乐观',
            ('neutral', 'retail'): '散户观望为主，情绪相对平稳',
            ('accumulating', 'institution'): '机构正在建仓，看好后市',
            ('distributing', 'institution'): '机构正在出货，准备离场',
            ('neutral', 'institution'): '机构维持仓位，暂无明显动向',
        }
        return descriptions.get((behavior, participant), '行为模式不明确')
