"""
博弈预警服务 - GameAlertService

实时监控市场博弈态势，发现风险和机会时主动预警
"""
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from domain.ports import IFundFlowRepository
from application.services.opponent_behavior_service import OpponentBehaviorService
from application.services.manipulation_detector import ManipulationDetector

logger = structlog.get_logger(__name__)


class GameAlertService:
    """博弈预警服务 - 实时监控和预警

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        fund_flow_repo: Optional[IFundFlowRepository] = None,
        opponent_service: Optional[OpponentBehaviorService] = None,
        manipulation_detector: Optional[ManipulationDetector] = None,
    ):
        """初始化服务

        Args:
            fund_flow_repo: 资金流仓库（可选）
            opponent_service: 对手行为服务（可选）
            manipulation_detector: 操纵检测器（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.fund_flow_repo = fund_flow_repo
        self.opponent_service = opponent_service or OpponentBehaviorService()
        self.manipulation_detector = manipulation_detector or ManipulationDetector()

        # 预警阈值配置
        self.thresholds = {
            'retail_panic_threshold': -30,  # 散户恐慌：净流出30亿
            'retail_fomo_threshold': 30,    # 散户追涨：净流入30亿
            'institution_flow_threshold': 20,  # 机构资金流：20亿
            'manipulation_confidence': 0.8,  # 操纵检测置信度
        }

    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        检查所有预警条件

        Returns:
            预警列表 [
                {
                    'alert_id': 'alert_001',
                    'type': 'opportunity',  # opportunity/risk
                    'level': 'high',        # low/medium/high/critical
                    'title': '抄底机会',
                    'message': '散户恐慌抛售，XX股超跌30%',
                    'action': '建议建仓',
                    'symbols': ['600519.SH'],
                    'created_at': '2026-06-26 01:00:00'
                }
            ]
        """
        logger.info("🔍 开始检查博弈预警")

        alerts = []

        try:
            # 1. 检查对手行为预警
            opponent_alerts = self._check_opponent_alerts()
            alerts.extend(opponent_alerts)

            # 2. 检查操纵预警
            manipulation_alerts = self._check_manipulation_alerts()
            alerts.extend(manipulation_alerts)

            # 3. 检查持仓风险预警（如果有持仓）
            # position_alerts = self._check_position_alerts()
            # alerts.extend(position_alerts)

            logger.info(f"✅ 预警检查完成: 发现{len(alerts)}个预警")
            return alerts

        except Exception as e:
            logger.error(f"❌ 预警检查失败: {e}", exc_info=True)
            return []

    def _check_opponent_alerts(self) -> List[Dict[str, Any]]:
        """检查对手行为预警"""
        alerts = []

        try:
            # 获取当前对手行为
            opponent_behavior = self.opponent_service.analyze_current_behavior()

            # 散户恐慌 + 机构建仓 = 抄底机会
            if (opponent_behavior['retail']['behavior'] == 'panic_selling' and
                opponent_behavior['institution']['behavior'] == 'accumulating'):

                alerts.append({
                    'alert_id': self._generate_alert_id(),
                    'type': 'opportunity',
                    'level': 'high',
                    'title': '抄底机会',
                    'message': (
                        f"散户恐慌抛售（{opponent_behavior['retail']['flow_amount']:.1f}亿），"
                        f"机构逢低建仓（{opponent_behavior['institution']['flow_amount']:.1f}亿）"
                    ),
                    'action': '建议创建"恐慌抄底池"',
                    'symbols': [],
                    'details': {
                        'market_phase': opponent_behavior['market_phase'],
                        'retail_emotion': opponent_behavior['retail']['emotion_index']
                    },
                    'created_at': datetime.now().isoformat()
                })

            # 散户追涨 + 机构出货 = 风险预警
            if (opponent_behavior['retail']['behavior'] == 'fomo_buying' and
                opponent_behavior['institution']['behavior'] == 'distributing'):

                alerts.append({
                    'alert_id': self._generate_alert_id(),
                    'type': 'risk',
                    'level': 'high',
                    'title': '顶部风险',
                    'message': (
                        f"散户追涨（{opponent_behavior['retail']['flow_amount']:.1f}亿），"
                        f"机构出货（{opponent_behavior['institution']['flow_amount']:.1f}亿）"
                    ),
                    'action': '建议减仓或空仓观望',
                    'symbols': [],
                    'details': {
                        'market_phase': opponent_behavior['market_phase']
                    },
                    'created_at': datetime.now().isoformat()
                })

            # 机构大量出货（无论散户如何）= 风险预警
            institution_flow = opponent_behavior['institution']['flow_amount']
            if institution_flow < -50:  # 机构净流出>50亿
                alerts.append({
                    'alert_id': self._generate_alert_id(),
                    'type': 'risk',
                    'level': 'critical',
                    'title': '机构大量出货',
                    'message': f"机构净流出{abs(institution_flow):.1f}亿，市场风险剧增",
                    'action': '建议大幅减仓或清仓',
                    'symbols': [],
                    'details': {
                        'institution_flow': institution_flow
                    },
                    'created_at': datetime.now().isoformat()
                })

        except Exception as e:
            logger.warning(f"检查对手行为预警失败: {e}")

        return alerts

    def _check_manipulation_alerts(self) -> List[Dict[str, Any]]:
        """检查操纵预警"""
        alerts = []

        try:
            # 执行操纵检测
            manipulation_result = self.manipulation_detector.detect_market_manipulation()

            # 活跃的操纵事件 → 风险预警
            active_manipulations = manipulation_result.get('active_manipulations', [])

            for manip in active_manipulations:
                # 只预警高置信度和高风险的
                if (manip.get('confidence', 0) >= self.thresholds['manipulation_confidence'] and
                    manip.get('risk_level') in ['high', 'extreme']):

                    alerts.append({
                        'alert_id': self._generate_alert_id(),
                        'type': 'risk',
                        'level': 'critical' if manip['risk_level'] == 'extreme' else 'high',
                        'title': '操纵风险预警',
                        'message': (
                            f"{manip['symbol']} {manip.get('name', '')} "
                            f"检测到{manip['manipulation_type']}操纵行为（置信度{manip['confidence']*100:.0f}%）"
                        ),
                        'action': '远离该股，避免高位接盘',
                        'symbols': [manip['symbol']],
                        'details': {
                            'manipulation_type': manip['manipulation_type'],
                            'stage': manip['stage'],
                            'signals': manip.get('signals', []),
                            'current_price': manip.get('current_price'),
                            'fair_value': manip.get('fair_value')
                        },
                        'created_at': datetime.now().isoformat()
                    })

            # 崩盘后机会 → 机会预警
            opportunities = manipulation_result.get('post_manipulation_opportunities', [])

            for opp in opportunities:
                if opp.get('confidence', 0) >= 0.7:
                    alerts.append({
                        'alert_id': self._generate_alert_id(),
                        'type': 'opportunity',
                        'level': 'medium',
                        'title': '崩盘抄底机会',
                        'message': (
                            f"{opp['symbol']} 已崩盘完成，"
                            f"当前价格{opp.get('current_price', 0):.2f}接近公允价值{opp.get('fair_value', 0):.2f}"
                        ),
                        'action': opp.get('entry_trigger', '止跌企稳后介入'),
                        'symbols': [opp['symbol']],
                        'details': {
                            'upside': opp.get('upside', 'N/A'),
                            'confidence': opp.get('confidence', 0)
                        },
                        'created_at': datetime.now().isoformat()
                    })

        except Exception as e:
            logger.warning(f"检查操纵预警失败: {e}")

        return alerts

    def _check_position_alerts(self) -> List[Dict[str, Any]]:
        """检查持仓风险预警"""
        alerts = []

        # TODO: 实现持仓风险检查
        # 需要获取当前持仓，检查每个持仓的风险状态

        return alerts

    def _generate_alert_id(self) -> str:
        """生成预警ID"""
        import uuid
        return f"alert_{uuid.uuid4().hex[:8]}"

    def get_alert_statistics(self) -> Dict[str, Any]:
        """
        获取预警统计

        Returns:
            {
                'total_alerts': 10,
                'by_type': {
                    'opportunity': 4,
                    'risk': 6
                },
                'by_level': {
                    'critical': 2,
                    'high': 3,
                    'medium': 4,
                    'low': 1
                },
                'recent_alerts': [...]
            }
        """
        # 简化实现：实时生成统计
        alerts = self.check_alerts()

        by_type = {}
        by_level = {}

        for alert in alerts:
            alert_type = alert.get('type', 'unknown')
            by_type[alert_type] = by_type.get(alert_type, 0) + 1

            level = alert.get('level', 'unknown')
            by_level[level] = by_level.get(level, 0) + 1

        return {
            'total_alerts': len(alerts),
            'by_type': by_type,
            'by_level': by_level,
            'recent_alerts': alerts[:10]
        }

    def subscribe_alerts(self, user_id: str, preferences: Dict) -> Dict[str, Any]:
        """
        订阅预警

        Args:
            user_id: 用户ID
            preferences: 订阅偏好 {
                'alert_types': ['opportunity', 'risk'],
                'min_level': 'medium',
                'symbols': ['600519.SH']  # 可选，指定关注股票
            }

        Returns:
            订阅信息
        """
        # TODO: 实现订阅逻辑（存储到数据库）
        logger.info(f"用户{user_id}订阅预警: {preferences}")

        return {
            'user_id': user_id,
            'subscribed': True,
            'preferences': preferences
        }
